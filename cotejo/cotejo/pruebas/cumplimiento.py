"""Pruebas de cumplimiento: configuracion de la infraestructura (C-01 a C-04).

Consultan la interfaz de programacion del proveedor en modo lectura y comparan
el resultado obtenido con el criterio declarado en el catalogo.

Una prueba que no puede ejecutarse se marca como NO_EJECUTADA y nunca como
conforme. La distincion importa: en el entorno local varias de estas
capacidades no existen, y presentar su ausencia como conformidad seria el peor
resultado posible de un trabajo de aseguramiento.
"""

from __future__ import annotations

from ..contexto import Contexto
from ..modelos import Conclusion, Observacion, ResultadoPrueba


def _no_disponible(ctx: Contexto, capacidad: str, procedimiento: str) -> ResultadoPrueba:
    return ResultadoPrueba.no_ejecutada(
        f"{capacidad} no esta disponible en el entorno '{ctx.entorno}'. "
        "La prueba queda pendiente de ejecutarse contra la cuenta desplegada.",
        procedimiento,
    )


def _error(procedimiento: str, exc: Exception) -> ResultadoPrueba:
    return ResultadoPrueba.no_ejecutada(
        f"La consulta fallo: {type(exc).__name__}: {exc}", procedimiento
    )


# --------------------------------------------------------------------------- #
# C-01
# --------------------------------------------------------------------------- #


def registro_de_actividad(ctx: Contexto) -> ResultadoPrueba:
    """El registro esta activo y con validacion de integridad de sus archivos."""
    procedimiento = (
        f"aws cloudtrail describe-trails --trail-name-list {ctx.nombre_registro} "
        f"&& aws cloudtrail get-trail-status --name {ctx.nombre_registro}"
    )
    if ctx.es_local:
        return _no_disponible(ctx, "El registro de actividad del proveedor", procedimiento)

    try:
        cliente = ctx.cliente_aws("cloudtrail")
        descripcion = cliente.describe_trails(trailNameList=[ctx.nombre_registro])
        registros = descripcion.get("trailList", [])
        if not registros:
            return ResultadoPrueba(
                conclusion=Conclusion.DESVIADO,
                observaciones=[Observacion(procedimiento, descripcion)],
                resumen=f"No existe el registro de actividad {ctx.nombre_registro}.",
            )

        registro = registros[0]
        estado = cliente.get_trail_status(Name=ctx.nombre_registro)
        validacion = bool(registro.get("LogFileValidationEnabled"))
        entregando = bool(estado.get("IsLogging"))

        conforme = validacion and entregando
        return ResultadoPrueba(
            conclusion=Conclusion.CONFORME if conforme else Conclusion.DESVIADO,
            observaciones=[
                Observacion(procedimiento, {"describe_trails": descripcion, "status": estado})
            ],
            resumen=(
                "El registro esta activo y valida la integridad de sus archivos."
                if conforme
                else f"Registro activo: {entregando}; validacion de integridad: {validacion}."
            ),
            detalle={"entregando": entregando, "validacion_integridad": validacion},
        )
    except Exception as exc:  # noqa: BLE001
        return _error(procedimiento, exc)


# --------------------------------------------------------------------------- #
# C-02
# --------------------------------------------------------------------------- #


def cifrado_de_evidencias(ctx: Contexto) -> ResultadoPrueba:
    """Cifrado por omision con llave propia, rotacion habilitada y objeto cifrado.

    Se comprueban las tres cosas y no solo la configuracion del contenedor: que
    el contenedor pida cifrado no demuestra que un objeto concreto este cifrado,
    y es el objeto el que constituye la evidencia de entrega.
    """
    procedimiento = (
        f"aws s3api get-bucket-encryption --bucket {ctx.bucket_evidencias} "
        f"&& aws kms get-key-rotation-status --key-id {ctx.alias_llave} "
        f"&& aws s3api head-object sobre un objeto del contenedor"
    )
    if ctx.es_local:
        return _no_disponible(
            ctx, "El cifrado con llave administrada por el cliente (KMS)", procedimiento
        )

    observaciones: list[Observacion] = []
    fallos: list[str] = []

    try:
        s3 = ctx.cliente_aws("s3")
        cifrado = s3.get_bucket_encryption(Bucket=ctx.bucket_evidencias)
        observaciones.append(Observacion("s3api get-bucket-encryption", cifrado))
        reglas = cifrado["ServerSideEncryptionConfiguration"]["Rules"]
        algoritmo = reglas[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
        if algoritmo != "aws:kms":
            fallos.append(f"el cifrado por omision es {algoritmo} y no aws:kms")
    except Exception as exc:  # noqa: BLE001
        observaciones.append(Observacion("s3api get-bucket-encryption", None, error=str(exc)))
        fallos.append("no hay cifrado por omision configurado en el contenedor")

    try:
        kms = ctx.cliente_aws("kms")
        llave = kms.describe_key(KeyId=ctx.alias_llave)
        id_llave = llave["KeyMetadata"]["KeyId"]
        rotacion = kms.get_key_rotation_status(KeyId=id_llave)
        observaciones.append(Observacion("kms get-key-rotation-status", rotacion))
        if not rotacion.get("KeyRotationEnabled"):
            fallos.append("la rotacion de la llave no esta habilitada")
    except Exception as exc:  # noqa: BLE001
        observaciones.append(Observacion("kms get-key-rotation-status", None, error=str(exc)))
        fallos.append(f"no fue posible consultar la llave {ctx.alias_llave}")

    try:
        s3 = ctx.cliente_aws("s3")
        listado = s3.list_objects_v2(Bucket=ctx.bucket_evidencias, MaxKeys=1)
        objetos = listado.get("Contents", [])
        if not objetos:
            observaciones.append(
                Observacion("s3api list-objects-v2", listado, error="no hay objetos que inspeccionar")
            )
            fallos.append("no hay ninguna evidencia almacenada sobre la que comprobar el cifrado")
        else:
            propiedades = s3.head_object(Bucket=ctx.bucket_evidencias, Key=objetos[0]["Key"])
            observaciones.append(Observacion("s3api head-object", propiedades))
            if propiedades.get("ServerSideEncryption") != "aws:kms":
                fallos.append(
                    f"el objeto {objetos[0]['Key']} no declara cifrado aws:kms"
                )
    except Exception as exc:  # noqa: BLE001
        observaciones.append(Observacion("s3api head-object", None, error=str(exc)))
        fallos.append("no fue posible inspeccionar un objeto almacenado")

    return ResultadoPrueba(
        conclusion=Conclusion.DESVIADO if fallos else Conclusion.CONFORME,
        observaciones=observaciones,
        resumen=(
            "; ".join(fallos)
            if fallos
            else "Cifrado por omision con la llave del proyecto, rotacion habilitada y objeto cifrado."
        ),
        detalle={"fallos": fallos},
    )


# --------------------------------------------------------------------------- #
# C-03
# --------------------------------------------------------------------------- #


def acceso_publico_bloqueado(ctx: Contexto) -> ResultadoPrueba:
    """Los cuatro indicadores de bloqueo de acceso publico estan activos."""
    procedimiento = f"aws s3api get-public-access-block --bucket {ctx.bucket_evidencias}"
    if ctx.es_local:
        return _no_disponible(ctx, "El bloqueo de acceso publico del contenedor", procedimiento)

    try:
        respuesta = ctx.cliente_aws("s3").get_public_access_block(Bucket=ctx.bucket_evidencias)
        configuracion = respuesta["PublicAccessBlockConfiguration"]
        apagados = [clave for clave, valor in configuracion.items() if not valor]
        return ResultadoPrueba(
            conclusion=Conclusion.DESVIADO if apagados else Conclusion.CONFORME,
            observaciones=[Observacion(procedimiento, respuesta)],
            resumen=(
                f"Indicadores de bloqueo desactivados: {', '.join(apagados)}"
                if apagados
                else "Los cuatro indicadores de bloqueo de acceso publico estan activos."
            ),
            detalle={"indicadores_desactivados": apagados},
        )
    except Exception as exc:  # noqa: BLE001
        # La ausencia de configuracion es una desviacion, no un fallo de la
        # prueba: significa que el contenedor no tiene el bloqueo aplicado.
        if "NoSuchPublicAccessBlockConfiguration" in str(exc):
            return ResultadoPrueba(
                conclusion=Conclusion.DESVIADO,
                observaciones=[Observacion(procedimiento, None, error=str(exc))],
                resumen="El contenedor no tiene configuracion de bloqueo de acceso publico.",
            )
        return _error(procedimiento, exc)


# --------------------------------------------------------------------------- #
# C-04
# --------------------------------------------------------------------------- #


def versionado_activo(ctx: Contexto) -> ResultadoPrueba:
    """El versionado del contenedor esta en estado Enabled.

    Esta prueba si se ejecuta en el entorno local, porque el almacenamiento
    equivalente implementa el versionado. Es la unica de cumplimiento que lo
    hace, y por eso el informe local no puede presentarse como una auditoria
    completa de la infraestructura.
    """
    procedimiento = f"aws s3api get-bucket-versioning --bucket {ctx.bucket_evidencias}"
    try:
        respuesta = ctx.cliente_aws("s3").get_bucket_versioning(Bucket=ctx.bucket_evidencias)
        estado = respuesta.get("Status", "NoConfigurado")
        conforme = estado == "Enabled"
        return ResultadoPrueba(
            conclusion=Conclusion.CONFORME if conforme else Conclusion.DESVIADO,
            observaciones=[Observacion(procedimiento, respuesta)],
            resumen=(
                "El versionado del contenedor esta habilitado."
                if conforme
                else f"El versionado del contenedor esta en estado {estado}."
            ),
            detalle={"estado": estado},
        )
    except Exception as exc:  # noqa: BLE001
        return _error(procedimiento, exc)
