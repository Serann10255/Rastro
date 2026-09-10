"""Autorizacion por rol (REQ-07).

Una decision explicita por operacion, y constancia en la bitacora tanto de lo
permitido como de lo rechazado, porque el requisito exige las dos cosas.

Que hay en el codigo y que en la base de datos
----------------------------------------------

**El catalogo de operaciones vive aqui y solo aqui.** Es la lista cerrada de lo
que el sistema sabe hacer, y ninguna organizacion puede ampliarla: un rol se
compone eligiendo de esta lista, nunca inventando permisos. Esa es la propiedad
que hace que abrir la configuracion de roles no sea abrir la puerta.

**La composicion de cada rol puede vivir en la tabla de la organizacion.** Una
empresa puede necesitar un coordinador con mas alcance que un despachador y
menos que un administrador, y eso es una decision suya, no del programa.

Las definiciones de abajo son el suelo: lo que aplica cuando la organizacion no
ha configurado nada, y el punto de partida que se aprovisiona a cada empresa.

Dos reglas que no se pueden desactivar desde ninguna pantalla:

1. **El administrador siempre tiene todas las operaciones.** Se resuelve aqui y
   no se lee de la tabla, de modo que ninguna edicion -ni un error, ni un
   descuido- puede dejar a una organizacion sin nadie que la administre.
2. **Un rol solo puede contener operaciones de este catalogo.** Lo que no este
   aqui no existe, aunque alguien lo escriba en la tabla.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Grupo(StrEnum):
    """Los roles que el sistema trae de fabrica.

    No son los unicos posibles: una organizacion puede crear los suyos. Estos
    son los que el sistema conoce por su nombre porque alguna regla los
    menciona -el conductor y sus envios propios, el auditor y su independencia-.
    """

    ADMINISTRADOR = "administrador"
    COORDINADOR = "coordinador"
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

    # Datos maestros y administracion de la organizacion.
    USUARIO_LISTAR = "usuario:listar"
    USUARIO_CREAR = "usuario:crear"
    USUARIO_EDITAR = "usuario:editar"
    MAESTRO_CONSULTAR = "maestro:consultar"
    MAESTRO_EDITAR = "maestro:editar"
    TABLERO_CONSULTAR = "tablero:consultar"
    EQUIPO_CONSULTAR = "equipo:consultar"
    ROL_CONSULTAR = "rol:consultar"
    ROL_ADMINISTRAR = "rol:administrar"


#: Como se agrupan las operaciones al presentarlas. Es informacion de interfaz y
#: vive aqui para que una operacion nueva no pueda quedarse sin sitio: la
#: pantalla recorre este mapa, no una lista suya.
AREAS: dict[str, tuple[str, tuple[Operacion, ...]]] = {
    "envios": (
        "Envios",
        (
            Operacion.ENVIO_CREAR,
            Operacion.ENVIO_ASIGNAR,
            Operacion.ENVIO_LISTAR,
            Operacion.ENVIO_CONSULTAR,
        ),
    ),
    "operacion": (
        "Operacion en calle",
        (
            Operacion.EVENTO_REGISTRAR,
            Operacion.EVENTO_REANUDAR,
            Operacion.EVIDENCIA_CARGAR,
            Operacion.EVIDENCIA_DESCARGAR,
        ),
    ),
    "administracion": (
        "Administracion",
        (
            Operacion.USUARIO_LISTAR,
            Operacion.USUARIO_CREAR,
            Operacion.USUARIO_EDITAR,
            Operacion.ROL_CONSULTAR,
            Operacion.ROL_ADMINISTRAR,
            Operacion.EQUIPO_CONSULTAR,
        ),
    ),
    "maestros": (
        "Datos maestros",
        (Operacion.MAESTRO_CONSULTAR, Operacion.MAESTRO_EDITAR, Operacion.TABLERO_CONSULTAR),
    ),
    "auditoria": (
        "Auditoria",
        (Operacion.BITACORA_CONSULTAR, Operacion.BITACORA_VERIFICAR),
    ),
}

#: Que hace cada operacion, en una linea. Lo lee la pantalla de roles: marcar
#: casillas llamadas `evento:reanudar` sin saber que significan es como firmar
#: sin leer.
DESCRIPCIONES: dict[Operacion, str] = {
    Operacion.ENVIO_CREAR: "Registrar envios, individuales o en lote",
    Operacion.ENVIO_ASIGNAR: "Asignar un mensajero y ver los envios de toda la empresa",
    Operacion.ENVIO_LISTAR: "Ver el listado de envios",
    Operacion.ENVIO_CONSULTAR: "Abrir un envio y su historico",
    Operacion.EVENTO_REGISTRAR: "Marcar el avance: recogido, en transito, entregado, incidencia",
    Operacion.EVENTO_REANUDAR: "Autorizar la continuacion de un envio detenido por incidencia",
    Operacion.EVIDENCIA_CARGAR: "Adjuntar la prueba de entrega",
    Operacion.EVIDENCIA_DESCARGAR: "Consultar las evidencias cargadas",
    Operacion.BITACORA_CONSULTAR: "Leer el registro encadenado de toda la actividad",
    Operacion.BITACORA_VERIFICAR: "Recalcular la cadena y detectar alteraciones",
    Operacion.USUARIO_LISTAR: "Ver las cuentas de la organizacion",
    Operacion.USUARIO_CREAR: "Crear cuentas",
    Operacion.USUARIO_EDITAR: "Cambiar rol, datos o estado de una cuenta",
    Operacion.MAESTRO_CONSULTAR: "Ver tiendas, clientes y transportistas",
    Operacion.MAESTRO_EDITAR: "Crear y modificar tiendas, clientes y transportistas",
    Operacion.TABLERO_CONSULTAR: "Ver el tablero de indicadores",
    Operacion.EQUIPO_CONSULTAR: "Ver los mensajeros disponibles para asignar",
    Operacion.ROL_CONSULTAR: "Ver los roles de la organizacion y sus permisos",
    Operacion.ROL_ADMINISTRAR: "Crear roles y cambiar que puede hacer cada uno",
}


@dataclass(frozen=True)
class DefinicionRol:
    clave: str
    nombre: str
    descripcion: str
    operaciones: frozenset[Operacion]
    #: De fabrica. No se puede borrar, pero si ajustar -salvo el administrador-.
    integrado: bool = True
    #: El administrador no se edita: es el seguro contra quedarse sin acceso.
    editable: bool = True


_TODAS = frozenset(Operacion)

#: Todo menos la bitacora. El administrador opera; el auditor revisa lo que se
#: opero, incluido lo que hizo el administrador. Si el mismo rol pudiera operar
#: y leer el registro de sus operaciones, la separacion de funciones que este
#: sistema promete dejaria de existir -y es justamente el control C-05 que el
#: programa de auditoria comprueba-. No es configurable: ningun rol puede
#: combinar la lectura de la bitacora con operaciones de escritura, y ninguna
#: cuenta puede sumar dos roles que juntos lo hagan.
_SIN_BITACORA = _TODAS - {Operacion.BITACORA_CONSULTAR, Operacion.BITACORA_VERIFICAR}

ROLES_INTEGRADOS: dict[str, DefinicionRol] = {
    Grupo.ADMINISTRADOR: DefinicionRol(
        clave=Grupo.ADMINISTRADOR,
        nombre="Administrador",
        descripcion="Responsable de la operacion y de las cuentas. Puede hacer todo lo "
        "que el sistema hace, salvo leer la bitacora: eso corresponde al auditor.",
        operaciones=_SIN_BITACORA,
        editable=False,
    ),
    Grupo.COORDINADOR: DefinicionRol(
        clave=Grupo.COORDINADOR,
        nombre="Coordinador",
        descripcion="Coordina la operacion diaria: despacha, autoriza envios detenidos "
        "y mantiene los catalogos. No administra cuentas ni roles.",
        operaciones=frozenset(
            {
                Operacion.ENVIO_CREAR,
                Operacion.ENVIO_ASIGNAR,
                Operacion.ENVIO_LISTAR,
                Operacion.ENVIO_CONSULTAR,
                Operacion.EVENTO_REGISTRAR,
                Operacion.EVENTO_REANUDAR,
                Operacion.EVIDENCIA_DESCARGAR,
                Operacion.MAESTRO_CONSULTAR,
                Operacion.MAESTRO_EDITAR,
                Operacion.TABLERO_CONSULTAR,
                Operacion.EQUIPO_CONSULTAR,
                Operacion.USUARIO_LISTAR,
            }
        ),
    ),
    Grupo.DESPACHADOR: DefinicionRol(
        clave=Grupo.DESPACHADOR,
        nombre="Despachador",
        descripcion="Despacha: registra envios, los asigna y sigue su avance. No "
        "autoriza envios detenidos ni toca cuentas ni catalogos.",
        operaciones=frozenset(
            {
                Operacion.ENVIO_CREAR,
                Operacion.ENVIO_ASIGNAR,
                Operacion.ENVIO_LISTAR,
                Operacion.ENVIO_CONSULTAR,
                Operacion.EVENTO_REGISTRAR,
                Operacion.EVIDENCIA_DESCARGAR,
                Operacion.MAESTRO_CONSULTAR,
                Operacion.TABLERO_CONSULTAR,
                Operacion.EQUIPO_CONSULTAR,
            }
        ),
    ),
    Grupo.CONDUCTOR: DefinicionRol(
        clave=Grupo.CONDUCTOR,
        nombre="Conductor",
        descripcion="Reparte: ve sus envios, marca el avance y adjunta la prueba de "
        "entrega. Reporta la incidencia; autorizarla corresponde a otro rol.",
        operaciones=frozenset(
            {
                Operacion.ENVIO_LISTAR,
                Operacion.ENVIO_CONSULTAR,
                Operacion.EVENTO_REGISTRAR,
                Operacion.EVIDENCIA_CARGAR,
                Operacion.MAESTRO_CONSULTAR,
                Operacion.TABLERO_CONSULTAR,
            }
        ),
    ),
    Grupo.AUDITOR: DefinicionRol(
        clave=Grupo.AUDITOR,
        nombre="Auditor",
        descripcion="Revisa y no modifica. Es el unico que lee la bitacora y verifica "
        "su integridad; ninguna operacion de escritura lo incluye.",
        operaciones=frozenset(
            {
                Operacion.ENVIO_CONSULTAR,
                Operacion.EVIDENCIA_DESCARGAR,
                Operacion.BITACORA_CONSULTAR,
                Operacion.BITACORA_VERIFICAR,
                Operacion.USUARIO_LISTAR,
                Operacion.ROL_CONSULTAR,
                Operacion.MAESTRO_CONSULTAR,
                Operacion.TABLERO_CONSULTAR,
            }
        ),
    ),
}

#: Grupos autorizados por operacion. Se deriva de las definiciones para que no
#: existan dos fuentes: antes era la fuente y ahora es la vista.
MATRIZ: dict[Operacion, frozenset[str]] = {
    operacion: frozenset(
        rol.clave for rol in ROLES_INTEGRADOS.values() if operacion in rol.operaciones
    )
    for operacion in Operacion
}

#: El auditor consulta y no modifica. Ninguna operacion de escritura lo incluye.
GRUPOS_SOLO_LECTURA: frozenset[str] = frozenset({Grupo.AUDITOR})

#: Operaciones que solo alcanzan los envios propios cuando quien las pide no ve
#: la operacion completa.
OPERACIONES_RESTRINGIDAS_A_ENVIOS_PROPIOS: frozenset[Operacion] = frozenset(
    {Operacion.EVENTO_REGISTRAR, Operacion.EVIDENCIA_CARGAR, Operacion.ENVIO_LISTAR}
)

#: Operaciones de escritura. Se usan para avisar cuando un rol las combina con
#: la lectura de la bitacora, que es lo que rompe la separacion de funciones.
OPERACIONES_DE_ESCRITURA: frozenset[Operacion] = frozenset(
    {
        Operacion.ENVIO_CREAR,
        Operacion.ENVIO_ASIGNAR,
        Operacion.EVENTO_REGISTRAR,
        Operacion.EVENTO_REANUDAR,
        Operacion.EVIDENCIA_CARGAR,
        Operacion.USUARIO_CREAR,
        Operacion.USUARIO_EDITAR,
        Operacion.MAESTRO_EDITAR,
        Operacion.ROL_ADMINISTRAR,
    }
)


def normalizar_grupos(grupos) -> frozenset[str]:
    """Normaliza los nombres de rol del token.

    Ya no descarta los desconocidos: un rol que este programa no trae de fabrica
    puede ser perfectamente valido si la organizacion lo creo. Lo que decide si
    un rol otorga algo no es que aparezca aqui, sino que exista con operaciones.
    """
    return frozenset(
        str(nombre).strip().lower() for nombre in (grupos or ()) if str(nombre).strip()
    )


def union_de_roles(
    grupos, definiciones: dict[str, DefinicionRol] | None = None
) -> frozenset[Operacion]:
    """La suma de lo que declaran estos roles, sin el atajo del administrador.

    ``operaciones_de`` resuelve el administrador de golpe -siempre lo tiene
    todo- y por eso no sirve para comprobar la separacion de funciones: la suma
    de «administrador + auditor» daria las del administrador y la bitacora
    desapareceria del calculo, que es justo lo que habria que detectar.
    """
    catalogo = definiciones or ROLES_INTEGRADOS
    concedidas: set[Operacion] = set()
    for nombre in normalizar_grupos(grupos):
        definicion = catalogo.get(nombre) or ROLES_INTEGRADOS.get(nombre)
        if definicion:
            concedidas |= definicion.operaciones
    return frozenset(concedidas)


def operaciones_de(
    grupos, definiciones: dict[str, DefinicionRol] | None = None
) -> frozenset[Operacion]:
    """Las operaciones que otorgan estos roles, juntas.

    ``definiciones`` son los roles de la organizacion. Sin ellas se aplican las
    de fabrica, que es lo que ocurre en una instalacion que todavia no ha
    configurado nada y en los servicios que no alcanzan la tabla de maestros.
    """
    catalogo = definiciones or ROLES_INTEGRADOS
    nombres = normalizar_grupos(grupos)

    # El administrador se resuelve aqui y no en la tabla: es el seguro contra
    # que una edicion deje a la organizacion sin nadie que pueda entrar a
    # deshacerla.
    if Grupo.ADMINISTRADOR in nombres:
        return ROLES_INTEGRADOS[Grupo.ADMINISTRADOR].operaciones

    return union_de_roles(nombres, catalogo)


def esta_autorizado(
    grupos, operacion: Operacion, definiciones: dict[str, DefinicionRol] | None = None
) -> bool:
    return Operacion(operacion) in operaciones_de(grupos, definiciones)


def exige_envio_propio(
    grupos, operacion: Operacion, definiciones: dict[str, DefinicionRol] | None = None
) -> bool:
    """Indica si, ademas del rol, hay que comprobar la asignacion del envio.

    El criterio es el permiso y no el nombre del rol: quien puede asignar ve la
    operacion completa, y quien no, solo lo suyo. Asi la regla sigue valiendo
    para un rol que la organizacion invente manana.
    """
    if Operacion(operacion) not in OPERACIONES_RESTRINGIDAS_A_ENVIOS_PROPIOS:
        return False
    concedidas = operaciones_de(grupos, definiciones)
    if Operacion.ENVIO_ASIGNAR in concedidas:
        return False
    return Operacion(operacion) in concedidas


def catalogo_de_operaciones() -> list[dict]:
    """El catalogo completo, agrupado y con descripciones, para la pantalla de roles."""
    return [
        {
            "area": clave,
            "nombre": nombre,
            "operaciones": [
                {
                    "operacion": str(operacion),
                    "descripcion": DESCRIPCIONES[operacion],
                    "escritura": operacion in OPERACIONES_DE_ESCRITURA,
                }
                for operacion in operaciones
            ],
        }
        for clave, (nombre, operaciones) in AREAS.items()
    ]


def vista_rol(definicion: DefinicionRol) -> dict:
    return {
        "clave": definicion.clave,
        "nombre": definicion.nombre,
        "descripcion": definicion.descripcion,
        "operaciones": sorted(str(o) for o in definicion.operaciones),
        "integrado": definicion.integrado,
        "editable": definicion.editable,
    }


def rompe_separacion_de_funciones(operaciones) -> bool:
    """Si un rol lee la bitacora y ademas escribe en el sistema.

    No se prohibe -es la organizacion quien decide como se reparte el trabajo-
    pero se avisa: quien opera y ademas revisa el registro de lo que opero puede
    revisar su propio rastro, y eso vacia de sentido el control.
    """
    conjunto = {Operacion(o) for o in operaciones}
    lee_bitacora = bool(conjunto & {Operacion.BITACORA_CONSULTAR, Operacion.BITACORA_VERIFICAR})
    return lee_bitacora and bool(conjunto & OPERACIONES_DE_ESCRITURA)
