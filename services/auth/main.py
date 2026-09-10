"""Microservicio de autenticacion (emisor de tokens del entorno local).

En AWS este servicio no se despliega: lo sustituye el grupo de usuarios de
Amazon Cognito, que emite el token con la lista de grupos y el identificador de
organizacion. Aqui se reproduce ese contrato para poder desarrollar y probar el
sistema completo sin consumir el presupuesto del laboratorio ni depender de una
sesion de cuatro horas.

El contrato que ambos emisores respetan es el mismo, y esa es la razon de que
sea sustituible: un token firmado, con ``sub``, ``email``, ``cognito:groups`` y
``custom:org_id``, validado por el resto de los servicios con la misma funcion.
"""

from __future__ import annotations

import hmac
import json
import os
from hashlib import sha256
from pathlib import Path

from fastapi import Depends
from pydantic import BaseModel, Field

from rastro_core.config import cargar_config
from rastro_core.errors import NoAutenticadoError
from rastro_core.http import crear_app, identidad_actual
from rastro_core.models import Identidad
from rastro_core.security import emitir_token_local

RUTA_SEMILLA = Path(
    os.getenv("RASTRO_SEMILLA_USUARIOS", Path(__file__).resolve().parents[2] / "seed" / "usuarios.json")
)

app = crear_app(
    "rastro-auth",
    "Emisor de tokens de sesion del entorno local. En AWS lo sustituye Amazon Cognito.",
)


class CredencialesSolicitud(BaseModel):
    usuario: str = Field(min_length=3, max_length=160)
    clave: str = Field(min_length=1, max_length=200)


def _cargar_directorio() -> dict:
    if not RUTA_SEMILLA.is_file():
        raise NoAutenticadoError("No hay directorio de usuarios configurado en este entorno.")
    return json.loads(RUTA_SEMILLA.read_text(encoding="utf-8"))


def _buscar_usuario(usuario: str) -> dict | None:
    for registro in _cargar_directorio().get("usuarios", []):
        if registro.get("usuario", "").lower() == usuario.strip().lower():
            return registro
    return None


def _clave_coincide(esperada: str, recibida: str) -> bool:
    """Comparacion en tiempo constante para no filtrar la clave por temporizacion."""
    return hmac.compare_digest(
        sha256(esperada.encode("utf-8")).digest(), sha256(recibida.encode("utf-8")).digest()
    )


@app.post("/auth/token", tags=["autenticacion"], summary="Emitir token de sesion")
async def emitir_token(solicitud: CredencialesSolicitud) -> dict:
    """Devuelve un token equivalente al que emitiria Cognito.

    Ante credenciales invalidas la respuesta no distingue entre usuario
    inexistente y clave incorrecta: hacerlo permitiria enumerar cuentas.
    """
    registro = _buscar_usuario(solicitud.usuario)
    if registro is None or not _clave_coincide(registro["clave"], solicitud.clave):
        raise NoAutenticadoError("Usuario o clave incorrectos.")

    config = cargar_config()
    token = emitir_token_local(
        sub=registro["sub"],
        email=registro["usuario"],
        org_id=registro["org_id"],
        grupos=registro["grupos"],
        config=config,
    )
    return {
        "token": token,
        "tipo": "Bearer",
        "vigencia_segundos": 3600,
        "usuario": {
            "sub": registro["sub"],
            "nombre": registro.get("nombre", ""),
            "email": registro["usuario"],
            "org_id": registro["org_id"],
            "grupos": registro["grupos"],
        },
    }


@app.get("/auth/yo", tags=["autenticacion"], summary="Identidad de la sesion vigente")
async def identidad_de_sesion(identidad: Identidad = Depends(identidad_actual)) -> dict:
    """Deja ver que grupos y que organizacion transporta el token en uso."""
    return {
        "sub": identidad.sub,
        "email": identidad.email,
        "org_id": identidad.org_id,
        "grupos": list(identidad.grupos),
    }


@app.get("/auth/organizaciones", tags=["autenticacion"], summary="Organizaciones aprovisionadas")
async def listar_organizaciones() -> dict:
    """Las organizaciones se aprovisionan con el despliegue, no se autogestionan.

    El registro autonomo de nuevas organizaciones esta excluido del alcance
    (apartado 8 del documento): pertenece a un modelo comercial que no forma
    parte del problema planteado.
    """
    return {"organizaciones": _cargar_directorio().get("organizaciones", [])}
