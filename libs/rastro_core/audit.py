"""Bitacora de auditoria encadenada por funciones hash (REQ-08).

Cada registro almacena el resultado de aplicar SHA-256 a la concatenacion del
hash anterior con el contenido actual. Modificar o eliminar un registro rompe la
verificacion de todos los posteriores, de modo que la alteracion es detectable
(Haber y Stornetta, 1991; Schneier y Kelsey, 1999).

La estructura de cada entrada es la cuadrupla que Kent y Souppaya (2006) fijan
como minimo de un registro util: quien, que accion, sobre que recurso y cuando.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Iterable

from .ids import marca_tiempo

#: Valor del hash previo del primer registro de cada organizacion.
HASH_GENESIS = "0" * 64


class Resultado(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ERROR = "ERROR"


#: Campos que entran en el calculo del hash. El orden es fijo y forma parte del
#: procedimiento de verificacion: cambiarlo invalida las cadenas existentes.
CAMPOS_FIRMADOS: tuple[str, ...] = (
    "org_id",
    "seq",
    "ts",
    "actor_sub",
    "actor_email",
    "actor_grupos",
    "accion",
    "recurso",
    "resultado",
    "detalle",
)


def contenido_canonico(registro: dict[str, Any]) -> str:
    """Serializacion determinista de los campos firmados.

    Se usa JSON con claves ordenadas, separadores sin espacios y sin escapar
    caracteres no ASCII, de modo que dos implementaciones distintas del
    verificador obtengan la misma cadena.
    """
    datos = {}
    for campo in CAMPOS_FIRMADOS:
        valor = registro.get(campo)
        if campo == "actor_grupos" and valor is not None:
            valor = sorted(str(g) for g in valor)
        datos[campo] = valor
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calcular_hash(hash_previo: str, registro: dict[str, Any]) -> str:
    material = f"{hash_previo}{contenido_canonico(registro)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def construir_registro(
    *,
    org_id: str,
    seq: int,
    actor_sub: str,
    actor_email: str,
    actor_grupos: Iterable[str],
    accion: str,
    recurso: str,
    resultado: Resultado | str,
    detalle: dict[str, Any] | None = None,
    hash_previo: str,
    ts: str | None = None,
) -> dict[str, Any]:
    """Arma una entrada completa de bitacora con su hash ya calculado."""
    registro: dict[str, Any] = {
        "org_id": org_id,
        "seq": int(seq),
        "ts": ts or marca_tiempo(),
        "actor_sub": actor_sub,
        "actor_email": actor_email or "",
        "actor_grupos": sorted(str(g) for g in (actor_grupos or ())),
        "accion": str(accion),
        "recurso": str(recurso),
        "resultado": str(Resultado(resultado)),
        "detalle": detalle or {},
    }
    registro["hash_previo"] = hash_previo
    registro["hash"] = calcular_hash(hash_previo, registro)
    return registro


class ResultadoVerificacion(dict):
    """Salida del verificador de la cadena.

    Se comporta como diccionario para poder serializarse tal cual en un papel de
    trabajo de Cotejo, y expone ``cadena_valida`` para lectura directa.
    """

    @property
    def cadena_valida(self) -> bool:
        return bool(self["cadena_valida"])


def verificar_cadena(registros: list[dict[str, Any]]) -> ResultadoVerificacion:
    """Recalcula la cadena y devuelve el punto exacto de ruptura, si lo hay.

    Detecta tres formas de alteracion: modificacion del contenido de un
    registro, sustitucion del hash almacenado y eliminacion de un registro
    intermedio (que aparece como salto en la secuencia).
    """
    ordenados = sorted(registros, key=lambda r: int(r.get("seq", 0)))
    esperado_previo = HASH_GENESIS
    seq_esperada = 1
    rupturas: list[dict[str, Any]] = []

    for registro in ordenados:
        seq = int(registro.get("seq", 0))

        if seq != seq_esperada:
            rupturas.append(
                {
                    "tipo": "SECUENCIA_INCOMPLETA",
                    "seq_esperada": seq_esperada,
                    "seq_encontrada": seq,
                    "descripcion": "Falta al menos un registro intermedio en la cadena.",
                }
            )
            seq_esperada = seq

        if registro.get("hash_previo") != esperado_previo:
            rupturas.append(
                {
                    "tipo": "ENCADENAMIENTO_ROTO",
                    "seq": seq,
                    "hash_previo_almacenado": registro.get("hash_previo"),
                    "hash_previo_esperado": esperado_previo,
                    "descripcion": "El registro no enlaza con el hash del anterior.",
                }
            )

        recalculado = calcular_hash(registro.get("hash_previo", ""), registro)
        if recalculado != registro.get("hash"):
            rupturas.append(
                {
                    "tipo": "CONTENIDO_ALTERADO",
                    "seq": seq,
                    "hash_almacenado": registro.get("hash"),
                    "hash_recalculado": recalculado,
                    "descripcion": "El contenido del registro no corresponde a su hash.",
                }
            )

        esperado_previo = registro.get("hash", "")
        seq_esperada = seq + 1

    return ResultadoVerificacion(
        {
            "cadena_valida": not rupturas,
            "registros_verificados": len(ordenados),
            "primera_seq": int(ordenados[0]["seq"]) if ordenados else None,
            "ultima_seq": int(ordenados[-1]["seq"]) if ordenados else None,
            "hash_final": esperado_previo if ordenados else HASH_GENESIS,
            "rupturas": rupturas,
            "punto_de_ruptura": rupturas[0] if rupturas else None,
            "verificado_en": marca_tiempo(),
        }
    )
