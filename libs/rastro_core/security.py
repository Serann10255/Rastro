"""Validacion del token de sesion.

En AWS el token lo emite Cognito y lo valida el autorizador de API Gateway
(supuesto SU-01); esta capa lo vuelve a validar dentro de cada servicio para no
depender de un unico control y para que la alternativa prevista en el apartado 8
-validar el token dentro de cada funcion- este implementada si SU-01 no se
confirma.

En local el emisor es el microservicio ``auth``, que firma con HS256. La
diferencia queda contenida aqui: ningun otro modulo sabe como se firma el token.
"""

from __future__ import annotations

import time
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from .config import Config, cargar_config
from .errors import NoAutenticadoError
from .models import Identidad

#: Reclamacion que transporta el identificador de organizacion.
CLAIM_ORG = "custom:org_id"
#: Reclamacion de grupos que emite Cognito.
CLAIM_GRUPOS = "cognito:groups"


@lru_cache(maxsize=4)
def _cliente_jwks(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=600)


def _llave_de_verificacion(token: str, config: Config):
    if config.jwt_jwks_url:
        return _cliente_jwks(config.jwt_jwks_url).get_signing_key_from_jwt(token).key, ["RS256"]
    if not config.jwt_secreto_local:
        raise NoAutenticadoError("No hay material de verificacion configurado para el token.")
    return config.jwt_secreto_local, ["HS256"]


def decodificar_token(token: str, config: Config | None = None) -> dict:
    """Valida firma, vigencia, emisor y audiencia. Devuelve las reclamaciones."""
    config = config or cargar_config()
    token = (token or "").strip()
    if not token:
        raise NoAutenticadoError("Falta el token de sesion.")

    llave, algoritmos = _llave_de_verificacion(token, config)
    try:
        return jwt.decode(
            token,
            llave,
            algorithms=algoritmos,
            issuer=config.jwt_emisor,
            audience=config.jwt_audiencia,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise NoAutenticadoError("El token de sesion expiro.") from exc
    except jwt.InvalidTokenError as exc:
        raise NoAutenticadoError(f"Token de sesion invalido: {exc}") from exc


def identidad_desde_token(token: str, config: Config | None = None) -> Identidad:
    """Traduce las reclamaciones a la identidad que consume el dominio.

    Un token sin organizacion no produce identidad: sin ese dato ninguna
    consulta puede resolverse (riesgo R-05).
    """
    claims = exigir_token_de_acceso(decodificar_token(token, config))
    org_id = str(claims.get(CLAIM_ORG) or claims.get("org_id") or "").strip()
    if not org_id:
        raise NoAutenticadoError("El token no declara organizacion; la peticion no puede resolverse.")

    grupos = claims.get(CLAIM_GRUPOS) or claims.get("grupos") or []
    if isinstance(grupos, str):
        grupos = [g for g in grupos.replace(",", " ").split() if g]

    return Identidad(
        sub=str(claims.get("sub")),
        email=str(claims.get("email") or ""),
        org_id=org_id,
        grupos=tuple(str(g) for g in grupos),
        sid=str(claims.get("sid") or ""),
    )


def extraer_token(encabezado: str | None) -> str:
    """Obtiene el token de un encabezado ``Authorization: Bearer <token>``."""
    if not encabezado:
        raise NoAutenticadoError("Falta el encabezado Authorization.")
    partes = encabezado.split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise NoAutenticadoError("El encabezado Authorization debe tener la forma 'Bearer <token>'.")
    return partes[1]


def emitir_token_local(
    *,
    sub: str,
    email: str,
    org_id: str,
    grupos,
    config: Config | None = None,
    vigencia_segundos: int = 3600,
) -> str:
    """Emite un token HS256 equivalente al de Cognito. Solo para el entorno local.

    Lo usan el microservicio ``auth`` y las pruebas sustantivas de Cotejo, que
    necesitan autenticarse como usuarios de distintos roles y organizaciones.
    """
    config = config or cargar_config()
    if not config.jwt_secreto_local:
        raise NoAutenticadoError("El emisor local requiere un secreto configurado.")
    ahora = int(time.time())
    carga = {
        "sub": sub,
        "email": email,
        CLAIM_ORG: org_id,
        CLAIM_GRUPOS: sorted(str(g) for g in grupos),
        "iss": config.jwt_emisor,
        "aud": config.jwt_audiencia,
        "iat": ahora,
        "exp": ahora + int(vigencia_segundos),
        "token_use": "id",
    }
    return jwt.encode(carga, config.jwt_secreto_local, algorithm="HS256")


# --------------------------------------------------------------------------- #
# Emision de la sesion: token de acceso y token de refresco
# --------------------------------------------------------------------------- #

#: Distingue los dos tipos de token. Sin esta marca, un token de refresco
#: -que vive mucho mas- serviria para operar, y su robo tendria el efecto de
#: una sesion permanente.
CLAIM_TIPO = "token_use"
TIPO_ACCESO = "id"
TIPO_REFRESCO = "refresh"


def emitir_token_de_acceso(
    *,
    sub: str,
    email: str,
    org_id: str,
    grupos,
    sesion_id: str,
    config: Config | None = None,
) -> tuple[str, int]:
    """Token corto con el que se opera. Devuelve el token y su vigencia."""
    config = config or cargar_config()
    if not config.jwt_secreto_local:
        raise NoAutenticadoError("El emisor requiere un secreto configurado.")

    ahora = int(time.time())
    vigencia = int(config.vigencia_token_segundos)
    carga = {
        "sub": sub,
        "email": email,
        CLAIM_ORG: org_id,
        CLAIM_GRUPOS: sorted(str(g) for g in grupos),
        "sid": sesion_id,
        "iss": config.jwt_emisor,
        "aud": config.jwt_audiencia,
        "iat": ahora,
        "exp": ahora + vigencia,
        CLAIM_TIPO: TIPO_ACCESO,
    }
    return jwt.encode(carga, config.jwt_secreto_local, algorithm="HS256"), vigencia


def emitir_token_de_refresco(
    *, sub: str, org_id: str, sesion_id: str, config: Config | None = None
) -> tuple[str, int]:
    """Token largo que solo sirve para pedir uno de acceso nuevo.

    No lleva grupos: si los llevara, un cambio de rol no surtiria efecto hasta
    que caducara el refresco. Al renovar se releen del registro del usuario.
    """
    config = config or cargar_config()
    if not config.jwt_secreto_local:
        raise NoAutenticadoError("El emisor requiere un secreto configurado.")

    ahora = int(time.time())
    vigencia = int(config.vigencia_refresco_segundos)
    carga = {
        "sub": sub,
        CLAIM_ORG: org_id,
        "sid": sesion_id,
        "iss": config.jwt_emisor,
        "aud": config.jwt_audiencia,
        "iat": ahora,
        "exp": ahora + vigencia,
        CLAIM_TIPO: TIPO_REFRESCO,
    }
    return jwt.encode(carga, config.jwt_secreto_local, algorithm="HS256"), vigencia


def decodificar_refresco(token: str, config: Config | None = None) -> dict:
    """Valida un token de refresco y comprueba que no sea uno de acceso."""
    claims = decodificar_token(token, config)
    if claims.get(CLAIM_TIPO) != TIPO_REFRESCO:
        raise NoAutenticadoError("Se esperaba un token de refresco.")
    if not claims.get("sid"):
        raise NoAutenticadoError("El token de refresco no identifica la sesion.")
    return claims


def exigir_token_de_acceso(claims: dict) -> dict:
    """Rechaza un token de refresco presentado como token de acceso."""
    if claims.get(CLAIM_TIPO) == TIPO_REFRESCO:
        raise NoAutenticadoError("Un token de refresco no sirve para operar.")
    return claims
