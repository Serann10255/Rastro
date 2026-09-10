"""Microservicio de rastreo: registro de puntos de control.

Cubre REQ-02 (cada punto de control con estado, ubicacion, autor y marca de
tiempo) y REQ-03 (rechazo de toda transicion no contemplada en la maquina de
estados). El servicio no decide que transiciones son validas: se lo pregunta a
``rastro_core.state_machine``, que es la representacion ejecutable de la Figura 2
del documento.

La operacion se disena como un unico formulario y sin campos obligatorios mas
alla del estado, porque la viabilidad operativa depende de que registrar un
punto de control sea mas rapido que enviar un mensaje de chat. Si exige mas
pasos, el mensajero vuelve a la practica anterior.
"""

from __future__ import annotations

from fastapi import Depends

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.dominio import cargar_envio, construir_evento
from rastro_core.errors import ValidacionError
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.ids import marca_tiempo
from rastro_core.models import RegistrarEventoSolicitud
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
