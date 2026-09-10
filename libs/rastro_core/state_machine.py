"""Maquina de estados del ciclo de vida de un envio (Figura 2 del documento).

El sistema admite unicamente las transiciones declaradas aqui. Cualquier otra
combinacion se rechaza con codigo 400 y el intento queda registrado en la
bitacora con resultado DENY (REQ-03).
"""

from __future__ import annotations

from enum import StrEnum

from .errors import TransicionInvalidaError


class Estado(StrEnum):
    CREADO = "CREADO"
    ASIGNADO = "ASIGNADO"
    RECOLECTADO = "RECOLECTADO"
    EN_TRANSITO = "EN_TRANSITO"
    EN_REPARTO = "EN_REPARTO"
    ENTREGADO = "ENTREGADO"
    INCIDENCIA = "INCIDENCIA"


#: Secuencia normal del proceso, de recepcion a entrega.
FLUJO_PRINCIPAL: tuple[Estado, ...] = (
    Estado.CREADO,
    Estado.ASIGNADO,
    Estado.RECOLECTADO,
    Estado.EN_TRANSITO,
    Estado.EN_REPARTO,
    Estado.ENTREGADO,
)

#: Estado final: no admite ninguna transicion de salida.
ESTADOS_FINALES: frozenset[Estado] = frozenset({Estado.ENTREGADO})

#: Transiciones del flujo principal, sin contar las que involucran INCIDENCIA.
_TRANSICIONES_BASE: dict[Estado, frozenset[Estado]] = {
    origen: frozenset({destino})
    for origen, destino in zip(FLUJO_PRINCIPAL, FLUJO_PRINCIPAL[1:])
}

#: INCIDENCIA se alcanza desde cualquier estado anterior a la entrega.
ORIGENES_INCIDENCIA: frozenset[Estado] = frozenset(
    e for e in FLUJO_PRINCIPAL if e not in ESTADOS_FINALES
)

#: La entrega exige evidencia cargada antes de aceptar la transicion (REQ-05).
ESTADOS_QUE_EXIGEN_EVIDENCIA: frozenset[Estado] = frozenset({Estado.ENTREGADO})


def transiciones_permitidas(origen: Estado, *, estado_previo: Estado | None = None) -> frozenset[Estado]:
    """Devuelve los estados alcanzables desde ``origen``.

    Desde INCIDENCIA solo se puede reanudar hacia el estado en que se
    encontraba el envio antes del incidente o hacia el siguiente del flujo, y
    esa reanudacion exige autorizacion del despachador (ver ``authz``).
    """
    origen = Estado(origen)
    if origen in ESTADOS_FINALES:
        return frozenset()

    if origen is Estado.INCIDENCIA:
        if estado_previo is None:
            return frozenset()
        previo = Estado(estado_previo)
        destinos = {previo}
        destinos |= set(_TRANSICIONES_BASE.get(previo, frozenset()))
        return frozenset(destinos)

    permitidas = set(_TRANSICIONES_BASE.get(origen, frozenset()))
    if origen in ORIGENES_INCIDENCIA:
        permitidas.add(Estado.INCIDENCIA)
    return frozenset(permitidas)


def es_transicion_valida(origen: Estado, destino: Estado, *, estado_previo: Estado | None = None) -> bool:
    return Estado(destino) in transiciones_permitidas(origen, estado_previo=estado_previo)


def validar_transicion(origen: Estado, destino: Estado, *, estado_previo: Estado | None = None) -> None:
    """Lanza ``TransicionInvalidaError`` si la transicion no esta contemplada."""
    origen = Estado(origen)
    try:
        destino = Estado(destino)
    except ValueError as exc:
        raise TransicionInvalidaError(
            f"El estado '{destino}' no existe en la maquina de estados.",
            {"origen": str(origen), "destino": str(destino)},
        ) from exc

    if not es_transicion_valida(origen, destino, estado_previo=estado_previo):
        permitidas = sorted(str(e) for e in transiciones_permitidas(origen, estado_previo=estado_previo))
        raise TransicionInvalidaError(
            f"Transicion no permitida de {origen} a {destino}.",
            {"origen": str(origen), "destino": str(destino), "permitidas": permitidas},
        )


def requiere_autorizacion_despachador(origen: Estado) -> bool:
    """La reanudacion tras una incidencia es la operacion mas sensible.

    Introduce una separacion de funciones: el conductor reporta la incidencia,
    pero solo el despachador puede reanudar el envio.
    """
    return Estado(origen) is Estado.INCIDENCIA
