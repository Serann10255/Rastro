"""Prepara el entorno local: tablas, indices, contenedor y datos sinteticos.

Es el equivalente local de la secuencia de despliegue de AWS y comparte con ella
la misma definicion de tablas e indices, de modo que lo que se prueba en local
tiene la misma forma que lo desplegado. La secuencia es idempotente: puede
ejecutarse tantas veces como haga falta sin duplicar recursos ni datos.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config as ConfigBoto
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "libs"))

from rastro_core.config import cargar_config  # noqa: E402
from rastro_core.ids import marca_tiempo, nuevo_id_envio, nuevo_id_evento  # noqa: E402
from rastro_core.state_machine import Estado  # noqa: E402

CONFIG = cargar_config()
RAIZ = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Definicion de las tablas: la misma que usa el despliegue en AWS
# --------------------------------------------------------------------------- #


def definicion_tabla_envios(nombre: str) -> dict:
    """Tabla unica de envios y eventos.

    La clave de particion combina organizacion y envio, de modo que los datos de
    cada empresa quedan en particiones distintas. La clave de ordenamiento
    distingue el registro maestro de los eventos, fechados en formato ordenable,
    y asi el historico completo se obtiene con una sola consulta.
    """
    return {
        "TableName": nombre,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi_org_pk", "AttributeType": "S"},
            {"AttributeName": "gsi_org_sk", "AttributeType": "S"},
            {"AttributeName": "gsi_pub_pk", "AttributeType": "S"},
            {"AttributeName": "gsi_pub_sk", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "GlobalSecondaryIndexes": [
            {
                # Listado de envios de una organizacion, del mas reciente al
                # mas antiguo. Solo indexa registros maestros.
                "IndexName": "gsi_org",
                "KeySchema": [
                    {"AttributeName": "gsi_org_pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi_org_sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                # Consulta publica por identificador de envio (REQ-04): el
                # destinatario no conoce la organizacion, solo el identificador.
                "IndexName": "gsi_publico",
                "KeySchema": [
                    {"AttributeName": "gsi_pub_pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi_pub_sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    }


def definicion_tabla_bitacora(nombre: str) -> dict:
    """Bitacora encadenada, una cadena independiente por organizacion."""
    return {
        "TableName": nombre,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
    }


# --------------------------------------------------------------------------- #
# Aprovisionamiento
# --------------------------------------------------------------------------- #


def crear_tabla(cliente, definicion: dict) -> str:
    nombre = definicion["TableName"]
    try:
        cliente.create_table(**definicion)
        cliente.get_waiter("table_exists").wait(TableName=nombre)
        return f"tabla creada: {nombre}"
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"ResourceInUseException", "TableAlreadyExistsException"}:
            return f"tabla ya existente: {nombre}"
        raise


def crear_contenedor(cliente, nombre: str) -> list[str]:
    """Crea el contenedor y aplica los controles que el entorno local soporte.

    El equivalente local no implementa todas las operaciones de la interfaz del
    proveedor. Cuando falta una, se informa en lugar de simularla: un control
    que no se puede aplicar aqui es exactamente un control que este entorno no
    acredita, y esa distincion es lo que Cotejo verifica contra la cuenta real.
    """
    pasos = []
    try:
        cliente.create_bucket(Bucket=nombre)
        pasos.append(f"contenedor creado: {nombre}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
        pasos.append(f"contenedor ya existente: {nombre}")

    # Versionado: conserva versiones anteriores de cada evidencia (control C-04)
    # y hace detectable la sustitucion de una prueba de entrega.
    pasos.append(
        _aplicar_control(
            "versionado",
            cliente.put_bucket_versioning,
            Bucket=nombre,
            VersioningConfiguration={"Status": "Enabled"},
        )
    )

    # Bloqueo de acceso publico (control C-03). El almacenamiento local no
    # implementa esta operacion; en AWS la aplica deploy/aws/10-datos.sh.
    pasos.append(
        _aplicar_control(
            "bloqueo de acceso publico",
            cliente.put_public_access_block,
            Bucket=nombre,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    )
    return pasos


def _aplicar_control(nombre: str, operacion, **argumentos) -> str:
    try:
        operacion(**argumentos)
        return f"{nombre}: aplicado"
    except ClientError as exc:
        codigo = exc.response["Error"]["Code"]
        if codigo in {"MalformedXML", "NotImplemented", "MethodNotAllowed", "InvalidRequest"}:
            return f"{nombre}: NO disponible en el entorno local ({codigo}); se aplica solo en AWS"
        raise


# --------------------------------------------------------------------------- #
# Datos sinteticos
# --------------------------------------------------------------------------- #

ENVIOS_SEMILLA = [
    {
        "org_id": "org-andes",
        "creado_por": "u-andes-desp",
        "conductor_sub": "u-andes-cond-1",
        "conductor_nombre": "Carlos Nieto",
        "origen": {"linea": "Calle 100 #15-20", "ciudad": "Bogota", "referencia": "Oficina 402"},
        "destino": {"linea": "Carrera 7 #32-16", "ciudad": "Bogota", "referencia": "Piso 8"},
        "destinatario": {"nombre": "Laura Mejia Rios", "telefono": "3000000001"},
        "descripcion": "Sobre con documentos contractuales",
        "recorrido": [Estado.ASIGNADO, Estado.RECOLECTADO, Estado.EN_TRANSITO],
    },
    {
        "org_id": "org-andes",
        "creado_por": "u-andes-desp",
        "conductor_sub": "u-andes-cond-2",
        "conductor_nombre": "Camila Ortiz",
        "origen": {"linea": "Avenida 68 #40-11", "ciudad": "Bogota"},
        "destino": {"linea": "Calle 45 #13-05", "ciudad": "Bogota"},
        "destinatario": {"nombre": "Andres Pardo Leon", "telefono": "3000000002"},
        "descripcion": "Paquete liviano",
        "recorrido": [Estado.ASIGNADO],
    },
    {
        "org_id": "org-sabana",
        "creado_por": "u-sabana-desp",
        "conductor_sub": "u-sabana-cond",
        "conductor_nombre": "Santiago Bravo",
        "origen": {"linea": "Autopista Norte km 20", "ciudad": "Chia"},
        "destino": {"linea": "Calle 80 #90-10", "ciudad": "Bogota"},
        "destinatario": {"nombre": "Marcela Nino Cruz", "telefono": "3000000003"},
        "descripcion": "Caja de muestras",
        "recorrido": [Estado.ASIGNADO, Estado.RECOLECTADO],
    },
]


def sembrar_envios(recurso) -> list[str]:
    """Carga envios sinteticos con su historico, sin tocar la bitacora.

    La bitacora no se siembra a proposito: sus eslabones deben producirse como
    efecto de operaciones reales del sistema. Una cadena fabricada por el guion
    de preparacion no probaria nada.
    """
    from rastro_core.repository import RepositorioDynamo

    repositorio = RepositorioDynamo(CONFIG, recurso=recurso)
    creados = []

    for plantilla in ENVIOS_SEMILLA:
        ahora = marca_tiempo()
        envio_id = nuevo_id_envio()
        envio = {
            "envio_id": envio_id,
            "org_id": plantilla["org_id"],
            "estado": Estado.CREADO.value,
            "creado_en": ahora,
            "actualizado_en": ahora,
            "creado_por": plantilla["creado_por"],
            "origen": plantilla["origen"],
            "destino": plantilla["destino"],
            "destinatario": plantilla["destinatario"],
            "descripcion": plantilla["descripcion"],
            "evidencias": [],
        }
        repositorio.guardar_envio(envio)

        estado_anterior = Estado.CREADO
        _agregar_evento(repositorio, envio, Estado.CREADO, None, plantilla["creado_por"])

        for estado in plantilla["recorrido"]:
            if estado is Estado.ASIGNADO:
                envio["conductor_sub"] = plantilla["conductor_sub"]
                envio["conductor_nombre"] = plantilla["conductor_nombre"]
            actor = (
                plantilla["creado_por"] if estado is Estado.ASIGNADO else plantilla["conductor_sub"]
            )
            _agregar_evento(repositorio, envio, estado, estado_anterior, actor)
            estado_anterior = estado

        envio["estado"] = estado_anterior.value
        envio["actualizado_en"] = marca_tiempo()
        repositorio.actualizar_envio(envio)
        creados.append(envio_id)

    return creados


def _agregar_evento(repositorio, envio: dict, estado, estado_anterior, actor: str) -> None:
    repositorio.agregar_evento(
        {
            "evento_id": nuevo_id_evento(),
            "envio_id": envio["envio_id"],
            "org_id": envio["org_id"],
            "estado": estado.value,
            "estado_anterior": estado_anterior.value if estado_anterior else None,
            "ts": marca_tiempo(),
            "actor_sub": actor,
            "actor_email": f"{actor}@rastro.test",
            "actor_grupos": ["despachador"] if "desp" in actor else ["conductor"],
            "nota": "Dato sintetico de preparacion del entorno",
        }
    )
    time.sleep(0.002)  # Separa las marcas de tiempo para que el orden sea estable.


def datos_ya_sembrados(recurso) -> bool:
    tabla = recurso.Table(CONFIG.tabla_envios)
    return tabla.scan(Limit=1).get("Count", 0) > 0


def main() -> int:
    argumentos = {
        "region_name": CONFIG.region,
        "endpoint_url": CONFIG.endpoint_dynamodb,
    }
    cliente_dynamo = boto3.client("dynamodb", **argumentos)
    recurso_dynamo = boto3.resource("dynamodb", **argumentos)
    cliente_s3 = boto3.client(
        "s3",
        region_name=CONFIG.region,
        endpoint_url=CONFIG.endpoint_s3,
        config=ConfigBoto(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    pasos = [
        crear_tabla(cliente_dynamo, definicion_tabla_envios(CONFIG.tabla_envios)),
        crear_tabla(cliente_dynamo, definicion_tabla_bitacora(CONFIG.tabla_bitacora)),
        *crear_contenedor(cliente_s3, CONFIG.bucket_evidencias),
    ]

    if datos_ya_sembrados(recurso_dynamo):
        pasos.append("datos sinteticos: ya existen, no se duplican")
        identificadores = []
    else:
        identificadores = sembrar_envios(recurso_dynamo)
        pasos.append(f"datos sinteticos: {len(identificadores)} envios creados")

    for paso in pasos:
        print(f"  [ok] {paso}")

    if identificadores:
        destino = RAIZ / "seed" / "envios-creados.json"
        destino.write_text(
            json.dumps({"envios": identificadores, "creado_en": marca_tiempo()}, indent=2),
            encoding="utf-8",
        )
        print(f"  [ok] identificadores de consulta publica en {destino.name}")

    print("\nEntorno local preparado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
