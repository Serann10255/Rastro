"""Cliente del programa de auditoría.

Es la traducción de `cotejo/web/src/api/cliente.ts`. Habla con dos servicios
distintos y conviene tenerlo presente: la autenticación la resuelve el proveedor
de identidad de Rastro —el auditor es un usuario de la organización, no una
cuenta aparte— y todo lo demás lo atiende el programa de auditoría.

Hay una instancia por página abierta: en el modo web varios navegadores
comparten el proceso, y una sesión guardada en el módulo la verían todos. La
sesión vive en memoria y se pierde al cerrar la aplicación, como en la web se
pierde al cerrar la pestaña.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable
from urllib.parse import quote

from comun.http import ErrorApi, enviar, interpretar

POR_OMISION = {"entorno": "local", "url_cotejo": "", "url_rastro": ""}

SIN_SERVICIO = "No se pudo alcanzar el servicio. Compruebe que esté levantado."


class ClienteCotejo:
    def __init__(self, configuracion: dict[str, Any]) -> None:
        self.configuracion = configuracion
        self.sesion: dict[str, Any] | None = None
        self.al_cambiar_sesion: Callable[[dict[str, Any] | None], None] = lambda _sesion: None

    def _raiz(self, base: str) -> str:
        clave = "url_cotejo" if base == "cotejo" else "url_rastro"
        return str(self.configuracion.get(clave) or "").rstrip("/")

    async def peticion(
        self,
        ruta: str,
        *,
        metodo: str = "GET",
        cuerpo: Any = None,
        base: str = "cotejo",
        autenticada: bool = True,
        parametros: dict[str, Any] | None = None,
    ) -> Any:
        cabeceras: dict[str, str] = {}
        if autenticada:
            if not self.sesion:
                raise ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.")
            cabeceras["Authorization"] = f"Bearer {self.sesion['token']}"

        try:
            respuesta = await enviar(
                metodo, f"{self._raiz(base)}{ruta}", cuerpo=cuerpo, parametros=parametros, cabeceras=cabeceras
            )
        except ErrorApi as error:
            raise ErrorApi(0, "SIN_CONEXION", SIN_SERVICIO) from error

        try:
            return interpretar(respuesta)
        except ErrorApi:
            # Cotejo no renueva el token: dura una hora, más que una revisión.
            # Un 401 con sesión significa que caducó, y se vuelve a entrar.
            if respuesta.status_code == 401 and autenticada and self.sesion is not None:
                self.sesion = None
                self.al_cambiar_sesion(None)
            raise

    # -- Sesión -------------------------------------------------------------
    async def entrar(self, correo: str, clave: str) -> dict[str, Any]:
        """La autenticación va contra Rastro: el auditor es un usuario de la
        organización auditada, con el grupo `auditor`. Cotejo no mantiene su
        propio directorio de usuarios, y esa dependencia está declarada."""
        datos = await self.peticion(
            "/auth/token",
            metodo="POST",
            cuerpo={"correo": correo, "clave": clave},
            base="rastro",
            autenticada=False,
        )
        return {"token": datos["token"], "usuario": datos["usuario"], "emitida_en": time.time()}

    def salud(self):
        return self.peticion("/salud", autenticada=False)

    def catalogo(self):
        return self.peticion("/catalogo")

    def ejecuciones(self):
        return self.peticion("/ejecuciones")

    def ejecutar(self, solo: list[str] | None = None):
        """En local la respuesta trae la revisión terminada. En AWS solo la
        encarga —API Gateway corta a los 30 s y una revisión tarda más— y
        responde con su estado «en_curso»; `esperar_ejecucion` pregunta hasta
        que termina (ADR-015)."""
        return self.peticion("/ejecuciones", metodo="POST", cuerpo={"solo": solo})

    def estado_ejecucion(self, ejecucion_id: str):
        return self.peticion(f"/ejecuciones/{quote(ejecucion_id, safe='')}/estado")

    def ejecucion(self, ejecucion_id: str):
        return self.peticion(f"/ejecuciones/{quote(ejecucion_id, safe='')}")

    def informe_texto(self, ejecucion_id: str):
        return self.peticion(f"/ejecuciones/{quote(ejecucion_id, safe='')}/informe.txt")

    def papel(self, ejecucion_id: str, control_id: str):
        return self.peticion(
            f"/ejecuciones/{quote(ejecucion_id, safe='')}/papeles/{quote(control_id, safe='')}"
        )

    def verificar_almacen(self, ejecucion_id: str):
        return self.peticion(f"/ejecuciones/{quote(ejecucion_id, safe='')}/verificacion", metodo="POST")

    def comparar(self, a: str, b: str):
        return self.peticion("/comparacion", parametros={"a": a, "b": b})

    async def esperar_ejecucion(self, ejecucion_id: str) -> None:
        """Espera a que termine una revisión encargada. Pregunta cada tres
        segundos y se rinde a los seis minutos: la función que la ejecuta tiene
        cinco."""
        limite = time.monotonic() + 6 * 60
        while time.monotonic() < limite:
            await asyncio.sleep(3)
            estado = await self.estado_ejecucion(ejecucion_id)
            if estado.get("estado") == "lista":
                return
            if estado.get("estado") == "fallida":
                raise ErrorApi(500, "EJECUCION_FALLIDA", estado.get("motivo") or "La revisión no terminó.")
        raise ErrorApi(504, "SIN_RESPUESTA", "La revisión sigue sin terminar. Vuelva a mirar en unos minutos.")
