"""Microservicio de rastreo: puntos de control y rutas de entrega.

Cubre REQ-02 (cada punto de control con estado, ubicacion, autor y marca de
tiempo) y REQ-03 (rechazo de toda transicion no contemplada en la maquina de
estados). El servicio no decide que transiciones son validas: se lo pregunta a
``rastro_core.state_machine``, que es la representacion ejecutable de la Figura 2
del documento.

Tambien sostiene las rutas de entrega: el conductor elige las guias que va a
entregar, sale a ruta y su telefono reporta la posicion mientras la ruta esta
abierta. Viven aqui y no en un servicio aparte porque una ruta es rastreo -mueve
envios por la maquina de estados y anade ubicacion a su recorrido- y porque
separarla obligaria a dos servicios a escribir el mismo estado de un envio.

La operacion se disena como un unico formulario y sin campos obligatorios mas
alla del estado, porque la viabilidad operativa depende de que registrar un
punto de control sea mas rapido que enviar un mensaje de chat. Si exige mas
pasos, el mensajero vuelve a la practica anterior.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, Query

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.dominio import cargar_envio, construir_evento
from rastro_core.errors import ConflictoError, NoEncontradoError, ValidacionError
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.ids import ahora_utc, marca_tiempo
from rastro_core.models import (
    FinalizarRutaSolicitud,
    IniciarRutaSolicitud,
    RegistrarEventoSolicitud,
    ReportarPosicionesSolicitud,
)
from rastro_core.rutas import (
    ESTADOS_APTOS_PARA_RUTA,
    MAX_POSICIONES_POR_CONSULTA,
    TESTIGO_HUERFANO_SEGUNDOS,
    EstadoRuta,
    camino_a_reparto,
    construir_ruta,
    edad_en_segundos,
    expiracion_del_recorrido,
    la_mas_reciente,
    normalizar_posicion,
    posterior_a,
    resumen,
    senal,
    vista_ruta,
)
from rastro_core.security import emitir_testigo_de_consulta, testigo_de_consulta_vigente
from rastro_core.state_machine import (
    ESTADOS_QUE_EXIGEN_EVIDENCIA,
    Estado,
    codigo_de,
    definicion,
    requiere_autorizacion_despachador,
    transiciones_permitidas,
    validar_transicion,
)

app = crear_app(
    "rastro-rastreo",
    "Registro de puntos de control con validacion de la maquina de estados.",
)


@app.get(
    "/envios/{envio_id}/transiciones",
    tags=["rastreo"],
    summary="Transiciones permitidas desde el estado actual",
)
async def consultar_transiciones(envio_id: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """La interfaz movil solo ofrece los estados alcanzables.

    Impedir la transicion invalida en el cliente reduce errores; rechazarla en
    el servidor es lo que la hace un control. Lo primero no sustituye lo segundo.
    """
    ctx.exigir(Operacion.ENVIO_CONSULTAR, recurso=f"envio/{envio_id}")
    envio = cargar_envio(ctx, envio_id, Operacion.ENVIO_CONSULTAR)
    estado = Estado(envio["estado"])
    previo = envio.get("estado_previo_incidencia")

    alcanzables = sorted(
        transiciones_permitidas(estado, estado_previo=previo), key=lambda e: codigo_de(e)
    )
    return {
        "envio_id": envio_id,
        "estado_actual": str(estado),
        "codigo_estado": codigo_de(estado),
        "estado_previo_incidencia": previo,
        "transiciones": [str(e) for e in alcanzables],
        # El detalle lleva el codigo y si cada destino exige despachador, para
        # que la interfaz no tenga que deducirlo con reglas propias que se
        # desincronizarian del servidor.
        "detalle_transiciones": [
            {
                "estado": str(e),
                "codigo": codigo_de(e),
                "etiqueta": definicion(e).etiqueta,
                "final": definicion(e).final,
                "exige_despachador": requiere_autorizacion_despachador(estado, e),
            }
            for e in alcanzables
        ],
        "exige_autorizacion_despachador": requiere_autorizacion_despachador(estado),
    }


@app.post(
    "/envios/{envio_id}/eventos",
    status_code=201,
    tags=["rastreo"],
    summary="Registrar un punto de control",
)
async def registrar_evento(
    envio_id: str,
    solicitud: RegistrarEventoSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    envio = _cargar_para_evento(ctx, envio_id, solicitud.estado)
    estado_actual = Estado(envio["estado"])
    estado_previo = envio.get("estado_previo_incidencia")
    recurso = f"envio/{envio_id}"

    # REQ-03: la transicion invalida se rechaza y el intento queda registrado.
    try:
        validar_transicion(estado_actual, solicitud.estado, estado_previo=estado_previo)
    except ValidacionError as exc:
        ctx.registrar(
            accion=Operacion.EVENTO_REGISTRAR,
            recurso=recurso,
            resultado=Resultado.DENY,
            detalle={"motivo": "transicion_invalida", **exc.detalle},
        )
        raise

    # REQ-05: no se da por entregado un envio sin la evidencia que lo acredite.
    if solicitud.estado in ESTADOS_QUE_EXIGEN_EVIDENCIA:
        _exigir_evidencia(ctx, envio, solicitud, recurso)

    evento = construir_evento(
        ctx,
        envio=envio,
        estado=solicitud.estado,
        estado_anterior=estado_actual,
        ubicacion=solicitud.ubicacion.as_dict() if solicitud.ubicacion else None,
        nota=solicitud.nota,
        evidencia_id=solicitud.evidencia_id,
    )
    ctx.repositorio.agregar_evento(evento)

    envio["estado"] = str(solicitud.estado)
    envio["codigo_estado"] = codigo_de(solicitud.estado)
    envio["actualizado_en"] = marca_tiempo()
    if solicitud.estado is Estado.INCIDENCIA:
        # Se conserva el estado desde el que se entro para poder reanudar.
        envio["estado_previo_incidencia"] = str(estado_actual)
    elif estado_actual is Estado.INCIDENCIA:
        envio["estado_previo_incidencia"] = None
    ctx.repositorio.actualizar_envio(envio)
    _reflejar_en_ruta(ctx, envio, solicitud.estado)

    ctx.registrar(
        accion=Operacion.EVENTO_REGISTRAR,
        recurso=recurso,
        resultado=Resultado.ALLOW,
        detalle={
            "estado_anterior": str(estado_actual),
            "codigo_anterior": codigo_de(estado_actual),
            "estado": str(solicitud.estado),
            "codigo_estado": codigo_de(solicitud.estado),
            "evento_id": evento["evento_id"],
            "con_ubicacion": solicitud.ubicacion is not None,
        },
    )
    return {"envio": envio, "evento": evento}


def _cargar_para_evento(ctx: Contexto, envio_id: str, estado_destino: Estado) -> dict:
    """Aplica la autorizacion que corresponde segun la transicion.

    Hay dos operaciones que el mensajero no decide por su cuenta: reanudar un
    envio detenido por una incidencia -el conductor reporta, otro rol autoriza-
    y cerrarlo por devolucion o cancelacion, que tienen efecto comercial sobre
    el cliente. Es una separacion de funciones deliberada.
    """
    envio_previo = cargar_envio(ctx, envio_id, Operacion.EVENTO_REGISTRAR)

    if requiere_autorizacion_despachador(Estado(envio_previo["estado"]), estado_destino):
        ctx.exigir(
            Operacion.EVENTO_REANUDAR,
            recurso=f"envio/{envio_id}",
            detalle={"estado_actual": envio_previo["estado"], "estado_solicitado": str(estado_destino)},
        )
        # La reanudacion no exige que el envio este asignado a quien la autoriza.
        return ctx.repositorio.obtener_envio(ctx.org_id, envio_id)

    ctx.exigir(Operacion.EVENTO_REGISTRAR, recurso=f"envio/{envio_id}")
    return envio_previo


def _exigir_evidencia(
    ctx: Contexto, envio: dict, solicitud: RegistrarEventoSolicitud, recurso: str
) -> None:
    evidencias = set(envio.get("evidencias") or ())
    if solicitud.evidencia_id and solicitud.evidencia_id in evidencias:
        return

    ctx.registrar(
        accion=Operacion.EVENTO_REGISTRAR,
        recurso=recurso,
        resultado=Resultado.DENY,
        detalle={
            "motivo": "entrega_sin_evidencia",
            "evidencia_id": solicitud.evidencia_id,
        },
    )
    raise ValidacionError(
        "La entrega exige una evidencia cargada y confirmada para este envio.",
        {"estado": str(solicitud.estado), "evidencia_id": solicitud.evidencia_id},
    )


def _reflejar_en_ruta(ctx: Contexto, envio: dict, estado: Estado) -> None:
    """Lleva el nuevo estado del envio a la parada de su ruta abierta.

    Es una copia para el mapa de seguimiento, no la fuente: el estado del envio
    ya quedo guardado y es el que vale. Por eso un fallo aqui no tumba el
    registro del punto de control -el conductor reintentaria y la maquina de
    estados le rechazaria una transicion que ya hizo- sino que deja la parada
    atrasada hasta el siguiente cambio.
    """
    ruta_id = envio.get("ruta_id")
    if not ruta_id:
        return
    try:
        ruta = ctx.repositorio.obtener_ruta(ctx.org_id, ruta_id)
        if ruta.get("estado") != EstadoRuta.ACTIVA:
            return
        for indice, parada in enumerate(ruta.get("paradas") or []):
            if parada.get("envio_id") == envio["envio_id"]:
                ctx.repositorio.anotar_parada(
                    ctx.org_id,
                    ruta_id,
                    indice,
                    envio["envio_id"],
                    str(estado),
                    codigo_de(estado),
                    marca_tiempo(),
                )
                return
    except Exception:  # noqa: BLE001 - la parada es derivada; el envio ya es correcto
        return


# --------------------------------------------------------------------------- #
# Rutas de entrega
# --------------------------------------------------------------------------- #


@app.post("/rutas", status_code=201, tags=["rutas"], summary="Salir a ruta con las guias elegidas")
async def iniciar_ruta(
    solicitud: IniciarRutaSolicitud, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """Abre la ruta del conductor y lleva cada envio a EN_REPARTO.

    Todo se valida antes de escribir nada: si una sola guia no puede salir, no
    sale ninguna. Al reves de lo que pasa con el registro en lote, aqui la
    seleccion es un todo -el conductor carga el vehiculo con esas guias- y una
    ruta a medias le diria al destinatario de la guia rechazada que su paquete
    va en camino cuando se quedo en la bodega.
    """
    ctx.exigir(Operacion.RUTA_OPERAR, recurso="ruta/nueva")

    identificadores = list(dict.fromkeys(e.strip() for e in solicitud.envios if e.strip()))
    if not identificadores:
        raise ValidacionError("Elija al menos una guia para salir a ruta.")
    envios = [cargar_envio(ctx, envio_id, Operacion.RUTA_OPERAR) for envio_id in identificadores]

    # Una ruta lleva los envios de quien conduce. Para un conductor, uno ajeno
    # ya respondio «no existe» al cargarlo; esto alcanza a quien ve toda la
    # operacion y podria, por error, salir a ruta con paquetes de otro.
    ajenos = [e["envio_id"] for e in envios if e.get("conductor_sub") != ctx.identidad.sub]
    if ajenos:
        _rechazar_inicio(ctx, "envio_de_otro_mensajero", {"envios": ajenos})
        raise ValidacionError(
            "Una ruta solo lleva envios asignados a quien la conduce.", {"envios": ajenos}
        )

    no_aptos = [
        {"envio_id": e["envio_id"], "estado": e["estado"]}
        for e in envios
        if Estado(e["estado"]) not in ESTADOS_APTOS_PARA_RUTA
    ]
    if no_aptos:
        _rechazar_inicio(ctx, "estado_no_apto_para_ruta", {"envios": no_aptos})
        raise ValidacionError(
            "Solo salen a ruta los envios que ya tiene en su poder: recolectados, en "
            "transito o en reparto.",
            {"no_aptos": no_aptos, "aptos": sorted(str(e) for e in ESTADOS_APTOS_PARA_RUTA)},
        )

    ruta = construir_ruta(
        org_id=ctx.org_id,
        conductor_sub=ctx.identidad.sub,
        conductor_nombre=next(
            (e["conductor_nombre"] for e in envios if e.get("conductor_nombre")),
            ctx.identidad.email or ctx.identidad.sub,
        ),
        envios=envios,
    )
    _reservar_ruta(ctx, ruta["ruta_id"])

    try:
        ubicacion = (
            solicitud.ubicacion.model_dump(include={"lat", "lon"}) if solicitud.ubicacion else None
        )
        transiciones = 0
        for envio, parada in zip(envios, ruta["paradas"], strict=True):
            estado_actual = Estado(envio["estado"])
            hora_previa: str | None = None
            for siguiente in camino_a_reparto(estado_actual):
                validar_transicion(estado_actual, siguiente)
                evento = construir_evento(
                    ctx,
                    envio=envio,
                    estado=siguiente,
                    estado_anterior=estado_actual,
                    ubicacion=ubicacion,
                    nota="Salida a ruta de entrega",
                )
                evento["ts"] = hora_previa = posterior_a(hora_previa)
                ctx.repositorio.agregar_evento(evento)
                estado_actual = siguiente
                transiciones += 1

            envio["estado"] = str(estado_actual)
            envio["codigo_estado"] = codigo_de(estado_actual)
            envio["ruta_id"] = ruta["ruta_id"]
            envio["actualizado_en"] = marca_tiempo()
            ctx.repositorio.actualizar_envio(envio)
            parada["estado"] = str(estado_actual)
            parada["codigo_estado"] = codigo_de(estado_actual)

        if solicitud.ubicacion:
            primera = {
                **normalizar_posicion(
                    solicitud.ubicacion.model_dump(), iniciada_en=ruta["iniciada_en"]
                ),
                "expira_en": expiracion_del_recorrido(),
            }
            ctx.repositorio.agregar_posiciones(ctx.org_id, ruta["ruta_id"], [primera])
            ruta["ultima_posicion"] = _sin_retencion(primera)
            ruta["posiciones"] = 1

        ctx.repositorio.guardar_ruta(ruta)
    except Exception:
        # Sin la ruta guardada, el testigo dejaria al conductor bloqueado: no
        # podria salir de nuevo hasta que venciera el margen de huerfano.
        ctx.repositorio.liberar_ruta_activa(ctx.org_id, ctx.identidad.sub, ruta["ruta_id"])
        raise

    ctx.registrar(
        accion=Operacion.RUTA_OPERAR,
        recurso=f"ruta/{ruta['ruta_id']}",
        resultado=Resultado.ALLOW,
        detalle={
            "operacion": "iniciar",
            "envios": identificadores,
            "transiciones": transiciones,
            "con_ubicacion": solicitud.ubicacion is not None,
        },
    )
    return {"ruta": vista_ruta(ruta), "transiciones": transiciones}


@app.get("/rutas/activa", tags=["rutas"], summary="La ruta en curso de quien consulta")
async def consultar_ruta_activa(
    testigo: str | None = Query(default=None, max_length=2000),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """La ruta abierta del conductor, o ninguna.

    Es lo que permite cerrar el navegador a mitad del recorrido sin perderlo:
    al volver, la pantalla pregunta aqui y retoma el modo ruta.

    Sin ruta, responde ademas que estados pueden salir a una: la pantalla de
    seleccion los necesita, y escribirlos alli seria una segunda copia de una
    regla que vive en ``rutas``.
    """
    ctx.exigir(Operacion.RUTA_OPERAR, recurso="ruta/activa")

    ruta = _ruta_activa_vigente(ctx)
    if ruta is None:
        return {
            "ruta": None,
            "testigo": None,
            "estados_aptos": sorted(str(e) for e in ESTADOS_APTOS_PARA_RUTA),
            "consultado_en": marca_tiempo(),
        }

    testigo = _dejar_constancia(
        ctx,
        operacion=Operacion.RUTA_OPERAR,
        recurso=f"ruta/{ruta['ruta_id']}",
        testigo=testigo,
        detalle={"paradas": len(ruta.get("paradas") or [])},
    )
    return {"ruta": vista_ruta(ruta), "testigo": testigo, "consultado_en": marca_tiempo()}


@app.get("/rutas", tags=["rutas"], summary="Rutas de la organizacion")
async def listar_rutas(
    estado: Literal["activas", "finalizadas", "todas"] = Query(default="activas"),
    testigo: str | None = Query(default=None, max_length=2000),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Lo que pinta el mapa de seguimiento: cada ruta con su ultima posicion.

    Ver donde esta una persona es leer un dato personal suyo, y por eso esta
    consulta deja constancia en la bitacora. Una sola por pantalla abierta cada
    pocos minutos, no una por cada refresco (ver ``_dejar_constancia``).
    """
    ctx.exigir(Operacion.RUTA_SEGUIR, recurso="ruta/lista")

    rutas = ctx.repositorio.listar_rutas(ctx.org_id, limite=100)
    if estado == "activas":
        rutas = [r for r in rutas if r.get("estado") == EstadoRuta.ACTIVA]
    elif estado == "finalizadas":
        rutas = [r for r in rutas if r.get("estado") == EstadoRuta.FINALIZADA]

    testigo = _dejar_constancia(
        ctx,
        operacion=Operacion.RUTA_SEGUIR,
        recurso="ruta/lista",
        testigo=testigo,
        detalle={"estado": estado, "devueltas": len(rutas)},
    )
    ahora = ahora_utc()
    return {
        "rutas": [vista_ruta(r, ahora) for r in rutas],
        "total": len(rutas),
        "testigo": testigo,
        "consultado_en": marca_tiempo(),
    }


@app.get("/rutas/{ruta_id}", tags=["rutas"], summary="Una ruta con su recorrido")
async def consultar_ruta(
    ruta_id: str,
    desde: str | None = Query(default=None, max_length=40),
    testigo: str | None = Query(default=None, max_length=2000),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """La ruta y las posiciones de su recorrido.

    Con ``desde`` devuelve solo las posiciones posteriores: el mapa pide cada
    diez segundos lo nuevo, no el recorrido entero cada vez.
    """
    ruta = _cargar_ruta_para_lectura(ctx, ruta_id)
    posiciones = ctx.repositorio.listar_posiciones(
        ctx.org_id, ruta_id, desde=desde, limite=MAX_POSICIONES_POR_CONSULTA
    )
    propia = ruta.get("conductor_sub") == ctx.identidad.sub
    testigo = _dejar_constancia(
        ctx,
        operacion=Operacion.RUTA_OPERAR if propia else Operacion.RUTA_SEGUIR,
        recurso=f"ruta/{ruta_id}",
        testigo=testigo,
        detalle={"posiciones": len(posiciones), "incremental": desde is not None},
    )
    return {
        "ruta": vista_ruta(ruta),
        "posiciones": [_sin_retencion(p) for p in posiciones],
        "testigo": testigo,
        "consultado_en": marca_tiempo(),
    }


@app.post(
    "/rutas/{ruta_id}/posiciones", tags=["rutas"], summary="Reportar la posicion del conductor"
)
async def reportar_posiciones(
    ruta_id: str,
    solicitud: ReportarPosicionesSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Recibe una o varias lecturas del GPS del telefono.

    No deja un eslabon por peticion en la bitacora: son cuatro por minuto y por
    conductor, y la bitacora registraria el pulso del telefono en lugar de lo
    que hacen las personas. Lo que si queda es el inicio y el cierre de la ruta
    -con el recuento de posiciones- y cada intento rechazado. Las posiciones
    mismas se conservan como el recorrido de la ruta.
    """
    ctx.exigir(Operacion.RUTA_OPERAR, recurso=f"ruta/{ruta_id}")
    ruta = _cargar_ruta_propia(ctx, ruta_id)
    if ruta.get("estado") != EstadoRuta.ACTIVA:
        raise ConflictoError(
            "La ruta ya termino: su ubicacion dejo de compartirse.", {"ruta_id": ruta_id}
        )

    ahora = ahora_utc()
    expira_en = expiracion_del_recorrido(ahora)
    nuevas = [
        {
            **normalizar_posicion(p.model_dump(), iniciada_en=ruta["iniciada_en"], ahora=ahora),
            "expira_en": expira_en,
        }
        for p in solicitud.posiciones
    ]
    ctx.repositorio.agregar_posiciones(ctx.org_id, ruta_id, nuevas)

    ultima = _sin_retencion(la_mas_reciente(ruta.get("ultima_posicion"), nuevas))
    ctx.repositorio.anotar_posiciones(ctx.org_id, ruta_id, ultima, len(nuevas), marca_tiempo())
    ruta["ultima_posicion"] = ultima
    return {"recibidas": len(nuevas), "ultima_posicion": ultima, "senal": senal(ruta, ahora)}


@app.post("/rutas/{ruta_id}/finalizacion", tags=["rutas"], summary="Terminar la ruta")
async def finalizar_ruta(
    ruta_id: str,
    solicitud: FinalizarRutaSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Cierra la ruta y deja de compartir la ubicacion.

    Las paradas que queden abiertas siguen en reparto: cerrar la ruta no dice
    que paso con esos paquetes, y decidirlo aqui -devolverlos, por ejemplo- seria
    una decision comercial que el conductor no toma (ver ``authz``).
    """
    ctx.exigir(Operacion.RUTA_OPERAR, recurso=f"ruta/{ruta_id}")
    ruta = _cargar_ruta_propia(ctx, ruta_id)
    if ruta.get("estado") != EstadoRuta.ACTIVA:
        raise ConflictoError("La ruta ya estaba finalizada.", {"ruta_id": ruta_id})

    cuenta = resumen(ruta)
    cierre = "completada" if cuenta["pendientes"] == 0 else "manual"
    ctx.repositorio.cerrar_ruta(
        ctx.org_id,
        ruta_id,
        finalizada_en=marca_tiempo(),
        cierre=cierre,
        nota_cierre=solicitud.nota.strip(),
    )
    ctx.repositorio.liberar_ruta_activa(ctx.org_id, ruta["conductor_sub"], ruta_id)

    ctx.registrar(
        accion=Operacion.RUTA_OPERAR,
        recurso=f"ruta/{ruta_id}",
        resultado=Resultado.ALLOW,
        detalle={
            "operacion": "finalizar",
            "cierre": cierre,
            **cuenta,
            "posiciones": int(ruta.get("posiciones", 0)),
        },
    )
    return {"ruta": vista_ruta(ctx.repositorio.obtener_ruta(ctx.org_id, ruta_id))}


# --------------------------------------------------------------------------- #
# Apoyo de las rutas
# --------------------------------------------------------------------------- #


def _rechazar_inicio(ctx: Contexto, motivo: str, detalle: dict) -> None:
    ctx.registrar(
        accion=Operacion.RUTA_OPERAR,
        recurso="ruta/nueva",
        resultado=Resultado.DENY,
        detalle={"motivo": motivo, **detalle},
    )


def _reservar_ruta(ctx: Contexto, ruta_id: str) -> None:
    """Toma el testigo de ruta activa del conductor, o explica por que no.

    Un testigo cuya ruta ya se cerro, o que nunca llego a tener ruta porque el
    inicio fallo a medias, no debe dejar al conductor sin poder salir: se
    libera y se vuelve a intentar. El margen de huerfano evita confundir con un
    abandono el inicio que esta ocurriendo en ese mismo momento.
    """
    repositorio = ctx.repositorio
    sub = ctx.identidad.sub
    try:
        repositorio.reservar_ruta_activa(ctx.org_id, sub, ruta_id)
        return
    except ConflictoError as exc:
        previa = exc.detalle.get("ruta_id")
        reservada_en = exc.detalle.get("reservada_en")

    try:
        vigente = repositorio.obtener_ruta(ctx.org_id, previa).get("estado") == EstadoRuta.ACTIVA
    except (NoEncontradoError, ValidacionError):
        edad = edad_en_segundos(reservada_en)
        vigente = edad is not None and edad < TESTIGO_HUERFANO_SEGUNDOS

    if vigente:
        _rechazar_inicio(ctx, "ruta_en_curso", {"ruta_id": previa})
        raise ConflictoError(
            "Ya tiene una ruta en curso. Terminela antes de salir con otra.", {"ruta_id": previa}
        )

    if previa:
        repositorio.liberar_ruta_activa(ctx.org_id, sub, previa)
    repositorio.reservar_ruta_activa(ctx.org_id, sub, ruta_id)


def _ruta_activa_vigente(ctx: Contexto) -> dict | None:
    testigo = ctx.repositorio.ruta_activa_de(ctx.org_id, ctx.identidad.sub)
    if not testigo:
        return None
    try:
        ruta = ctx.repositorio.obtener_ruta(ctx.org_id, testigo["ruta_id"])
    except NoEncontradoError:
        return None
    return ruta if ruta.get("estado") == EstadoRuta.ACTIVA else None


def _cargar_ruta(ctx: Contexto, ruta_id: str, operacion: Operacion) -> dict:
    """Recupera una ruta de la organizacion, o responde como si no existiera.

    El mismo criterio que ``cargar_envio``: una ruta de otra empresa recibe la
    misma respuesta que un identificador inventado, y el intento queda en la
    bitacora (REQ-06).
    """
    try:
        return ctx.repositorio.obtener_ruta(ctx.org_id, ruta_id)
    except (NoEncontradoError, ValidacionError):
        ctx.registrar(
            accion=operacion,
            recurso=f"ruta/{ruta_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "fuera_de_organizacion_o_inexistente"},
        )
        raise NoEncontradoError("La ruta no existe.", {"ruta_id": ruta_id}) from None


def _cargar_ruta_propia(ctx: Contexto, ruta_id: str) -> dict:
    """Solo quien conduce la ruta reporta su posicion o la cierra.

    No basta con ver la operacion completa: una posicion reportada por otra
    persona pondria el paquete donde no esta.
    """
    ruta = _cargar_ruta(ctx, ruta_id, Operacion.RUTA_OPERAR)
    if ruta.get("conductor_sub") != ctx.identidad.sub:
        ctx.registrar(
            accion=Operacion.RUTA_OPERAR,
            recurso=f"ruta/{ruta_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "ruta_de_otro_conductor"},
        )
        raise NoEncontradoError("La ruta no existe.", {"ruta_id": ruta_id})
    return ruta


def _cargar_ruta_para_lectura(ctx: Contexto, ruta_id: str) -> dict:
    """Quien sigue rutas ve cualquiera de su empresa; quien conduce, la suya."""
    if ctx.puede(Operacion.RUTA_SEGUIR):
        return _cargar_ruta(ctx, ruta_id, Operacion.RUTA_SEGUIR)
    if ctx.puede(Operacion.RUTA_OPERAR):
        return _cargar_ruta_propia(ctx, ruta_id)
    ctx.exigir(Operacion.RUTA_SEGUIR, recurso=f"ruta/{ruta_id}")
    raise NoEncontradoError("La ruta no existe.")  # pragma: no cover - exigir ya lanzo


def _dejar_constancia(
    ctx: Contexto, *, operacion: Operacion, recurso: str, testigo: str | None, detalle: dict
) -> str:
    """Registra la consulta en la bitacora, salvo que ya conste hace poco.

    Una pantalla de seguimiento abierta pregunta cada diez segundos. La primera
    pregunta se registra y recibe un testigo firmado; las siguientes lo
    devuelven y no se registran hasta que vence. El resultado es un eslabon por
    pantalla cada pocos minutos: lo bastante para saber quien miro la ubicacion
    de quien y cuando, sin que la bitacora se llene de refrescos.
    """
    if testigo and testigo_de_consulta_vigente(
        testigo, sub=ctx.identidad.sub, org_id=ctx.org_id, recurso=recurso
    ):
        return testigo
    ctx.registrar(
        accion=operacion,
        recurso=recurso,
        resultado=Resultado.ALLOW,
        detalle={**detalle, "consulta": True},
    )
    return emitir_testigo_de_consulta(sub=ctx.identidad.sub, org_id=ctx.org_id, recurso=recurso)


def _sin_retencion(posicion: dict | None) -> dict | None:
    """La marca de expiracion es del almacenamiento, no de quien consulta."""
    if posicion is None:
        return None
    return {c: v for c, v in posicion.items() if c not in {"expira_en", "org_id", "ruta_id"}}
