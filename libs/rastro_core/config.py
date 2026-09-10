"""Configuracion en tiempo de ejecucion (REQ-09: portabilidad).

Ningun identificador propio de la cuenta se escribe a mano en el codigo. El
nombre del contenedor se deriva del numero de cuenta, el rol de ejecucion se
referencia por nombre y la llave de cifrado por alias. Los identificadores que
el proveedor genera al desplegar se escriben en ``config/deployment.json``, que
esta capa lee al arrancar.

Trasladar el sistema a otra cuenta se reduce entonces a ejecutar la secuencia de
despliegue: no hay valores literales que rastrear en el codigo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_DESPLIEGUE = RAIZ_PROYECTO / "config" / "deployment.json"

#: Prefijos y alias: partes estables del nombre, nunca el identificador completo.
PREFIJO_RECURSOS = "rastro"
ALIAS_LLAVE = f"alias/{PREFIJO_RECURSOS}"
NOMBRE_ROL_EJECUCION = "LabRole"


@dataclass(frozen=True)
class Config:
    entorno: str
    region: str
    account_id: str
    tabla_envios: str
    tabla_bitacora: str
    bucket_evidencias: str
    alias_llave: str
    endpoint_dynamodb: str | None
    endpoint_s3: str | None
    endpoint_s3_publico: str | None
    s3_force_path_style: bool
    jwt_emisor: str
    jwt_audiencia: str
    jwt_jwks_url: str | None
    jwt_secreto_local: str | None
    url_publica_api: str
    vigencia_enlace_segundos: int
    urls_servicios: dict[str, str] = field(default_factory=dict)

    @property
    def es_local(self) -> bool:
        return self.entorno == "local"

    def como_dict(self) -> dict:
        datos = self.__dict__.copy()
        datos["jwt_secreto_local"] = "***" if self.jwt_secreto_local else None
        return datos


def _leer_despliegue() -> dict:
    ruta = Path(os.getenv("RASTRO_DEPLOYMENT_FILE", RUTA_DESPLIEGUE))
    if not ruta.is_file():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _valor(clave_env: str, despliegue: dict, clave_despliegue: str, defecto=None):
    """Precedencia: variable de entorno, luego archivo de despliegue, luego defecto."""
    if (bruto := os.getenv(clave_env)) not in (None, ""):
        return bruto
    if (valor := despliegue.get(clave_despliegue)) not in (None, ""):
        return valor
    return defecto


def _booleano(valor, defecto: bool = False) -> bool:
    if valor is None:
        return defecto
    return str(valor).strip().lower() in {"1", "true", "si", "yes", "on"}


@lru_cache(maxsize=1)
def cargar_config() -> Config:
    despliegue = _leer_despliegue()
    entorno = _valor("RASTRO_ENTORNO", despliegue, "entorno", "local")
    region = _valor("AWS_REGION", despliegue, "region", "us-east-1")
    account_id = str(_valor("RASTRO_ACCOUNT_ID", despliegue, "account_id", "000000000000"))

    # El nombre del contenedor se deriva de la cuenta: al migrar cambia solo.
    bucket = _valor(
        "RASTRO_BUCKET_EVIDENCIAS",
        despliegue,
        "bucket_evidencias",
        f"{PREFIJO_RECURSOS}-evidencias-{account_id}",
    )

    return Config(
        entorno=entorno,
        region=region,
        account_id=account_id,
        tabla_envios=_valor("RASTRO_TABLA_ENVIOS", despliegue, "tabla_envios", f"{PREFIJO_RECURSOS}-envios"),
        tabla_bitacora=_valor(
            "RASTRO_TABLA_BITACORA", despliegue, "tabla_bitacora", f"{PREFIJO_RECURSOS}-bitacora"
        ),
        bucket_evidencias=bucket,
        alias_llave=_valor("RASTRO_ALIAS_LLAVE", despliegue, "alias_llave", ALIAS_LLAVE),
        endpoint_dynamodb=_valor("RASTRO_ENDPOINT_DYNAMODB", despliegue, "endpoint_dynamodb"),
        endpoint_s3=_valor("RASTRO_ENDPOINT_S3", despliegue, "endpoint_s3"),
        # Direccion con la que el dispositivo alcanza el almacenamiento. En AWS
        # coincide con la interna; en local no, porque el nombre del contenedor
        # no se resuelve desde el navegador. La firma cubre el nombre del
        # servidor, de modo que un enlace firmado contra la direccion interna es
        # inservible para el cliente aunque la ruta sea correcta.
        endpoint_s3_publico=_valor(
            "RASTRO_ENDPOINT_S3_PUBLICO", despliegue, "endpoint_s3_publico"
        ),
        s3_force_path_style=_booleano(
            _valor("RASTRO_S3_PATH_STYLE", despliegue, "s3_force_path_style", entorno == "local"), True
        ),
        jwt_emisor=_valor("RASTRO_JWT_EMISOR", despliegue, "jwt_emisor", "http://auth:8001"),
        jwt_audiencia=_valor("RASTRO_JWT_AUDIENCIA", despliegue, "jwt_audiencia", "rastro-web"),
        jwt_jwks_url=_valor("RASTRO_JWT_JWKS_URL", despliegue, "jwt_jwks_url"),
        jwt_secreto_local=_valor("RASTRO_JWT_SECRETO", despliegue, "jwt_secreto_local", "rastro-secreto-local-solo-para-desarrollo-32b"),
        url_publica_api=_valor("RASTRO_URL_API", despliegue, "url_publica_api", "http://localhost:8080"),
        vigencia_enlace_segundos=int(
            _valor("RASTRO_VIGENCIA_ENLACE", despliegue, "vigencia_enlace_segundos", 300)
        ),
        urls_servicios=despliegue.get("urls_servicios", {}),
    )


def reiniciar_config() -> None:
    """Limpia la cache. Lo usan las pruebas al cambiar variables de entorno."""
    cargar_config.cache_clear()
