"""Catalogo de estados y maquina de estados del ciclo de vida de un envio.

Cada estado tiene un **codigo numerico unico** dentro de un rango compacto
(10-90, en saltos de diez). El codigo existe por una razon operativa: es lo que
viaja en los archivos de intercambio con transportistas y clientes, donde un
nombre en texto es fragil -cambia con el idioma, con la ortografia y con quien
escriba el archivo- mientras que un numero no. Los saltos de diez dejan sitio
para intercalar estados sin renumerar los existentes, que es lo que obligaria a
reprocesar el historico.

El sistema admite unicamente las transiciones representadas aqui. Cualquier otra
combinacion se rechaza con codigo 400 y el intento queda registrado en la
bitacora con resultado DENY (REQ-03).
"""

from __future__ import annotations

from dataclasses import dataclass
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
    DEVUELTO = "DEVUELTO"
    CANCELADO = "CANCELADO"


class Fase(StrEnum):
    """Agrupacion de estados para los tableros y los informes."""

    REGISTRO = "registro"
    PREPARACION = "preparacion"
    TRANSPORTE = "transporte"
    DISTRIBUCION = "distribucion"
    CIERRE = "cierre"
    EXCEPCION = "excepcion"


@dataclass(frozen=True)
class DefinicionEstado:
    codigo: int
    estado: Estado
    fase: Fase
    etiqueta: str
    descripcion: str
    #: Un estado final no admite ninguna transicion de salida.
    final: bool = False
    #: Un cierre correcto (entregado) frente a un cierre por excepcion.
    exitoso: bool = False


#: El catalogo. El orden es el del avance del proceso, no el alfabetico: es el
#: que espera cualquiera que lea un tablero de operacion.
CATALOGO: tuple[DefinicionEstado, ...] = (
    DefinicionEstado(
        10, Estado.CREADO, Fase.REGISTRO, "Creado",
        "El envio esta registrado y tiene identificador, pero nadie lo ha tomado todavia.",
    ),
    DefinicionEstado(
        20, Estado.ASIGNADO, Fase.PREPARACION, "Asignado",
        "Hay un mensajero responsable del envio.",
    ),
    DefinicionEstado(
        30, Estado.RECOLECTADO, Fase.PREPARACION, "Recolectado",
        "El mensajero tiene el paquete en su poder.",
    ),
    DefinicionEstado(
        40, Estado.EN_TRANSITO, Fase.TRANSPORTE, "En transito",
        "El paquete se desplaza entre puntos de la red.",
    ),
    DefinicionEstado(
        50, Estado.EN_REPARTO, Fase.DISTRIBUCION, "En reparto",
        "El paquete va en la ruta de ultima milla hacia el destinatario.",
    ),
    DefinicionEstado(
        60, Estado.ENTREGADO, Fase.CIERRE, "Entregado",
        "El destinatario recibio el paquete y existe evidencia que lo acredita.",
        final=True, exitoso=True,
    ),
    DefinicionEstado(
        70, Estado.INCIDENCIA, Fase.EXCEPCION, "Incidencia",
        "El envio esta detenido. Reanudarlo exige autorizacion del despachador.",
    ),
    DefinicionEstado(
        80, Estado.DEVUELTO, Fase.CIERRE, "Devuelto al origen",
        "El envio volvio al remitente sin haberse entregado.",
        final=True,
    ),
    DefinicionEstado(
        90, Estado.CANCELADO, Fase.CIERRE, "Cancelado",
        "El envio se anulo antes de que el mensajero lo recogiera.",
        final=True,
    ),
)

POR_ESTADO: dict[Estado, DefinicionEstado] = {d.estado: d for d in CATALOGO}
POR_CODIGO: dict[int, DefinicionEstado] = {d.codigo: d for d in CATALOGO}

#: Secuencia normal del proceso, de recepcion a entrega.
FLUJO_PRINCIPAL: tuple[Estado, ...] = (
    Estado.CREADO,
    Estado.ASIGNADO,
    Estado.RECOLECTADO,
    Estado.EN_TRANSITO,
    Estado.EN_REPARTO,
    Estado.ENTREGADO,
)

ESTADOS_FINALES: frozenset[Estado] = frozenset(d.estado for d in CATALOGO if d.final)

#: Transiciones del flujo principal, sin contar las que involucran INCIDENCIA.
_TRANSICIONES_BASE: dict[Estado, frozenset[Estado]] = {
    origen: frozenset({destino})
    for origen, destino in zip(FLUJO_PRINCIPAL, FLUJO_PRINCIPAL[1:])
}

#: INCIDENCIA se alcanza desde cualquier estado anterior a un cierre.
ORIGENES_INCIDENCIA: frozenset[Estado] = frozenset(
    e for e in FLUJO_PRINCIPAL if e not in ESTADOS_FINALES
)

#: Cancelar solo tiene sentido antes de que el paquete salga del origen. Una vez
#: recolectado, lo que corresponde es devolverlo, no anularlo: el paquete existe
#: y esta en poder de alguien.
ORIGENES_CANCELACION: frozenset[Estado] = frozenset({Estado.CREADO, Estado.ASIGNADO})

#: La devolucion cierra un envio que ya salio pero no llego a su destinatario.
ORIGENES_DEVOLUCION: frozenset[Estado] = frozenset(
    {Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO, Estado.INCIDENCIA}
)

#: La entrega exige evidencia cargada antes de aceptar la transicion (REQ-05).
ESTADOS_QUE_EXIGEN_EVIDENCIA: frozenset[Estado] = frozenset({Estado.ENTREGADO})

#: Cerrar un envio por devolucion o cancelacion no lo puede decidir el mensajero:
#: son decisiones comerciales con efecto sobre el cliente.
ESTADOS_QUE_EXIGEN_DESPACHADOR: frozenset[Estado] = frozenset(
    {Estado.DEVUELTO, Estado.CANCELADO}
)


# --------------------------------------------------------------------------- #
# Consulta del catalogo
# --------------------------------------------------------------------------- #


def definicion(estado: Estado | str) -> DefinicionEstado:
    try:
        return POR_ESTADO[Estado(estado)]
    except (ValueError, KeyError) as exc:
        raise TransicionInvalidaError(
            f"El estado '{estado}' no existe en el catalogo.", {"estado": str(estado)}
        ) from exc


def codigo_de(estado: Estado | str) -> int:
    return definicion(estado).codigo


def estado_de_codigo(codigo: int) -> Estado:
    """Traduce el codigo numerico de un archivo de intercambio a su estado."""
    try:
        return POR_CODIGO[int(codigo)].estado
    except (ValueError, KeyError, TypeError) as exc:
        raise TransicionInvalidaError(
            f"El codigo de estado {codigo} no existe en el catalogo.",
            {"codigo": codigo, "codigos_validos": sorted(POR_CODIGO)},
        ) from exc


def catalogo_publico() -> list[dict]:
    """El catalogo completo, para que la interfaz no lo duplique."""
    return [
        {
            "codigo": d.codigo,
            "estado": str(d.estado),
            "fase": str(d.fase),
            "etiqueta": d.etiqueta,
            "descripcion": d.descripcion,
            "final": d.final,
            "exitoso": d.exitoso,
        }
        for d in CATALOGO
    ]


# --------------------------------------------------------------------------- #
# Maquina de estados
# --------------------------------------------------------------------------- #


def transiciones_permitidas(
    origen: Estado, *, estado_previo: Estado | None = None
) -> frozenset[Estado]:
    """Devuelve los estados alcanzables desde ``origen``.

    Desde INCIDENCIA solo se puede reanudar hacia el estado en que se
    encontraba el envio antes del incidente o hacia el siguiente del flujo, y
    esa reanudacion exige autorizacion del despachador (ver ``authz``).
    """
    origen = Estado(origen)
    if origen in ESTADOS_FINALES:
        return frozenset()

    if origen is Estado.INCIDENCIA:
        destinos: set[Estado] = {Estado.DEVUELTO}
        if estado_previo is not None:
            previo = Estado(estado_previo)
            destinos.add(previo)
            destinos |= set(_TRANSICIONES_BASE.get(previo, frozenset()))
        return frozenset(destinos)

    permitidas = set(_TRANSICIONES_BASE.get(origen, frozenset()))
    if origen in ORIGENES_INCIDENCIA:
        permitidas.add(Estado.INCIDENCIA)
    if origen in ORIGENES_CANCELACION:
        permitidas.add(Estado.CANCELADO)
    if origen in ORIGENES_DEVOLUCION:
        permitidas.add(Estado.DEVUELTO)
    return frozenset(permitidas)


def es_transicion_valida(
    origen: Estado, destino: Estado, *, estado_previo: Estado | None = None
) -> bool:
    return Estado(destino) in transiciones_permitidas(origen, estado_previo=estado_previo)


def validar_transicion(
    origen: Estado, destino: Estado, *, estado_previo: Estado | None = None
) -> None:
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
        permitidas = sorted(
            str(e) for e in transiciones_permitidas(origen, estado_previo=estado_previo)
        )
        raise TransicionInvalidaError(
            f"Transicion no permitida de {origen} a {destino}.",
            {
                "origen": str(origen),
                "codigo_origen": codigo_de(origen),
                "destino": str(destino),
                "codigo_destino": codigo_de(destino),
                "permitidas": permitidas,
            },
        )


def requiere_autorizacion_despachador(
    origen: Estado, destino: Estado | None = None
) -> bool:
    """Operaciones que el mensajero no puede decidir por su cuenta.

    Son dos: reanudar un envio detenido por una incidencia -el conductor
    reporta el incidente, otro rol autoriza continuar- y cerrarlo por devolucion
    o cancelacion, que tienen efecto comercial sobre el cliente.
    """
    if Estado(origen) is Estado.INCIDENCIA:
        return True
    if destino is not None and Estado(destino) in ESTADOS_QUE_EXIGEN_DESPACHADOR:
        return True
    return False
