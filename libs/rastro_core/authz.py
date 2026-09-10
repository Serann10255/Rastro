"""Matriz de autorizacion por grupo (REQ-07).

Cuatro grupos de usuarios y una decision explicita por operacion. Toda decision
-permitida o rechazada- se registra en la bitacora, porque el requisito exige
constancia tanto de las operaciones permitidas como de las rechazadas.
"""

from __future__ import annotations

from enum import StrEnum


class Grupo(StrEnum):
    ADMINISTRADOR = "administrador"
    DESPACHADOR = "despachador"
    CONDUCTOR = "conductor"
    AUDITOR = "auditor"


class Operacion(StrEnum):
    ENVIO_CREAR = "envio:crear"
    ENVIO_ASIGNAR = "envio:asignar"
    ENVIO_LISTAR = "envio:listar"
    ENVIO_CONSULTAR = "envio:consultar"
    EVENTO_REGISTRAR = "evento:registrar"
    EVENTO_REANUDAR = "evento:reanudar"
    EVIDENCIA_CARGAR = "evidencia:cargar"
    EVIDENCIA_DESCARGAR = "evidencia:descargar"
    BITACORA_CONSULTAR = "bitacora:consultar"
    BITACORA_VERIFICAR = "bitacora:verificar"


#: Grupos autorizados por operacion. Lo que no aparece, se rechaza.
MATRIZ: dict[Operacion, frozenset[Grupo]] = {
    Operacion.ENVIO_CREAR: frozenset({Grupo.ADMINISTRADOR, Grupo.DESPACHADOR}),
    Operacion.ENVIO_ASIGNAR: frozenset({Grupo.ADMINISTRADOR, Grupo.DESPACHADOR}),
    Operacion.ENVIO_LISTAR: frozenset({Grupo.ADMINISTRADOR, Grupo.DESPACHADOR, Grupo.CONDUCTOR}),
    Operacion.ENVIO_CONSULTAR: frozenset(
        {Grupo.ADMINISTRADOR, Grupo.DESPACHADOR, Grupo.CONDUCTOR, Grupo.AUDITOR}
    ),
    Operacion.EVENTO_REGISTRAR: frozenset({Grupo.CONDUCTOR, Grupo.DESPACHADOR}),
    Operacion.EVENTO_REANUDAR: frozenset({Grupo.DESPACHADOR, Grupo.ADMINISTRADOR}),
    Operacion.EVIDENCIA_CARGAR: frozenset({Grupo.CONDUCTOR}),
    Operacion.EVIDENCIA_DESCARGAR: frozenset({Grupo.ADMINISTRADOR, Grupo.DESPACHADOR, Grupo.AUDITOR}),
    Operacion.BITACORA_CONSULTAR: frozenset({Grupo.AUDITOR}),
    Operacion.BITACORA_VERIFICAR: frozenset({Grupo.AUDITOR}),
}

#: El auditor consulta y no modifica. Ninguna operacion de escritura lo incluye.
GRUPOS_SOLO_LECTURA: frozenset[Grupo] = frozenset({Grupo.AUDITOR})

#: El conductor solo alcanza los envios que tiene asignados.
OPERACIONES_RESTRINGIDAS_A_ENVIOS_PROPIOS: frozenset[Operacion] = frozenset(
    {Operacion.EVENTO_REGISTRAR, Operacion.EVIDENCIA_CARGAR, Operacion.ENVIO_LISTAR}
)


def normalizar_grupos(grupos) -> frozenset[Grupo]:
    """Convierte la lista de grupos del token; descarta los desconocidos."""
    conocidos = set()
    for nombre in grupos or ():
        try:
            conocidos.add(Grupo(str(nombre).strip().lower()))
        except ValueError:
            continue
    return frozenset(conocidos)


def esta_autorizado(grupos, operacion: Operacion) -> bool:
    permitidos = MATRIZ.get(Operacion(operacion), frozenset())
    return bool(normalizar_grupos(grupos) & permitidos)


def exige_envio_propio(grupos, operacion: Operacion) -> bool:
    """Indica si, ademas del grupo, hay que comprobar la asignacion del envio."""
    grupos = normalizar_grupos(grupos)
    if Operacion(operacion) not in OPERACIONES_RESTRINGIDAS_A_ENVIOS_PROPIOS:
        return False
    if grupos & {Grupo.ADMINISTRADOR, Grupo.DESPACHADOR}:
        return False
    return Grupo.CONDUCTOR in grupos
