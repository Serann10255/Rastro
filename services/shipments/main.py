"""Microservicio de envios: registro, asignacion y consulta autenticada.

Cubre REQ-01 (registro con identificador unico no predecible) y la asignacion de
mensajero, que es la operacion con la que el despachador pone el envio en manos
de un conductor concreto.
"""

from __future__ import annotations

from fastapi import Depends, Query

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.dominio import (
    cargar_envio,
    construir_envio,
    construir_evento,
    historico_autenticado,
    resumen_para_lista,
)
from rastro_core.errors import ValidacionError
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.ids import marca_tiempo
from rastro_core.models import AsignarConductorSolicitud, CrearEnvioSolicitud
from rastro_core.state_machine import Estado, validar_transicion

app = crear_app(
    "rastro-envios",
    "Registro, asignacion y consulta de envios dentro de una organizacion.",
)


@app.post("/envios", status_code=201, tags=["envios"], summary="Registrar un envio")
async def crear_envio(
    solicitud: CrearEnvioSolicitud, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """REQ-01. Un conductor que invoque esta operacion recibe 403 y queda en bitacora."""
    ctx.exigir(Operacion.ENVIO_CREAR, recurso="envio/nuevo")

    envio = construir_envio(ctx, solicitud)
    ctx.repositorio.guardar_envio(envio)

    evento = construir_evento(
        ctx, envio=envio, estado=Estado.CREADO, estado_anterior=None, nota="Registro del envio"
    )
    ctx.repositorio.agregar_evento(evento)

    ctx.registrar(
        accion=Operacion.ENVIO_CREAR,
        recurso=f"envio/{envio['envio_id']}",
        resultado=Resultado.ALLOW,
        detalle={"estado": Estado.CREADO.value},
    )
    return {"envio": envio, "evento": evento}


@app.post("/envios/{envio_id}/asignacion", tags=["envios"], summary="Asignar mensajero")
async def asignar_conductor(
    envio_id: str,
    solicitud: AsignarConductorSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Transicion CREADO -> ASIGNADO. La valida la maquina de estados, no el servicio."""
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


@app.get("/envios", tags=["envios"], summary="Listar envios de la organizacion")
async def listar_envios(
    limite: int = Query(default=50, ge=1, le=200),
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


@app.get("/envios/{envio_id}", tags=["envios"], summary="Consultar un envio con su historico")
async def consultar_envio(envio_id: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.ENVIO_CONSULTAR, recurso=f"envio/{envio_id}")
    return historico_autenticado(ctx, envio_id)
