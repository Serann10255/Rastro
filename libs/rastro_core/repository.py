"""Acceso a datos. Unico punto donde se leen y escriben envios y bitacora.

Ningun microservicio construye consultas por su cuenta: todos pasan por esta
capa, que recibe el identificador de organizacion desde el token y lo aplica sin
excepcion. Es la mitigacion del riesgo R-05 y la razon de que el aislamiento
entre organizaciones no sea una funcion adicional sino una propiedad del acceso
a datos.

Hay dos implementaciones con la misma interfaz publica: ``RepositorioDynamo``,
que opera contra DynamoDB (local o AWS), y ``RepositorioMemoria``, que sostiene
las pruebas unitarias sin infraestructura. Ambas comparten la construccion de
claves de ``claves.py``, de modo que el control de aislamiento se implementa una
sola vez.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol

from . import claves
from .audit import HASH_GENESIS, Resultado, construir_registro, verificar_cadena
from .config import Config, cargar_config
from .errors import ConflictoError, NoEncontradoError
from .ids import marca_tiempo, nuevo_id_evento

MAX_REINTENTOS_BITACORA = 8


# --------------------------------------------------------------------------- #
# Interfaz
# --------------------------------------------------------------------------- #


class Repositorio(Protocol):
    def guardar_envio(self, envio: dict) -> dict: ...
    def obtener_envio(self, org_id: str, envio_id: str) -> dict: ...
    def actualizar_envio(self, envio: dict) -> dict: ...
    def listar_envios(self, org_id: str, limite: int = 50) -> list[dict]: ...
    def agregar_evento(self, evento: dict) -> dict: ...
    def listar_eventos(self, org_id: str, envio_id: str) -> list[dict]: ...
    def historico_publico(self, envio_id: str) -> tuple[dict | None, list[dict]]: ...
    def registrar_bitacora(self, **kwargs) -> dict: ...
    def listar_bitacora(self, org_id: str, limite: int = 500) -> list[dict]: ...
    def verificar_bitacora(self, org_id: str) -> dict: ...


# --------------------------------------------------------------------------- #
# Implementacion en memoria (pruebas unitarias)
# --------------------------------------------------------------------------- #


class RepositorioMemoria:
    """Replica el comportamiento de las claves sin requerir infraestructura."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict] = {}
        self._bitacora: dict[tuple[str, str], dict] = {}
        self._lock = threading.RLock()

    # -- envios ------------------------------------------------------------ #

    def guardar_envio(self, envio: dict) -> dict:
        pk = claves.pk_envio(envio["org_id"], envio["envio_id"])
        with self._lock:
            if (pk, claves.SK_MAESTRO) in self._items:
                raise ConflictoError("El envio ya existe.")
            self._items[(pk, claves.SK_MAESTRO)] = dict(envio)
        return envio

    def obtener_envio(self, org_id: str, envio_id: str) -> dict:
        pk = claves.pk_envio(org_id, envio_id)
        item = self._items.get((pk, claves.SK_MAESTRO))
        if item is None:
            raise NoEncontradoError("El envio no existe.", {"envio_id": envio_id})
        return dict(item)

    def actualizar_envio(self, envio: dict) -> dict:
        pk = claves.pk_envio(envio["org_id"], envio["envio_id"])
        with self._lock:
            if (pk, claves.SK_MAESTRO) not in self._items:
                raise NoEncontradoError("El envio no existe.")
            self._items[(pk, claves.SK_MAESTRO)] = dict(envio)
        return envio

    def listar_envios(self, org_id: str, limite: int = 50) -> list[dict]:
        prefijo = claves.gsi_org_pk(org_id) + "#ENV#"
        encontrados = [
            dict(v)
            for (pk, sk), v in self._items.items()
            if sk == claves.SK_MAESTRO and pk.startswith(prefijo)
        ]
        encontrados.sort(key=lambda e: e.get("creado_en", ""), reverse=True)
        return encontrados[:limite]

    # -- eventos ----------------------------------------------------------- #

    def agregar_evento(self, evento: dict) -> dict:
        pk = claves.pk_envio(evento["org_id"], evento["envio_id"])
        sk = claves.sk_evento(evento["ts"], evento["evento_id"])
        with self._lock:
            self._items[(pk, sk)] = dict(evento)
        return evento

    def listar_eventos(self, org_id: str, envio_id: str) -> list[dict]:
        pk = claves.pk_envio(org_id, envio_id)
        eventos = [
            dict(v)
            for (p, sk), v in self._items.items()
            if p == pk and sk.startswith(claves.PREFIJO_EVENTO)
        ]
        eventos.sort(key=lambda e: (e.get("ts", ""), e.get("evento_id", "")))
        return eventos

    def historico_publico(self, envio_id: str) -> tuple[dict | None, list[dict]]:
        maestro = None
        eventos = []
        for (_pk, sk), item in self._items.items():
            if item.get("envio_id") != envio_id:
                continue
            if sk == claves.SK_MAESTRO:
                maestro = dict(item)
            elif sk.startswith(claves.PREFIJO_EVENTO):
                eventos.append(dict(item))
        eventos.sort(key=lambda e: (e.get("ts", ""), e.get("evento_id", "")))
        return maestro, eventos

    # -- bitacora ---------------------------------------------------------- #

    def registrar_bitacora(self, **kwargs) -> dict:
        org_id = kwargs["org_id"]
        with self._lock:
            registros = self._registros_org(org_id)
            seq = (max((int(r["seq"]) for r in registros), default=0)) + 1
            previo = (
                max(registros, key=lambda r: int(r["seq"]))["hash"] if registros else HASH_GENESIS
            )
            registro = construir_registro(seq=seq, hash_previo=previo, **kwargs)
            self._bitacora[(claves.pk_bitacora(org_id), claves.sk_bitacora(seq))] = registro
        return registro

    def _registros_org(self, org_id: str) -> list[dict]:
        pk = claves.pk_bitacora(org_id)
        return [dict(v) for (p, _sk), v in self._bitacora.items() if p == pk]

    def listar_bitacora(self, org_id: str, limite: int = 500) -> list[dict]:
        registros = self._registros_org(org_id)
        registros.sort(key=lambda r: int(r["seq"]))
        return registros[:limite]

    def verificar_bitacora(self, org_id: str) -> dict:
        return verificar_cadena(self.listar_bitacora(org_id, limite=10_000))

    # -- utilidades de prueba ---------------------------------------------- #

    def alterar_registro_bitacora(self, org_id: str, seq: int, campo: str, valor: Any) -> None:
        """Alteracion controlada para la prueba de integridad (control C-08).

        No forma parte de la interfaz de dominio: existe para que las pruebas
        comprueben que el verificador detecta la manipulacion, que es la unica
        forma de demostrar que la prueba sirve para algo.
        """
        clave = (claves.pk_bitacora(org_id), claves.sk_bitacora(seq))
        if clave not in self._bitacora:
            raise NoEncontradoError("No existe ese registro de bitacora.")
        self._bitacora[clave][campo] = valor


# --------------------------------------------------------------------------- #
# Implementacion sobre DynamoDB
# --------------------------------------------------------------------------- #


class RepositorioDynamo:
    """Opera contra DynamoDB Local o contra el servicio en AWS, sin distincion."""

    def __init__(self, config: Config | None = None, recurso=None) -> None:
        self.config = config or cargar_config()
        if recurso is None:
            import boto3

            recurso = boto3.resource(
                "dynamodb",
                region_name=self.config.region,
                endpoint_url=self.config.endpoint_dynamodb,
            )
        self._envios = recurso.Table(self.config.tabla_envios)
        self._registro = recurso.Table(self.config.tabla_bitacora)

    # -- envios ------------------------------------------------------------ #

    def _item_maestro(self, envio: dict) -> dict:
        return {
            **_sin_nulos(envio),
            "pk": claves.pk_envio(envio["org_id"], envio["envio_id"]),
            "sk": claves.SK_MAESTRO,
            "gsi_org_pk": claves.gsi_org_pk(envio["org_id"]),
            "gsi_org_sk": claves.gsi_org_sk(envio["creado_en"], envio["envio_id"]),
            "gsi_pub_pk": claves.gsi_publico_pk(envio["envio_id"]),
            "gsi_pub_sk": claves.SK_MAESTRO,
        }

    def guardar_envio(self, envio: dict) -> dict:
        from botocore.exceptions import ClientError

        try:
            self._envios.put_item(
                Item=self._item_maestro(envio),
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConflictoError("El envio ya existe.") from exc
            raise
        return envio

    def obtener_envio(self, org_id: str, envio_id: str) -> dict:
        respuesta = self._envios.get_item(
            Key={"pk": claves.pk_envio(org_id, envio_id), "sk": claves.SK_MAESTRO}
        )
        item = respuesta.get("Item")
        if not item:
            raise NoEncontradoError("El envio no existe.", {"envio_id": envio_id})
        return _limpiar(item)

    def actualizar_envio(self, envio: dict) -> dict:
        from botocore.exceptions import ClientError

        try:
            self._envios.put_item(
                Item=self._item_maestro(envio),
                ConditionExpression="attribute_exists(pk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NoEncontradoError("El envio no existe.") from exc
            raise
        return envio

    def listar_envios(self, org_id: str, limite: int = 50) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        respuesta = self._envios.query(
            IndexName="gsi_org",
            KeyConditionExpression=Key("gsi_org_pk").eq(claves.gsi_org_pk(org_id)),
            ScanIndexForward=False,
            Limit=limite,
        )
        return [_limpiar(i) for i in respuesta.get("Items", [])]

    # -- eventos ----------------------------------------------------------- #

    def agregar_evento(self, evento: dict) -> dict:
        item = {
            **_sin_nulos(evento),
            "pk": claves.pk_envio(evento["org_id"], evento["envio_id"]),
            "sk": claves.sk_evento(evento["ts"], evento["evento_id"]),
            "gsi_pub_pk": claves.gsi_publico_pk(evento["envio_id"]),
            "gsi_pub_sk": claves.sk_evento(evento["ts"], evento["evento_id"]),
        }
        self._envios.put_item(Item=item)
        return evento

    def listar_eventos(self, org_id: str, envio_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        respuesta = self._envios.query(
            KeyConditionExpression=(
                Key("pk").eq(claves.pk_envio(org_id, envio_id))
                & Key("sk").begins_with(claves.PREFIJO_EVENTO)
            ),
            ScanIndexForward=True,
        )
        return [_limpiar(i) for i in respuesta.get("Items", [])]

    def historico_publico(self, envio_id: str) -> tuple[dict | None, list[dict]]:
        from boto3.dynamodb.conditions import Key

        respuesta = self._envios.query(
            IndexName="gsi_publico",
            KeyConditionExpression=Key("gsi_pub_pk").eq(claves.gsi_publico_pk(envio_id)),
            ScanIndexForward=True,
        )
        maestro, eventos = None, []
        for item in respuesta.get("Items", []):
            limpio = _limpiar(item)
            if item.get("sk") == claves.SK_MAESTRO:
                maestro = limpio
            else:
                eventos.append(limpio)
        eventos.sort(key=lambda e: (e.get("ts", ""), e.get("evento_id", "")))
        return maestro, eventos

    # -- bitacora ---------------------------------------------------------- #

    def registrar_bitacora(self, **kwargs) -> dict:
        """Escribe el siguiente eslabon de la cadena de la organizacion.

        El documento declara una limitacion conocida frente a escrituras
        concurrentes: dos operaciones simultaneas pueden leer el mismo hash
        previo. Aqui se acota con una escritura condicional sobre la unicidad de
        la secuencia y un reintento limitado, de modo que la segunda escritura
        no sobrescriba a la primera sino que recalcule su eslabon.
        """
        from botocore.exceptions import ClientError

        org_id = kwargs["org_id"]
        for intento in range(MAX_REINTENTOS_BITACORA):
            ultimo = self._ultimo_registro(org_id)
            seq = int(ultimo["seq"]) + 1 if ultimo else 1
            previo = ultimo["hash"] if ultimo else HASH_GENESIS
            registro = construir_registro(seq=seq, hash_previo=previo, **kwargs)
            try:
                self._registro.put_item(
                    Item={
                        **registro,
                        "pk": claves.pk_bitacora(org_id),
                        "sk": claves.sk_bitacora(seq),
                    },
                    ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
                )
                return registro
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
                if intento == MAX_REINTENTOS_BITACORA - 1:
                    raise ConflictoError(
                        "No se pudo encadenar el registro de bitacora tras varios intentos."
                    ) from exc
        raise ConflictoError("No se pudo encadenar el registro de bitacora.")

    def _ultimo_registro(self, org_id: str) -> dict | None:
        from boto3.dynamodb.conditions import Key

        respuesta = self._registro.query(
            KeyConditionExpression=Key("pk").eq(claves.pk_bitacora(org_id)),
            ScanIndexForward=False,
            Limit=1,
        )
        items = respuesta.get("Items", [])
        return _limpiar(items[0]) if items else None

    def listar_bitacora(self, org_id: str, limite: int = 500) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        registros: list[dict] = []
        argumentos: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(claves.pk_bitacora(org_id)),
            "ScanIndexForward": True,
        }
        while len(registros) < limite:
            respuesta = self._registro.query(**argumentos)
            registros.extend(_limpiar(i) for i in respuesta.get("Items", []))
            if "LastEvaluatedKey" not in respuesta:
                break
            argumentos["ExclusiveStartKey"] = respuesta["LastEvaluatedKey"]
        return registros[:limite]

    def verificar_bitacora(self, org_id: str) -> dict:
        return verificar_cadena(self.listar_bitacora(org_id, limite=10_000))


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

_CAMPOS_INTERNOS = {"pk", "sk", "gsi_org_pk", "gsi_org_sk", "gsi_pub_pk", "gsi_pub_sk"}


def _limpiar(item: dict) -> dict:
    """Quita las claves de almacenamiento y normaliza los numeros de DynamoDB."""
    return {c: _desde_dynamo(v) for c, v in item.items() if c not in _CAMPOS_INTERNOS}


def _desde_dynamo(valor: Any) -> Any:
    """Inversa de ``_a_dynamo``. Recorre estructuras anidadas.

    La conversion alcanza las coordenadas de un punto de control, que llegan
    anidadas dentro del evento y no en la raiz del item.
    """
    from decimal import Decimal

    if isinstance(valor, Decimal):
        return int(valor) if valor % 1 == 0 else float(valor)
    if isinstance(valor, dict):
        return {k: _desde_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_desde_dynamo(v) for v in valor]
    return valor


def _sin_nulos(datos: dict) -> dict:
    """DynamoDB admite nulos, pero conservarlos ensucia el item y el hash."""
    return {k: _a_dynamo(v) for k, v in datos.items() if v is not None}


def _a_dynamo(valor: Any) -> Any:
    """Convierte los numeros con decimales al tipo que DynamoDB acepta.

    El servicio no admite ``float``: rechaza la escritura. La conversion se hace
    desde la representacion en texto y no desde el binario, para que el valor
    almacenado sea el que el usuario vio y no su aproximacion binaria. Importa
    en las coordenadas de un punto de control, que son evidencia.
    """
    from decimal import Decimal

    if isinstance(valor, float):
        return Decimal(str(valor))
    if isinstance(valor, dict):
        return {k: _a_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_a_dynamo(v) for v in valor]
    return valor


def construir_repositorio(config: Config | None = None) -> Repositorio:
    """Devuelve la implementacion que corresponde a la configuracion vigente."""
    config = config or cargar_config()
    if config.entorno == "memoria":
        return RepositorioMemoria()
    return RepositorioDynamo(config)


__all__ = [
    "MAX_REINTENTOS_BITACORA",
    "Repositorio",
    "RepositorioDynamo",
    "RepositorioMemoria",
    "Resultado",
    "construir_repositorio",
    "marca_tiempo",
    "nuevo_id_evento",
]
