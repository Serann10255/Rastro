"""Prepara el entorno local: tablas, indices, contenedor y datos sinteticos.

Es el equivalente local de la secuencia de despliegue de AWS y comparte con ella
la misma definicion de tablas e indices, de modo que lo que se prueba en local
tiene la misma forma que lo desplegado. La secuencia es idempotente: puede
ejecutarse tantas veces como haga falta sin duplicar recursos ni datos.

Las contrasenas de la semilla se derivan aqui con PBKDF2 y nunca se almacenan en
claro, ni siquiera en el entorno local. Guardarlas en claro "porque es solo
desarrollo" es como acaban en produccion.
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
from rastro_core.passwords import derivar  # noqa: E402
from rastro_core.state_machine import Estado, codigo_de  # noqa: E402

CONFIG = cargar_config()
RAIZ = Path(__file__).resolve().parents[2]
SEMILLA = RAIZ / "seed" / "organizaciones.json"
SEMILLA_MODULOS = RAIZ / "seed" / "modulos.json"


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


def definicion_tabla_maestros(nombre: str) -> dict:
    """Empresas, usuarios, tiendas, clientes y transportistas.

    El indice ``gsi_email`` resuelve el inicio de sesion: el usuario escribe su
    correo y no su organizacion, de modo que hay que encontrarlo sin saber en
    que particion esta. Es la unica consulta del sistema que no filtra por
    organizacion, y esta acotada a ese uso.
    """
    return {
        "TableName": nombre,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi_email_pk", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "gsi_email",
                "KeySchema": [{"AttributeName": "gsi_email_pk", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
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

    pasos.append(
        _aplicar_control(
            "versionado",
            cliente.put_bucket_versioning,
            Bucket=nombre,
            VersioningConfiguration={"Status": "Enabled"},
        )
    )
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
# Datos maestros
# --------------------------------------------------------------------------- #


def sembrar_maestros(recurso) -> dict:
    """Crea empresas, usuarios, tiendas, clientes y transportistas.

    Las contrasenas se derivan aqui. Derivarlas cuesta unos cientos de
    milisegundos por usuario -es el proposito de PBKDF2- y por eso la
    preparacion tarda unos segundos mas de lo que tardaria con hashes debiles.
    """
    from rastro_core.maestros import RepositorioMaestros

    maestros = RepositorioMaestros(CONFIG, recurso=recurso)
    semilla = json.loads(SEMILLA.read_text(encoding="utf-8"))

    resumen = {
        "organizaciones": 0,
        "usuarios": 0,
        "tiendas": 0,
        "clientes": 0,
        "transportistas": 0,
    }
    referencias: dict[str, dict] = {}

    for organizacion in semilla["organizaciones"]:
        org_id = organizacion["org_id"]
        maestros.guardar_empresa({k: v for k, v in organizacion.items() if not isinstance(v, list)})
        resumen["organizaciones"] += 1

        # Se conserva el usuario tal como quedo guardado, con el `sub` que el
        # repositorio le asigno. Inventar un `sub` aqui produciria envios
        # asignados a un conductor que no existe, y el sintoma seria que el
        # conductor entra y no ve ninguno de sus envios.
        usuarios_creados = []
        for usuario in organizacion["usuarios"]:
            creado = maestros.guardar_usuario(
                {
                    "correo": usuario["correo"],
                    "nombre": usuario["nombre"],
                    "org_id": org_id,
                    "grupos": usuario["grupos"],
                    "hash_clave": derivar(usuario["clave"]),
                    "telefono": usuario.get("telefono", ""),
                    "activo": True,
                }
            )
            usuarios_creados.append(creado)
            resumen["usuarios"] += 1

        tiendas = [maestros.guardar_tienda(org_id, t) for t in organizacion["tiendas"]]
        clientes = [maestros.guardar_cliente(org_id, c) for c in organizacion["clientes"]]
        transportistas = [
            maestros.guardar_transportista(org_id, t) for t in organizacion["transportistas"]
        ]

        resumen["tiendas"] += len(tiendas)
        resumen["clientes"] += len(clientes)
        resumen["transportistas"] += len(transportistas)

        referencias[org_id] = {
            "tiendas": tiendas,
            "clientes": clientes,
            "transportistas": transportistas,
            "usuarios": usuarios_creados,
        }

    return {"resumen": resumen, "referencias": referencias}


def sembrar_modulos(recurso) -> str:
    """Aprovisiona los modulos de cada organizacion.

    Se ejecuta siempre, tambien sobre una instalacion ya sembrada: de lo
    contrario, una instalacion existente no veria nunca un modulo nuevo y la
    pantalla de operaciones se quedaria vacia sin explicar por que.

    Lo que la organizacion decidio se respeta. Si un administrador apago un
    modulo, la actualizacion conserva su `disponible` y su motivo: volver a
    encenderlo en cada despliegue convertiria una decision de la empresa en algo
    que el sistema deshace a sus espaldas.
    """
    from rastro_core.errors import NoEncontradoError
    from rastro_core.maestros import RepositorioMaestros

    maestros = RepositorioMaestros(CONFIG, recurso=recurso)
    modulos = json.loads(SEMILLA_MODULOS.read_text(encoding="utf-8"))["modulos"]
    organizaciones = [
        o["org_id"] for o in json.loads(SEMILLA.read_text(encoding="utf-8"))["organizaciones"]
    ]

    nuevos = conservados = 0
    for org_id in organizaciones:
        for modulo in modulos:
            try:
                actual = maestros.obtener_modulo(org_id, modulo["clave"])
            except NoEncontradoError:
                maestros.guardar_modulo(org_id, modulo)
                nuevos += 1
                continue

            maestros.guardar_modulo(
                org_id,
                {
                    **modulo,
                    "disponible": actual.get("disponible", modulo.get("disponible", True)),
                    "motivo": actual.get("motivo", modulo.get("motivo", "")),
                },
            )
            conservados += 1

    return f"modulos: {nuevos} nuevos, {conservados} actualizados conservando su estado"


def sembrar_roles(recurso) -> str:
    """Aprovisiona a cada organizacion los roles de fabrica.

    Se escriben en la tabla para que la empresa pueda personalizarlos: mientras
    no exista el registro, el sistema aplica la definicion del codigo, y en
    cuanto existe manda la suya.

    No se pisa lo que la organizacion haya cambiado: si un administrador ajusto
    los permisos del despachador, una actualizacion posterior no los devuelve a
    los de fabrica a sus espaldas. El administrador no se escribe nunca: se
    resuelve en el codigo y siempre lo tiene todo, que es el seguro contra que
    una empresa se quede sin nadie que pueda entrar.
    """
    from rastro_core.authz import Grupo, ROLES_INTEGRADOS
    from rastro_core.errors import NoEncontradoError
    from rastro_core.maestros import RepositorioMaestros

    maestros = RepositorioMaestros(CONFIG, recurso=recurso)
    organizaciones = [
        o["org_id"] for o in json.loads(SEMILLA.read_text(encoding="utf-8"))["organizaciones"]
    ]

    nuevos = conservados = 0
    for org_id in organizaciones:
        for definicion in ROLES_INTEGRADOS.values():
            if definicion.clave == Grupo.ADMINISTRADOR:
                continue
            try:
                maestros.obtener_rol(org_id, definicion.clave)
                conservados += 1
            except NoEncontradoError:
                maestros.guardar_rol(
                    org_id,
                    {
                        "clave": definicion.clave,
                        "nombre": definicion.nombre,
                        "descripcion": definicion.descripcion,
                        "operaciones": sorted(str(o) for o in definicion.operaciones),
                    },
                )
                nuevos += 1

    return f"roles: {nuevos} aprovisionados, {conservados} ya personalizables"


def maestros_ya_sembrados(recurso) -> bool:
    tabla = recurso.Table(CONFIG.tabla_maestros)
    return tabla.scan(Limit=1).get("Count", 0) > 0


# --------------------------------------------------------------------------- #
# Envios sinteticos
# --------------------------------------------------------------------------- #

#: Recorridos representativos: uno completo, uno a medias, uno detenido y uno
#: recien creado. Un tablero con todos los envios en el mismo estado no permite
#: ver si los indicadores funcionan.
RECORRIDOS: list[list[Estado]] = [
    [Estado.ASIGNADO, Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO],
    [Estado.ASIGNADO, Estado.RECOLECTADO, Estado.EN_TRANSITO],
    [Estado.ASIGNADO, Estado.RECOLECTADO, Estado.INCIDENCIA],
    [Estado.ASIGNADO],
    [],
]

DESTINATARIOS = [
    ("Laura Mejia Rios", "3001110001", "Carrera 7 #32-16", "Bogota"),
    ("Andres Pardo Leon", "3001110002", "Calle 45 #13-05", "Bogota"),
    ("Marcela Nino Cruz", "3001110003", "Calle 80 #90-10", "Bogota"),
    ("Julian Cortes Amaya", "3001110004", "Carrera 15 #93-60", "Bogota"),
    ("Natalia Suarez Bello", "3001110005", "Avenida 19 #114-65", "Bogota"),
    ("Ricardo Tovar Leal", "3001110006", "Calle 26 #68-35", "Bogota"),
    ("Diana Camargo Solis", "3001110007", "Carrera 30 #45-03", "Bogota"),
    ("Felipe Arango Diaz", "3001110008", "Calle 72 #10-34", "Bogota"),
]

DESCRIPCIONES = [
    "Sobre con documentos contractuales",
    "Caja de muestras comerciales",
    "Paquete liviano",
    "Medicamentos refrigerados",
    "Repuestos pequenos",
]


def sembrar_envios(recurso, referencias: dict) -> list[str]:
    """Carga envios sinteticos con su historico, sin tocar la bitacora.

    La bitacora no se siembra a proposito: sus eslabones deben producirse como
    efecto de operaciones reales del sistema. Una cadena fabricada por el guion
    de preparacion no probaria nada.
    """
    from rastro_core.repository import RepositorioDynamo

    repositorio = RepositorioDynamo(CONFIG, recurso=recurso)
    creados: list[str] = []
    indice = 0

    for org_id, datos in referencias.items():
        conductores = [u for u in datos["usuarios"] if "conductor" in u["grupos"]]
        despachador = next(
            (u for u in datos["usuarios"] if "despachador" in u["grupos"]), datos["usuarios"][0]
        )

        for repeticion in range(len(RECORRIDOS) * 2):
            recorrido = RECORRIDOS[repeticion % len(RECORRIDOS)]
            tienda = datos["tiendas"][indice % len(datos["tiendas"])]
            cliente = datos["clientes"][indice % len(datos["clientes"])]
            transportista = datos["transportistas"][indice % len(datos["transportistas"])]
            conductor = conductores[indice % len(conductores)] if conductores else despachador
            nombre, telefono, direccion, ciudad = DESTINATARIOS[indice % len(DESTINATARIOS)]

            ahora = marca_tiempo()
            envio = {
                "envio_id": nuevo_id_envio(),
                "org_id": org_id,
                "estado": Estado.CREADO.value,
                "codigo_estado": codigo_de(Estado.CREADO),
                "creado_en": ahora,
                "actualizado_en": ahora,
                "creado_por": despachador["sub"],
                "origen": {
                    "linea": tienda["direccion"],
                    "ciudad": tienda["ciudad"],
                    "referencia": tienda["nombre"],
                },
                "destino": {"linea": direccion, "ciudad": ciudad, "referencia": ""},
                "destinatario": {"nombre": nombre, "telefono": telefono},
                "descripcion": DESCRIPCIONES[indice % len(DESCRIPCIONES)],
                "orden_compra": f"OC-2026-{1000 + indice}",
                "tienda_id": tienda["tienda_id"],
                "tienda_nombre": tienda["nombre"],
                "cliente_id": cliente["cliente_id"],
                "cliente_nombre": cliente["nombre"],
                "transportista_id": transportista["transportista_id"],
                "transportista_nombre": transportista["nombre"],
                "estacion_actual": tienda["nombre"],
                "peso_kg": round(0.5 + (indice % 7) * 1.4, 2),
                "valor_declarado": 50000 + (indice % 5) * 25000,
                "bultos": 1 + (indice % 3),
                "fecha_estimada": ahora[:10],
                "observaciones": "",
                "evidencias": [],
            }
            repositorio.guardar_envio(envio)
            _agregar_evento(repositorio, envio, Estado.CREADO, None, despachador, "despachador")

            estado_anterior = Estado.CREADO
            for estado in recorrido:
                if estado is Estado.ASIGNADO:
                    envio["conductor_sub"] = conductor["sub"]
                    envio["conductor_nombre"] = conductor["nombre"]
                actor = despachador if estado is Estado.ASIGNADO else conductor
                grupo = "despachador" if estado is Estado.ASIGNADO else "conductor"
                _agregar_evento(repositorio, envio, estado, estado_anterior, actor, grupo)
                if estado is Estado.INCIDENCIA:
                    envio["estado_previo_incidencia"] = estado_anterior.value
                estado_anterior = estado

            envio["estado"] = estado_anterior.value
            envio["codigo_estado"] = codigo_de(estado_anterior)
            envio["actualizado_en"] = marca_tiempo()
            repositorio.actualizar_envio(envio)
            creados.append(envio["envio_id"])
            indice += 1

    return creados


def _agregar_evento(repositorio, envio: dict, estado, estado_anterior, actor: dict, grupo: str) -> None:
    repositorio.agregar_evento(
        {
            "evento_id": nuevo_id_evento(),
            "envio_id": envio["envio_id"],
            "org_id": envio["org_id"],
            "estado": estado.value,
            "codigo_estado": codigo_de(estado),
            "estado_anterior": estado_anterior.value if estado_anterior else None,
            "ts": marca_tiempo(),
            "actor_sub": actor["sub"],
            "actor_email": actor["correo"],
            "actor_grupos": [grupo],
            "nota": "Dato sintetico de preparacion del entorno",
        }
    )
    time.sleep(0.002)  # Separa las marcas de tiempo para que el orden sea estable.


def envios_ya_sembrados(recurso) -> bool:
    tabla = recurso.Table(CONFIG.tabla_envios)
    return tabla.scan(Limit=1).get("Count", 0) > 0


# --------------------------------------------------------------------------- #


def main() -> int:
    argumentos = {"region_name": CONFIG.region, "endpoint_url": CONFIG.endpoint_dynamodb}
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
        crear_tabla(cliente_dynamo, definicion_tabla_maestros(CONFIG.tabla_maestros)),
        *crear_contenedor(cliente_s3, CONFIG.bucket_evidencias),
    ]

    referencias: dict = {}
    if maestros_ya_sembrados(recurso_dynamo):
        pasos.append("datos maestros: ya existen, no se duplican")
        referencias = _releer_referencias(recurso_dynamo)
    else:
        pasos.append("derivando contrasenas con PBKDF2 (tarda unos segundos)...")
        for paso in pasos:
            print(f"  [ok] {paso}")
        pasos = []
        siembra = sembrar_maestros(recurso_dynamo)
        referencias = siembra["referencias"]
        resumen = siembra["resumen"]
        pasos.append(
            "datos maestros: "
            + ", ".join(f"{cantidad} {clave}" for clave, cantidad in resumen.items())
        )

    pasos.append(sembrar_roles(recurso_dynamo))
    pasos.append(sembrar_modulos(recurso_dynamo))

    identificadores: list[str] = []
    if envios_ya_sembrados(recurso_dynamo):
        pasos.append("envios sinteticos: ya existen, no se duplican")
    elif referencias:
        identificadores = sembrar_envios(recurso_dynamo, referencias)
        pasos.append(f"envios sinteticos: {len(identificadores)} creados con su historico")

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


def _releer_referencias(recurso) -> dict:
    """Recupera los maestros ya existentes para poder sembrar envios encima."""
    from rastro_core.maestros import RepositorioMaestros

    maestros = RepositorioMaestros(CONFIG, recurso=recurso)
    semilla = json.loads(SEMILLA.read_text(encoding="utf-8"))
    referencias = {}
    for organizacion in semilla["organizaciones"]:
        org_id = organizacion["org_id"]
        tiendas = maestros.listar_tiendas(org_id)
        if not tiendas:
            continue
        referencias[org_id] = {
            "tiendas": tiendas,
            "clientes": maestros.listar_clientes(org_id),
            "transportistas": maestros.listar_transportistas(org_id),
            "usuarios": maestros.listar_usuarios(org_id),
        }
    return referencias


if __name__ == "__main__":
    raise SystemExit(main())
