"""Almacenamiento y verificacion de contrasenas.

Se usa PBKDF2-HMAC-SHA256 de la biblioteca estandar con 600 000 iteraciones, que
es la cifra que OWASP recomienda para esa combinacion. La eleccion merece
explicacion, porque Argon2id seria mejor: resiste ataques con hardware dedicado
que PBKDF2 no resiste igual de bien.

No se usa Argon2 porque exige una dependencia compilada, y el paquete de una
funcion Lambda se construye para una plataforma distinta de la del equipo de
desarrollo. Una dependencia binaria mal compilada falla al desplegar, en el
entorno del laboratorio, con las credenciales caducando cada cuatro horas. La
biblioteca estandar no tiene ese problema.

La limitacion se declara: para un despliegue productivo, Argon2id con una imagen
de contenedor propia. El formato de almacenamiento lleva el algoritmo delante,
de modo que migrar es posible sin invalidar las contrasenas existentes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

ALGORITMO = "pbkdf2_sha256"

#: Coste de derivacion. 600 000 iteraciones es la cifra que OWASP recomienda
#: para PBKDF2-HMAC-SHA256.
#:
#: Es ajustable por variable de entorno con un unico proposito legitimo: las
#: pruebas derivan decenas de contrasenas y con el coste de produccion tardan
#: minutos, lo que hace que nadie las ejecute. Bajarlo en pruebas es seguro
#: porque lo que se verifica es el mecanismo -que la contrasena no se almacena
#: en claro, que la verificacion funciona, que el formato permite migrar- y no
#: el coste, que es un parametro.
#:
#: En cualquier entorno con datos reales debe quedarse en el valor por omision.
#: El formato de almacenamiento lleva las iteraciones delante, de modo que subir
#: el coste no invalida las contrasenas ya derivadas: se rederivan al entrar.
ITERACIONES = max(1_000, int(os.getenv("RASTRO_PBKDF2_ITERACIONES") or 600_000))
LONGITUD_SAL = 16
LONGITUD_CLAVE_DERIVADA = 32

#: Minimo de 12 caracteres. No se exigen simbolos: las reglas de composicion
#: producen contrasenas predecibles y no mas fuertes. Lo que aporta es longitud.
LONGITUD_MINIMA = 12
LONGITUD_MAXIMA = 200


class ContrasenaInvalida(ValueError):
    """La contrasena no cumple la politica y no debe llegar a almacenarse."""


def _codificar(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def _decodificar(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"))


def validar_politica(clave: str) -> None:
    """Comprueba la politica antes de derivar el hash."""
    if not isinstance(clave, str) or len(clave) < LONGITUD_MINIMA:
        raise ContrasenaInvalida(
            f"La contrasena debe tener al menos {LONGITUD_MINIMA} caracteres."
        )
    if len(clave) > LONGITUD_MAXIMA:
        # Sin tope, una entrada enorme convierte el derivado en una negacion de
        # servicio: el coste de PBKDF2 lo paga el servidor, no quien la envia.
        raise ContrasenaInvalida(
            f"La contrasena no puede exceder {LONGITUD_MAXIMA} caracteres."
        )
    if clave.strip() != clave:
        raise ContrasenaInvalida("La contrasena no puede empezar ni terminar con espacios.")


def derivar(clave: str, *, iteraciones: int = ITERACIONES) -> str:
    """Devuelve ``algoritmo$iteraciones$sal$hash``, todo en base64.

    El formato lleva el algoritmo y las iteraciones delante para poder subir el
    coste con el tiempo -o cambiar de algoritmo- sin invalidar lo almacenado:
    cada registro sabe con que parametros se derivo.
    """
    validar_politica(clave)
    sal = secrets.token_bytes(LONGITUD_SAL)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal, iteraciones, dklen=LONGITUD_CLAVE_DERIVADA
    )
    return f"{ALGORITMO}${iteraciones}${_codificar(sal)}${_codificar(derivado)}"


def verificar(clave: str, almacenado: str) -> bool:
    """Comprueba la contrasena en tiempo constante.

    Nunca lanza por un formato invalido: devuelve ``False``. Un registro
    corrupto no debe distinguirse de una contrasena incorrecta, porque la
    diferencia seria observable desde fuera.
    """
    try:
        algoritmo, iteraciones, sal, esperado = almacenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        derivado = hashlib.pbkdf2_hmac(
            "sha256",
            clave.encode("utf-8"),
            _decodificar(sal),
            int(iteraciones),
            dklen=LONGITUD_CLAVE_DERIVADA,
        )
        return hmac.compare_digest(derivado, _decodificar(esperado))
    except (ValueError, AttributeError, TypeError):
        return False


def necesita_rederivar(almacenado: str, *, iteraciones: int = ITERACIONES) -> bool:
    """Indica si el hash se derivo con parametros mas debiles que los actuales.

    Se comprueba al iniciar sesion, que es el unico momento en que el sistema
    tiene la contrasena en claro y puede rederivarla sin pedirsela al usuario.
    """
    try:
        algoritmo, iteraciones_almacenadas, _sal, _hash = almacenado.split("$")
    except (ValueError, AttributeError):
        return True
    return algoritmo != ALGORITMO or int(iteraciones_almacenadas) < iteraciones


#: Hash de una contrasena que no corresponde a nadie. Se verifica contra el
#: cuando el usuario no existe, para que el tiempo de respuesta sea el mismo que
#: con un usuario real: sin esto, medir la latencia permite enumerar cuentas.
_SENUELO = derivar("senuelo-para-igualar-el-tiempo-de-respuesta", iteraciones=ITERACIONES)


def verificar_senuelo(clave: str) -> bool:
    """Consume el mismo tiempo que una verificacion real y siempre falla."""
    verificar(clave or "", _SENUELO)
    return False
