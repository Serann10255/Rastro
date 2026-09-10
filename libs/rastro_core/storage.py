"""Evidencias de entrega en almacenamiento de objetos cifrado (REQ-05).

Las evidencias no atraviesan los microservicios: el servicio genera un enlace
prefirmado de duracion limitada y el dispositivo del mensajero carga el archivo
directamente contra el almacenamiento, que lo cifra con la llave administrada
por el proyecto.

Las claves de objeto se construyen siempre bajo un prefijo por organizacion, de
modo que el enlace emitido queda acotado a esa organizacion y no puede
apuntar a los datos de otra empresa.
"""

from __future__ import annotations

import posixpath
import re
import uuid

from .config import Config, cargar_config
from .errors import ValidacionError

#: Extensiones admitidas para una evidencia de entrega.
EXTENSIONES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}

_SEGMENTO_VALIDO = re.compile(r"^[A-Za-z0-9._-]+$")


def _validar_segmento(valor: str, nombre: str) -> str:
    valor = (valor or "").strip()
    if not valor or not _SEGMENTO_VALIDO.match(valor):
        raise ValidacionError(f"El valor de {nombre} no es valido para una ruta de almacenamiento.")
    return valor


def prefijo_organizacion(org_id: str) -> str:
    """Todo objeto de una organizacion vive bajo este prefijo, sin excepcion."""
    return f"{_validar_segmento(org_id, 'organizacion')}/"


def construir_clave(org_id: str, envio_id: str, evidencia_id: str, tipo_contenido: str) -> str:
    extension = EXTENSIONES.get(tipo_contenido)
    if extension is None:
        raise ValidacionError(f"Tipo de contenido no admitido para evidencia: {tipo_contenido}")
    return posixpath.join(
        prefijo_organizacion(org_id),
        _validar_segmento(envio_id, "envio"),
        f"{_validar_segmento(evidencia_id, 'evidencia')}.{extension}",
    )


def nuevo_id_evidencia() -> str:
    return uuid.uuid4().hex


class AlmacenEvidencias:
    """Envuelve el cliente de objetos y concentra la politica de cifrado."""

    def __init__(self, config: Config | None = None, cliente=None, cliente_firma=None) -> None:
        self.config = config or cargar_config()
        self.cliente = cliente or self._construir_cliente(self.config.endpoint_s3)

        # La firma de un enlace prefirmado cubre el nombre del servidor. El
        # servicio alcanza el almacenamiento por su direccion interna, pero el
        # dispositivo del mensajero no la resuelve: hay que firmar contra la
        # direccion que usara el cliente. En AWS ambas coinciden y este segundo
        # cliente es el mismo objeto.
        publico = self.config.endpoint_s3_publico
        if cliente_firma is not None:
            self.cliente_firma = cliente_firma
        elif publico and publico != self.config.endpoint_s3:
            self.cliente_firma = self._construir_cliente(publico)
        else:
            self.cliente_firma = self.cliente

    def _construir_cliente(self, endpoint: str | None):
        import boto3
        from botocore.config import Config as BotoConfig

        return boto3.client(
            "s3",
            region_name=self.config.region,
            endpoint_url=endpoint,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if self.config.s3_force_path_style else "auto"},
            ),
        )

    # -- carga ------------------------------------------------------------- #

    def enlace_de_carga(
        self, *, org_id: str, envio_id: str, tipo_contenido: str, evidencia_id: str | None = None
    ) -> dict:
        """Enlace prefirmado de escritura, valido por un tiempo definido.

        El cifrado se impone en los parametros de la firma: un cliente que
        intente cargar sin la cabecera de cifrado obtiene una firma invalida.
        """
        evidencia_id = evidencia_id or nuevo_id_evidencia()
        clave = construir_clave(org_id, envio_id, evidencia_id, tipo_contenido)
        parametros = {
            "Bucket": self.config.bucket_evidencias,
            "Key": clave,
            "ContentType": tipo_contenido,
        }
        parametros.update(self._parametros_cifrado())

        url = self.cliente_firma.generate_presigned_url(
            "put_object",
            Params=parametros,
            ExpiresIn=self.config.vigencia_enlace_segundos,
        )
        return {
            "evidencia_id": evidencia_id,
            "clave": clave,
            "url": url,
            "metodo": "PUT",
            "vigencia_segundos": self.config.vigencia_enlace_segundos,
            "encabezados": self._encabezados_carga(tipo_contenido),
        }

    def enlace_de_descarga(self, *, org_id: str, clave: str) -> str:
        """Enlace de lectura. Comprueba que la clave pertenece a la organizacion."""
        self._exigir_prefijo(org_id, clave)
        return self.cliente_firma.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.config.bucket_evidencias, "Key": clave},
            ExpiresIn=self.config.vigencia_enlace_segundos,
        )

    def describir_objeto(self, *, org_id: str, clave: str) -> dict:
        """Propiedades del objeto, incluido su estado de cifrado.

        Cotejo la usa como evidencia del control C-02: el criterio no es que el
        codigo pida cifrado, sino que el objeto almacenado lo declare.
        """
        self._exigir_prefijo(org_id, clave)
        respuesta = self.cliente.head_object(Bucket=self.config.bucket_evidencias, Key=clave)
        return {
            "clave": clave,
            "tamano": respuesta.get("ContentLength"),
            "tipo_contenido": respuesta.get("ContentType"),
            "cifrado": respuesta.get("ServerSideEncryption"),
            "llave_kms": respuesta.get("SSEKMSKeyId"),
            "version_id": respuesta.get("VersionId"),
            "modificado_en": str(respuesta.get("LastModified", "")),
        }

    def existe(self, *, org_id: str, clave: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.describir_objeto(org_id=org_id, clave=clave)
            return True
        except ClientError:
            return False

    # -- internos ---------------------------------------------------------- #

    def _parametros_cifrado(self) -> dict:
        """En local (MinIO) no hay KMS; en AWS se exige la llave del proyecto.

        La diferencia queda contenida aqui y se declara: el entorno local no
        acredita el control de cifrado, que solo puede verificarse en AWS. Es
        justamente lo que comprueba el control C-02 de Cotejo.
        """
        if self.config.es_local:
            return {}
        return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self.config.alias_llave}

    def _encabezados_carga(self, tipo_contenido: str) -> dict:
        encabezados = {"Content-Type": tipo_contenido}
        if not self.config.es_local:
            encabezados["x-amz-server-side-encryption"] = "aws:kms"
            encabezados["x-amz-server-side-encryption-aws-kms-key-id"] = self.config.alias_llave
        return encabezados

    def _exigir_prefijo(self, org_id: str, clave: str) -> None:
        if not (clave or "").startswith(prefijo_organizacion(org_id)):
            # No se distingue entre "no existe" y "no es tuyo" (REQ-06).
            from .errors import NoEncontradoError

            raise NoEncontradoError("La evidencia no existe.")
