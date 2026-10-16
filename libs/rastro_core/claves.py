"""Construccion de claves del modelo de datos.

Es el unico lugar donde se arma una clave. Toda funcion exige el identificador
de organizacion y falla si no lo recibe, de modo que sea imposible construir por
descuido una consulta sin filtrar (riesgo R-05: una sola consulta sin ese filtro
basta para exponer los datos de una empresa a otra).
"""

from __future__ import annotations

from .errors import ValidacionError

#: Ancho fijo de la secuencia de bitacora: conserva el orden lexicografico.
ANCHO_SECUENCIA = 12

SK_MAESTRO = "META"
PREFIJO_EVENTO = "EVT#"
PREFIJO_POSICION = "POS#"
SK_RUTA_ACTIVA = "RUTA_ACTIVA"


def _exigir_org(org_id: str) -> str:
    org_id = (org_id or "").strip()
    if not org_id:
        raise ValidacionError(
            "Toda clave exige identificador de organizacion; la peticion no puede resolverse."
        )
    if "#" in org_id:
        raise ValidacionError("El identificador de organizacion no admite el caracter '#'.")
    return org_id


def _exigir_envio(envio_id: str) -> str:
    envio_id = (envio_id or "").strip()
    if not envio_id:
        raise ValidacionError("Falta el identificador de envio.")
    if "#" in envio_id:
        raise ValidacionError("El identificador de envio no admite el caracter '#'.")
    return envio_id


def pk_envio(org_id: str, envio_id: str) -> str:
    return f"ORG#{_exigir_org(org_id)}#ENV#{_exigir_envio(envio_id)}"


def sk_evento(ts: str, evento_id: str) -> str:
    return f"{PREFIJO_EVENTO}{ts}#{evento_id}"


def gsi_org_pk(org_id: str) -> str:
    return f"ORG#{_exigir_org(org_id)}"


def gsi_org_sk(creado_en: str, envio_id: str) -> str:
    return f"ENV#{creado_en}#{_exigir_envio(envio_id)}"


def gsi_publico_pk(envio_id: str) -> str:
    """Indice del punto de consulta publico (REQ-04).

    El destinatario solo dispone del identificador del envio, no de la
    organizacion. Este indice permite resolverlo sin abrir las particiones
    autenticadas: la vista que devuelve el servicio publico es reducida y no
    expone datos de operacion.
    """
    return f"ENV#{_exigir_envio(envio_id)}"


def _exigir_tramo(valor: str, nombre: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise ValidacionError(f"Falta el identificador de {nombre}.")
    if "#" in valor:
        raise ValidacionError(f"El identificador de {nombre} no admite el caracter '#'.")
    return valor


# -- Rutas de entrega -------------------------------------------------------- #
#
# Viven en la tabla de envios porque son operacion, no catalogo: crecen con el
# trabajo diario igual que los eventos. Usan su propia particion del indice por
# organizacion (``ORG#<org>#RUTAS``) para no aparecer nunca en el listado de
# envios, que consulta ``ORG#<org>`` sin filtrar por tipo.


def pk_ruta(org_id: str, ruta_id: str) -> str:
    return f"ORG#{_exigir_org(org_id)}#RUTA#{_exigir_tramo(ruta_id, 'ruta')}"


def sk_posicion(capturada_en: str, sufijo: str) -> str:
    return f"{PREFIJO_POSICION}{capturada_en}#{sufijo}"


def gsi_rutas_pk(org_id: str) -> str:
    return f"ORG#{_exigir_org(org_id)}#RUTAS"


def gsi_rutas_sk(iniciada_en: str, ruta_id: str) -> str:
    return f"RUTA#{iniciada_en}#{_exigir_tramo(ruta_id, 'ruta')}"


def pk_conductor(org_id: str, conductor_sub: str) -> str:
    """Particion del conductor. Guarda el testigo de su ruta activa.

    El testigo es lo que garantiza que un conductor tenga una sola ruta abierta:
    se escribe con una condicion de no existencia, de modo que dos inicios
    simultaneos -un doble toque en el boton- no pueden ganar los dos.
    """
    return f"ORG#{_exigir_org(org_id)}#CONDUCTOR#{_exigir_tramo(conductor_sub, 'conductor')}"


def pk_bitacora(org_id: str) -> str:
    return f"ORG#{_exigir_org(org_id)}"


def sk_bitacora(seq: int) -> str:
    return f"SEQ#{int(seq):0{ANCHO_SECUENCIA}d}"
