"""Cliente de la interfaz de programación de Rastro.

Es la traducción de `web/src/api/cliente.ts` y mantiene sus tres decisiones:

1. La dirección de la API sale de la configuración en tiempo de ejecución,
   nunca del código (REQ-09). Ver `comun/configuracion.py`.
2. La sesión se renueva sola: ante un 401 con sesión activa se pide un token
   nuevo con el refresco y se repite la petición **una** vez. Una sola
   renovación en curso, compartida por todas las peticiones que caduquen a la
   vez: el refresco se rota, y diez renovaciones simultáneas dejarían nueve
   inválidas y cerrarían la sesión de alguien que no hizo nada malo.
3. Los errores llegan como `ErrorApi` con el código de dominio.

Hay una instancia por página abierta. En el modo web, Flet atiende a varios
navegadores desde el mismo proceso de Python: una sesión guardada en una
variable del módulo la compartirían todos. Por eso nada de la sesión vive aquí
fuera de la instancia.

La sesión vive en memoria y se pierde al cerrar la aplicación, como en la web se
pierde al cerrar la pestaña: es lo deseado en un dispositivo que comparten
varios mensajeros. La ruta abierta no se pierde con ella: vive en el servidor y
se retoma al volver a entrar.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Callable
from urllib.parse import quote

from comun.http import ErrorApi, enviar, interpretar

POR_OMISION = {"entorno": "local", "region": "us-east-1", "url_publica_api": ""}


class ClienteRastro:
    def __init__(self, configuracion: dict[str, Any]) -> None:
        self.configuracion = configuracion
        self.sesion: dict[str, Any] | None = None
        self.al_cambiar_sesion: Callable[[dict[str, Any] | None], None] = lambda _sesion: None
        self._renovacion: asyncio.Future[dict[str, Any] | None] | None = None

    # -- Configuración -------------------------------------------------------
    @property
    def base(self) -> str:
        return str(self.configuracion.get("url_publica_api") or "").rstrip("/")

    # -- Peticiones ----------------------------------------------------------
    async def peticion(
        self,
        ruta: str,
        *,
        metodo: str = "GET",
        cuerpo: Any = None,
        autenticada: bool = True,
        parametros: dict[str, Any] | None = None,
        _ya_renovada: bool = False,
    ) -> Any:
        cabeceras: dict[str, str] = {}
        if autenticada:
            if not self.sesion:
                raise ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.")
            cabeceras["Authorization"] = f"Bearer {self.sesion['token']}"

        respuesta = await enviar(
            metodo, f"{self.base}{ruta}", cuerpo=cuerpo, parametros=parametros, cabeceras=cabeceras
        )

        # Token caducado: se renueva y se repite la petición una sola vez.
        if respuesta.status_code == 401 and autenticada and not _ya_renovada:
            if await self._renovar():
                return await self.peticion(
                    ruta,
                    metodo=metodo,
                    cuerpo=cuerpo,
                    autenticada=autenticada,
                    parametros=parametros,
                    _ya_renovada=True,
                )
            self._cerrar_local()

        try:
            return interpretar(respuesta)
        except ErrorApi:
            # Solo se cierra la sesión si la petición llevaba token. Un 401 de
            # una ruta abierta —el propio inicio de sesión— significa que el
            # servidor rechazó unas credenciales, no que la sesión caducó.
            if respuesta.status_code == 401 and autenticada:
                self._cerrar_local()
            raise

    async def _renovar(self) -> dict[str, Any] | None:
        if self._renovacion is not None:
            return await self._renovacion

        bucle = asyncio.get_running_loop()
        self._renovacion = bucle.create_future()
        renovada: dict[str, Any] | None = None
        try:
            refresco = (self.sesion or {}).get("refresco")
            if refresco:
                respuesta = await enviar("POST", f"{self.base}/auth/refrescar", cuerpo={"refresco": refresco})
                if respuesta.is_success:
                    renovada = {**respuesta.json(), "emitida_en": time.time()}
                    self.sesion = renovada
                    self.al_cambiar_sesion(renovada)
        except ErrorApi:
            renovada = None
        finally:
            self._renovacion.set_result(renovada)
            self._renovacion = None
        return renovada

    def _cerrar_local(self) -> None:
        if self.sesion is not None:
            self.sesion = None
            self.al_cambiar_sesion(None)

    # -- Sesión ---------------------------------------------------------------
    async def entrar(self, correo: str, clave: str) -> dict[str, Any]:
        datos = await self.peticion(
            "/auth/token", metodo="POST", cuerpo={"correo": correo, "clave": clave}, autenticada=False
        )
        self.sesion = {**datos, "emitida_en": time.time()}
        return self.sesion

    async def salir(self, todas: bool = False) -> None:
        """Revoca la sesión en el servidor antes de olvidarla aquí: al revés, ya
        no habría con qué autenticar el cierre."""
        try:
            await self.peticion("/auth/salir", metodo="POST", parametros={"todas": str(todas).lower()})
        except ErrorApi:
            pass  # Sin conexión el cierre local sigue teniendo sentido.
        self.sesion = None

    def yo(self):
        return self.peticion("/auth/yo")

    def cambiar_clave(self, actual: str, nueva: str):
        return self.peticion("/auth/clave", metodo="POST", cuerpo={"clave_actual": actual, "clave_nueva": nueva})

    # -- Roles, usuarios y empresa --------------------------------------------
    def catalogo_de_operaciones(self):
        return self.peticion("/auth/roles", autenticada=False)

    def roles(self):
        return self.peticion("/roles")

    def crear_rol(self, datos: dict[str, Any]):
        return self.peticion("/roles", metodo="POST", cuerpo=datos)

    def actualizar_rol(self, clave: str, datos: dict[str, Any]):
        return self.peticion(f"/roles/{quote(clave, safe='')}", metodo="POST", cuerpo=datos)

    def eliminar_rol(self, clave: str):
        return self.peticion(f"/roles/{quote(clave, safe='')}/eliminar", metodo="POST")

    def usuarios(self):
        return self.peticion("/usuarios")

    def crear_usuario(self, datos: dict[str, Any]):
        return self.peticion("/usuarios", metodo="POST", cuerpo=datos)

    def actualizar_usuario(self, correo: str, cambios: dict[str, Any]):
        return self.peticion(f"/usuarios/{quote(correo, safe='')}", metodo="POST", cuerpo=cambios)

    def empresa(self):
        return self.peticion("/empresa")

    def mensajeros(self):
        """A quién se puede asignar un envío. Sale del directorio de la empresa,
        no de una lista escrita aquí."""
        return self.peticion("/equipo/mensajeros")

    # -- Tablero y catálogos ---------------------------------------------------
    def tablero(self, dias: int = 30):
        return self.peticion("/tablero", parametros={"dias": dias})

    def catalogo_estados(self):
        return self.peticion("/catalogos/estados", autenticada=False)

    def modulos(self):
        return self.peticion("/catalogos/modulos")

    def actualizar_modulo(self, clave: str, disponible: bool, motivo: str):
        return self.peticion(
            f"/catalogos/modulos/{quote(clave, safe='')}",
            metodo="POST",
            cuerpo={"disponible": disponible, "motivo": motivo},
        )

    # -- Datos maestros: una sola forma para los tres recursos ----------------
    def maestros(self, recurso: str):
        return self.peticion(f"/{recurso}")

    def guardar_maestro(self, recurso: str, identificador: str | None, datos: dict[str, Any]):
        ruta = f"/{recurso}/{identificador}" if identificador else f"/{recurso}"
        return self.peticion(ruta, metodo="POST", cuerpo=datos)

    def eliminar_maestro(self, recurso: str, identificador: str):
        return self.peticion(f"/{recurso}/{identificador}/eliminar", metodo="POST")

    # -- Envíos ------------------------------------------------------------------
    def listar_envios(self, limite: int = 500):
        return self.peticion("/envios", parametros={"limite": limite})

    def consultar_envio(self, envio_id: str):
        return self.peticion(f"/envios/{envio_id}")

    def crear_envio(self, datos: dict[str, Any]):
        return self.peticion("/envios", metodo="POST", cuerpo=datos)

    def crear_lote(self, envios: list[dict[str, Any]]):
        return self.peticion("/envios/lote", metodo="POST", cuerpo={"envios": envios})

    def asignar_conductor(self, envio_id: str, sub: str, nombre: str):
        return self.peticion(
            f"/envios/{envio_id}/asignacion",
            metodo="POST",
            cuerpo={"conductor_sub": sub, "conductor_nombre": nombre},
        )

    def etiquetas(self, envios: list[str]):
        return self.peticion("/envios/etiquetas", metodo="POST", cuerpo={"envios": envios})

    async def exportar_envios(self) -> tuple[str, bytes]:
        """El CSV de exportación y el nombre que propone el servidor."""
        if not self.sesion:
            raise ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.")
        respuesta = await enviar(
            "GET",
            f"{self.base}/envios/exportar",
            cabeceras={"Authorization": f"Bearer {self.sesion['token']}"},
        )
        if not respuesta.is_success:
            interpretar(respuesta)
        nombre = re.search(r'filename="([^"]+)"', respuesta.headers.get("content-disposition", ""))
        return (nombre.group(1) if nombre else "envios.csv"), respuesta.content

    # -- Rastreo y evidencias ------------------------------------------------------
    def transiciones(self, envio_id: str):
        return self.peticion(f"/envios/{envio_id}/transiciones")

    def registrar_evento(self, envio_id: str, datos: dict[str, Any]):
        return self.peticion(f"/envios/{envio_id}/eventos", metodo="POST", cuerpo=datos)

    def solicitar_enlace(self, envio_id: str, nombre_archivo: str, tipo_contenido: str):
        return self.peticion(
            f"/envios/{envio_id}/evidencias",
            metodo="POST",
            cuerpo={"nombre_archivo": nombre_archivo, "tipo_contenido": tipo_contenido},
        )

    def confirmar_evidencia(self, envio_id: str, evidencia_id: str, tipo_contenido: str):
        return self.peticion(
            f"/envios/{envio_id}/evidencias/{evidencia_id}/confirmacion",
            metodo="POST",
            parametros={"tipo_contenido": tipo_contenido},
        )

    def listar_evidencias(self, envio_id: str):
        return self.peticion(f"/envios/{envio_id}/evidencias")

    @staticmethod
    async def cargar_evidencia(enlace: dict[str, Any], contenido: bytes) -> None:
        """El archivo va directo al almacenamiento con el enlace prefirmado: no
        atraviesa los servicios."""
        try:
            respuesta = await enviar(
                enlace.get("metodo", "PUT"),
                enlace["url"],
                cabeceras=enlace.get("encabezados") or {},
                contenido=contenido,
            )
        except ErrorApi as error:
            raise ErrorApi(0, "SIN_CONEXION", "No se pudo alcanzar el almacenamiento. Compruebe la red.") from error
        if not respuesta.is_success:
            raise ErrorApi(
                respuesta.status_code,
                "SOLICITUD_INVALIDA",
                f"El enlace expiró (vigencia de {enlace.get('vigencia_segundos')} s). Solicite uno nuevo."
                if respuesta.status_code == 403
                else f"El almacenamiento rechazó la carga con código {respuesta.status_code}.",
            )

    # -- Bitácora -----------------------------------------------------------------------
    def bitacora(self, resultado: str | None = None, limite: int = 1000):
        return self.peticion("/bitacora", parametros={"resultado": resultado, "limite": limite})

    def verificar_bitacora(self):
        return self.peticion("/bitacora/verificacion")

    # -- Rutas de entrega ---------------------------------------------------------
    # Las lecturas devuelven un `testigo`: la prueba firmada de que la consulta
    # ya quedó en la bitácora. Devolverlo en la siguiente evita que cada
    # refresco del mapa deje un eslabón.
    def iniciar_ruta(self, envios: list[str], ubicacion: dict[str, Any] | None):
        return self.peticion("/rutas", metodo="POST", cuerpo={"envios": envios, "ubicacion": ubicacion})

    def ruta_activa(self, testigo: str | None = None):
        return self.peticion("/rutas/activa", parametros={"testigo": testigo})

    def rutas(self, estado: str, testigo: str | None = None):
        return self.peticion("/rutas", parametros={"estado": estado, "testigo": testigo})

    def ruta(self, ruta_id: str, desde: str | None = None, testigo: str | None = None):
        return self.peticion(f"/rutas/{ruta_id}", parametros={"desde": desde, "testigo": testigo})

    def reportar_posiciones(self, ruta_id: str, posiciones: list[dict[str, Any]]):
        return self.peticion(f"/rutas/{ruta_id}/posiciones", metodo="POST", cuerpo={"posiciones": posiciones})

    def finalizar_ruta(self, ruta_id: str, nota: str = ""):
        return self.peticion(f"/rutas/{ruta_id}/finalizacion", metodo="POST", cuerpo={"nota": nota})

    # -- Consulta pública: sin token, por diseño -------------------------------------
    def consulta_publica(self, envio_id: str):
        return self.peticion(f"/publico/envios/{envio_id}", autenticada=False)

    def ubicacion_publica(self, envio_id: str):
        return self.peticion(f"/publico/envios/{envio_id}/ubicacion", autenticada=False)
