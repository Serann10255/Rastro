"""Microservicio de envios: registro, asignacion, consulta y guias.

Cubre REQ-01 (registro con identificador unico no predecible) y la asignacion de
mensajero. Ademas resuelve las dos operaciones que un cliente corporativo hace a
diario y que no tienen sentido de una en una: registrar un lote de envios y
generar sus guias.
"""

from __future__ import annotations

import csv
import io

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.dominio import (
    cargar_envio,
    construir_envio,
    construir_evento,
    datos_de_etiqueta,
    historico_autenticado,
    resumen_para_lista,
)
from rastro_core.errors import ValidacionError
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.ids import marca_tiempo
from rastro_core.maestros import RepositorioMaestros
from rastro_core.models import AsignarConductorSolicitud, CrearEnvioSolicitud, CrearLoteSolicitud
from rastro_core.state_machine import Estado, codigo_de, validar_transicion

app = crear_app(
    "rastro-envios",
    "Registro, asignacion, consulta y generacion de guias.",
)

#: Tope de guias por peticion. Generar mil etiquetas de una vez agota la memoria
#: de la funcion y produce un fallo sin explicacion; con tope, el limite se
#: comunica y quien lo alcanza pagina.
MAX_ETIQUETAS = 200

_maestros: RepositorioMaestros | None = None


def maestros() -> RepositorioMaestros:
    global _maestros
    if _maestros is None:
        _maestros = RepositorioMaestros()
    return _maestros


def fijar_maestros(repositorio: RepositorioMaestros) -> None:
    global _maestros
    _maestros = repositorio


class SolicitudEtiquetas(BaseModel):
    envios: list[str] = Field(min_length=1, max_length=MAX_ETIQUETAS)


# --------------------------------------------------------------------------- #
# Resolucion de referencias
# --------------------------------------------------------------------------- #


def _resolver_referencias(ctx: Contexto, solicitud: CrearEnvioSolicitud) -> dict:
    """Comprueba que tienda, cliente y transportista existen en la organizacion.

    Se validan aqui y no se aceptan a ciegas: un identificador inventado
    produciria un envio que apunta a una tienda inexistente, y el problema solo
    aparece meses despues, al intentar reconstruir de donde salio.
    """
    referencias: dict[str, str] = {}

    if solicitud.tienda_id:
        tienda = maestros().obtener_tienda(ctx.org_id, solicitud.tienda_id)
        referencias["tienda_nombre"] = tienda["nombre"]
    if solicitud.cliente_id:
        cliente = maestros().obtener_cliente(ctx.org_id, solicitud.cliente_id)
        referencias["cliente_nombre"] = cliente["nombre"]
    if solicitud.transportista_id:
        transportista = maestros().obtener_transportista(ctx.org_id, solicitud.transportista_id)
        referencias["transportista_nombre"] = transportista["nombre"]

    return referencias


def _crear_uno(ctx: Contexto, solicitud: CrearEnvioSolicitud) -> dict:
    envio = construir_envio(ctx, solicitud, referencias=_resolver_referencias(ctx, solicitud))
    ctx.repositorio.guardar_envio(envio)

    evento = construir_evento(
        ctx, envio=envio, estado=Estado.CREADO, estado_anterior=None, nota="Registro del envio"
    )
    ctx.repositorio.agregar_evento(evento)
    return {"envio": envio, "evento": evento}


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #


@app.post("/envios", status_code=201, tags=["envios"], summary="Registrar un envio")
async def crear_envio(
    solicitud: CrearEnvioSolicitud, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """REQ-01. Un conductor que invoque esta operacion recibe 403 y queda en bitacora."""
    ctx.exigir(Operacion.ENVIO_CREAR, recurso="envio/nuevo")

    resultado = _crear_uno(ctx, solicitud)

    ctx.registrar(
        accion=Operacion.ENVIO_CREAR,
        recurso=f"envio/{resultado['envio']['envio_id']}",
        resultado=Resultado.ALLOW,
        detalle={"estado": Estado.CREADO.value, "codigo_estado": codigo_de(Estado.CREADO)},
    )
    return resultado


@app.post("/envios/lote", status_code=201, tags=["envios"], summary="Registrar un lote de envios")
async def crear_lote(lote: CrearLoteSolicitud, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Registra varios envios en una sola peticion.

    Un envio que falla no impide los demas: se devuelve la lista de creados y la
    de rechazados con su motivo. Abortar el lote entero por una fila mala
    obligaria a corregir el archivo y reenviarlo completo, y quien despacha
    doscientos envios acabaria partiendolo a mano para encontrar cual falla.

    La bitacora registra el lote como una operacion, con su recuento: doscientos
    eslabones por un solo despacho enterrarian el resto del historico.
    """
    ctx.exigir(Operacion.ENVIO_CREAR, recurso="envio/lote")

    creados: list[dict] = []
    rechazados: list[dict] = []

    for indice, solicitud in enumerate(lote.envios):
        try:
            creados.append(_crear_uno(ctx, solicitud)["envio"])
        except Exception as exc:  # noqa: BLE001 - una fila mala no tumba el lote
            rechazados.append(
                {
                    "indice": indice,
                    "destinatario": solicitud.destinatario.nombre,
                    "orden_compra": solicitud.orden_compra,
                    "motivo": getattr(exc, "mensaje", str(exc)),
                }
            )

    ctx.registrar(
        accion=Operacion.ENVIO_CREAR,
        recurso="envio/lote",
        resultado=Resultado.ALLOW if creados else Resultado.DENY,
        detalle={
            "solicitados": len(lote.envios),
            "creados": len(creados),
            "rechazados": len(rechazados),
        },
    )
    return {
        "creados": [resumen_para_lista(e) for e in creados],
        "rechazados": rechazados,
        "resumen": {
            "solicitados": len(lote.envios),
            "creados": len(creados),
            "rechazados": len(rechazados),
        },
    }


@app.post("/envios/{envio_id}/asignacion", tags=["envios"], summary="Asignar mensajero")
async def asignar_conductor(
    envio_id: str,
    solicitud: AsignarConductorSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Transicion CREADO -> ASIGNADO. La valida la maquina de estados."""
    ctx.exigir(Operacion.ENVIO_ASIGNAR, recurso=f"envio/{envio_id}")
    envio = cargar_envio(ctx, envio_id, Operacion.ENVIO_ASIGNAR)

    estado_actual = Estado(envio["estado"])
    try:
        validar_transicion(estado_actual, Estado.ASIGNADO)
    except ValidacionError as exc:
        ctx.registrar(
            accion=Operacion.ENVIO_ASIGNAR,
            recurso=f"envio/{envio_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "transicion_invalida", **exc.detalle},
        )
        raise

    envio["conductor_sub"] = solicitud.conductor_sub
    envio["conductor_nombre"] = solicitud.conductor_nombre
    envio["estado"] = Estado.ASIGNADO.value
    envio["codigo_estado"] = codigo_de(Estado.ASIGNADO)
    envio["actualizado_en"] = marca_tiempo()
    ctx.repositorio.actualizar_envio(envio)

    evento = construir_evento(
        ctx,
        envio=envio,
        estado=Estado.ASIGNADO,
        estado_anterior=estado_actual,
        nota=f"Asignado a {solicitud.conductor_nombre or solicitud.conductor_sub}",
    )
    ctx.repositorio.agregar_evento(evento)

    ctx.registrar(
        accion=Operacion.ENVIO_ASIGNAR,
        recurso=f"envio/{envio_id}",
        resultado=Resultado.ALLOW,
        detalle={"conductor_sub": solicitud.conductor_sub},
    )
    return {"envio": envio, "evento": evento}


# --------------------------------------------------------------------------- #
# Consulta
# --------------------------------------------------------------------------- #


@app.get("/envios", tags=["envios"], summary="Listar envios de la organizacion")
async def listar_envios(
    limite: int = Query(default=200, ge=1, le=2000),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """El despachador ve los de su organizacion; el conductor, solo los suyos."""
    ctx.exigir(Operacion.ENVIO_LISTAR, recurso="envio/lista")

    envios = ctx.repositorio.listar_envios(ctx.org_id, limite=limite)
    if ctx.exige_envio_propio(Operacion.ENVIO_LISTAR):
        envios = [e for e in envios if e.get("conductor_sub") == ctx.identidad.sub]

    ctx.registrar(
        accion=Operacion.ENVIO_LISTAR,
        recurso="envio/lista",
        resultado=Resultado.ALLOW,
        detalle={"devueltos": len(envios)},
    )
    return {"envios": [resumen_para_lista(e) for e in envios], "total": len(envios)}


@app.get("/envios/exportar", tags=["envios"], summary="Exportar los envios a CSV")
async def exportar(ctx: Contexto = Depends(contexto_actual)) -> StreamingResponse:
    """Descarga la operacion en un archivo que se abre en una hoja de calculo.

    El estado sale con su codigo numerico ademas del nombre: es lo que hace
    interpretable el archivo para un sistema que no habla espanol.
    """
    ctx.exigir(Operacion.ENVIO_LISTAR, recurso="envio/exportar")

    envios = ctx.repositorio.listar_envios(ctx.org_id, limite=5000)
    if ctx.exige_envio_propio(Operacion.ENVIO_LISTAR):
        envios = [e for e in envios if e.get("conductor_sub") == ctx.identidad.sub]

    columnas = [
        "envio_id",
        "codigo_estado",
        "estado",
        "orden_compra",
        "cliente_nombre",
        "tienda_nombre",
        "destinatario",
        "direccion_destino",
        "ciudad_destino",
        "telefono",
        "conductor_nombre",
        "transportista_nombre",
        "bultos",
        "peso_kg",
        "fecha_estimada",
        "creado_en",
        "actualizado_en",
    ]

    memoria = io.StringIO()
    escritor = csv.DictWriter(memoria, fieldnames=columnas, extrasaction="ignore")
    escritor.writeheader()
    for envio in envios:
        destino = envio.get("destino") or {}
        destinatario = envio.get("destinatario") or {}
        escritor.writerow(
            {
                **{c: envio.get(c, "") for c in columnas},
                "destinatario": destinatario.get("nombre", ""),
                "telefono": destinatario.get("telefono", ""),
                "direccion_destino": destino.get("linea", ""),
                "ciudad_destino": destino.get("ciudad", ""),
            }
        )

    ctx.registrar(
        accion=Operacion.ENVIO_LISTAR,
        recurso="envio/exportar",
        resultado=Resultado.ALLOW,
        detalle={"exportados": len(envios), "formato": "csv"},
    )

    memoria.seek(0)
    nombre = f"envios-{ctx.org_id}-{marca_tiempo()[:10]}.csv"
    return StreamingResponse(
        iter([memoria.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@app.get("/envios/{envio_id}", tags=["envios"], summary="Consultar un envio con su historico")
async def consultar_envio(envio_id: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.ENVIO_CONSULTAR, recurso=f"envio/{envio_id}")
    return historico_autenticado(ctx, envio_id)


# --------------------------------------------------------------------------- #
# Guias
# --------------------------------------------------------------------------- #


@app.post("/envios/etiquetas", tags=["guias"], summary="Datos de guia de varios envios")
async def generar_etiquetas(
    solicitud: SolicitudEtiquetas, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """Devuelve los datos de guia; la interfaz los compone e imprime.

    El servicio no genera el PDF. Podria, pero implicaria una dependencia de
    composicion tipografica en una funcion de computo bajo demanda, y el
    navegador ya sabe imprimir. Lo que el servicio si hace es decidir que datos
    salen en la guia, que es la parte que no puede quedar en el cliente.

    Cada envio se carga por el camino unico de ``cargar_envio``, de modo que
    pedir guias en lote no es una via para saltarse el filtro por organizacion.
    """
    ctx.exigir(Operacion.ENVIO_CONSULTAR, recurso="envio/etiquetas")

    empresa = maestros().obtener_empresa(ctx.org_id)

    etiquetas: list[dict] = []
    no_encontrados: list[str] = []
    for envio_id in solicitud.envios:
        try:
            envio = cargar_envio(ctx, envio_id, Operacion.ENVIO_CONSULTAR)
        except Exception:  # noqa: BLE001 - un identificador ajeno no revela nada
            no_encontrados.append(envio_id)
            continue
        etiquetas.append(datos_de_etiqueta(envio, empresa))

    ctx.registrar(
        accion=Operacion.ENVIO_CONSULTAR,
        recurso="envio/etiquetas",
        resultado=Resultado.ALLOW,
        detalle={"solicitadas": len(solicitud.envios), "generadas": len(etiquetas)},
    )
    return {"etiquetas": etiquetas, "no_encontrados": no_encontrados}
