"""Ubicación del conductor: lecturas sueltas y transmisión en el modo ruta.

Es la traducción de `web/src/api/transmision.ts`, con las mismas reglas:

- **Una lectura cada quince segundos**, o antes si el vehículo se movió cien
  metros en cinco. Basta para ver el punto avanzar sin gastar los datos ni la
  batería del conductor.
- **Las lecturas se guardan si no hay señal** y se envían juntas al volver,
  hasta 240 (una hora de recorrido), en lotes de 60.
- **Si el vehículo está quieto, se pide una lectura fresca** en lugar de
  repetir la última: repetirla diría «estoy aquí ahora» con una medición vieja.
- **Si la ruta terminó en el servidor (409), se deja de transmitir.**

La diferencia está en el teléfono. El navegador detiene la página con la
pantalla apagada (ADR-013); la aplicación instalada en Android pide a sistema un
servicio en primer plano, con su notificación permanente, y sigue transmitiendo
con la pantalla apagada mientras la ruta esté abierta. La notificación no es
decorativa: compartir la ubicación de una persona es algo que esa persona tiene
que ver que está pasando.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any, Callable

import flet as ft
import flet_geolocator as ftg

from comun.http import ErrorApi

INTERVALO_ENVIO = 15.0
INTERVALO_MOVIMIENTO = 5.0
DISTANCIA_ADELANTO_M = 100.0
# Una lectura peor que esto es la de una antena, no la de un GPS.
PRECISION_UTIL_M = 500.0
MAX_PENDIENTES = 240
MAX_POR_ENVIO = 60
MAX_RECORRIDO = 2000


def distancia_metros(a: dict[str, float], b: dict[str, float]) -> float:
    """Distancia por la fórmula del haverseno."""
    radio = 6_371_000
    rad = math.radians
    d_lat = rad(b["lat"] - a["lat"])
    d_lon = rad(b["lon"] - a["lon"])
    h = math.sin(d_lat / 2) ** 2 + math.cos(rad(a["lat"])) * math.cos(rad(b["lat"])) * math.sin(d_lon / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(h))


def lectura_desde(posicion: ftg.GeolocatorPosition) -> dict[str, Any]:
    marca = posicion.timestamp if isinstance(posicion.timestamp, datetime) else datetime.now(timezone.utc)
    if marca.tzinfo is None:
        marca = marca.replace(tzinfo=timezone.utc)
    lectura: dict[str, Any] = {
        "lat": posicion.latitude,
        "lon": posicion.longitude,
        "precision_m": round(posicion.accuracy or 0, 1),
        "capturada_en": marca.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # El rumbo y la velocidad solo existen en movimiento; quieto llegan
    # negativos o nulos, y enviarlos haría fallar la validación del servidor.
    if posicion.heading is not None and math.isfinite(posicion.heading) and posicion.heading >= 0:
        lectura["rumbo"] = round(posicion.heading)
    if posicion.speed is not None and math.isfinite(posicion.speed) and posicion.speed >= 0:
        lectura["velocidad"] = round(posicion.speed, 1)
    return lectura


def mensaje_fallo(motivo: str, web: bool) -> tuple[str, str]:
    """Título y explicación de un fallo de ubicación. Dónde se arregla el permiso
    depende de dónde corre la aplicación: en el navegador o en el teléfono."""
    if motivo == "sin_permiso":
        donde = "los ajustes del navegador para este sitio" if web else "los ajustes del teléfono para Rastro"
        return (
            "La ubicación está bloqueada" + (" para este sitio" if web else " para esta aplicación"),
            "El modo ruta existe para compartir dónde va el vehículo, y sin ubicación no puede iniciarse. "
            f"Permítala en {donde} y vuelva a intentarlo. Mientras tanto, puede registrar las entregas una a "
            "una desde Mis envíos.",
        )
    return MENSAJE_FALLO[motivo]


MENSAJE_FALLO = {
    "sin_gps": ("Todavía no hay señal GPS", "Salga a cielo abierto un momento y vuelva a intentarlo."),
    "no_compatible": (
        "Este equipo no entrega la ubicación",
        "Salga a ruta desde la aplicación del teléfono o desde el navegador del teléfono.",
    ),
}


class Gps:
    """El servicio de ubicación de la página. Se crea al primer uso, dentro del
    contexto de la página, y se reutiliza: cada instancia es un servicio más
    registrado en el cliente."""

    def __init__(self) -> None:
        self._servicio: ftg.Geolocator | None = None

    def servicio(self) -> ftg.Geolocator:
        if self._servicio is None:
            self._servicio = ftg.Geolocator()
        return self._servicio

    @staticmethod
    def configuracion(continua: bool) -> ftg.GeolocatorConfiguration:
        pagina = ft.context.page
        if continua and pagina.platform == ft.PagePlatform.ANDROID and not pagina.web:
            return ftg.GeolocatorAndroidConfiguration(
                accuracy=ftg.GeolocatorPositionAccuracy.HIGH,
                distance_filter=5,
                interval_duration=ft.Duration(seconds=INTERVALO_MOVIMIENTO),
                foreground_notification_config=ftg.ForegroundNotificationConfiguration(
                    notification_title="Rastro: ruta en curso",
                    notification_text="Su ubicación se comparte con la empresa mientras la ruta esté abierta.",
                    notification_channel_name="Ruta en curso",
                    notification_enable_wake_lock=True,
                    notification_set_ongoing=True,
                ),
            )
        return ftg.GeolocatorConfiguration(accuracy=ftg.GeolocatorPositionAccuracy.HIGH, distance_filter=5)

    async def permiso(self) -> str | None:
        """None si hay permiso; si no, el motivo («sin_permiso», «no_compatible»).

        Distingue la negación del permiso de la falta de señal: lo primero lo
        arregla el conductor en los ajustes; lo segundo, saliendo a cielo
        abierto. Un solo mensaje para los dos no ayudaría con ninguno."""
        try:
            geo = self.servicio()
            estado = await asyncio.wait_for(geo.get_permission_status(), 8)
            if estado == ftg.GeolocatorPermissionStatus.DENIED:
                estado = await asyncio.wait_for(geo.request_permission(), 60)
        except (asyncio.TimeoutError, ft.FletUnsupportedPlatformException, RuntimeError, Exception):  # noqa: BLE001
            return "no_compatible"
        if estado in (ftg.GeolocatorPermissionStatus.DENIED, ftg.GeolocatorPermissionStatus.DENIED_FOREVER):
            return "sin_permiso"
        return None

    async def leer(self, espera: float = 15) -> tuple[dict[str, Any] | None, str | None]:
        """Una lectura única, para salir a ruta o para adjuntar a un evento.
        Devuelve (lectura, None) o (None, motivo del fallo)."""
        fallo = await self.permiso()
        if fallo:
            return None, fallo
        try:
            configuracion = ftg.GeolocatorConfiguration(
                accuracy=ftg.GeolocatorPositionAccuracy.HIGH, time_limit=ft.Duration(seconds=int(espera))
            )
            posicion = await asyncio.wait_for(self.servicio().get_current_position(configuracion), espera + 3)
        except asyncio.TimeoutError:
            return None, "sin_gps"
        except Exception:  # noqa: BLE001 - servicio desactivado o sin señal
            return None, "sin_gps"
        if posicion.latitude is None or posicion.longitude is None:
            return None, "sin_gps"
        return lectura_desde(posicion), None


class Transmisor:
    """La transmisión de una ruta abierta. Vive lo que vive la pantalla del modo
    ruta; al desmontarse, deja de escuchar el GPS."""

    def __init__(
        self,
        pagina: ft.Page,
        api: Any,
        gps: Gps,
        ruta_id: str,
        al_cambiar: Callable[[dict[str, Any]], None],
        al_terminar_la_ruta: Callable[[], None],
    ) -> None:
        self.pagina = pagina
        self.api = api
        self.gps = gps
        self.ruta_id = ruta_id
        self.al_cambiar = al_cambiar
        self.al_terminar_la_ruta = al_terminar_la_ruta
        self.cola: list[dict[str, Any]] = []
        self.en_curso = False
        self.ultima_encolada: tuple[dict[str, Any], float] | None = None
        self.ultima_lectura: tuple[dict[str, Any], float] | None = None
        self.estado: dict[str, Any] = {
            "estado": "preparando",
            "posicion": None,
            "recorrido": [],
            "ultimo_envio": None,
            "pendientes": 0,
            "sin_conexion": False,
        }

    def _publicar(self, **cambios: Any) -> None:
        self.estado = {**self.estado, **cambios}
        self.al_cambiar(self.estado)

    async def enviar(self) -> None:
        if self.en_curso or not self.cola:
            return
        self.en_curso = True
        lote = self.cola[:MAX_POR_ENVIO]
        try:
            await self.api.reportar_posiciones(self.ruta_id, lote)
            self.cola = self.cola[len(lote) :]
            self._publicar(ultimo_envio=time.time(), sin_conexion=False)
        except ErrorApi as error:
            if error.codigo == "CONFLICTO":
                # La ruta se cerró en otro lado: no queda a quién reportar.
                self.cola = []
                self._publicar(estado="detenida")
                self.al_terminar_la_ruta()
            elif error.codigo == "SIN_CONEXION" or error.estado >= 500:
                self._publicar(sin_conexion=True)
            else:
                # Un rechazo de validación no se arregla reintentando: se
                # descarta el lote para que no bloquee a los siguientes.
                self.cola = self.cola[len(lote) :]
        finally:
            self.en_curso = False
            self._publicar(pendientes=len(self.cola))

    def al_leer(self, lectura: dict[str, Any]) -> None:
        ahora = time.monotonic()
        self.ultima_lectura = (lectura, ahora)
        cambios: dict[str, Any] = {"posicion": lectura, "estado": "transmitiendo"}
        if (lectura.get("precision_m") or 0) > PRECISION_UTIL_M:
            self._publicar(**cambios)
            return

        recorrido = self.estado["recorrido"]
        if not recorrido or distancia_metros({"lat": recorrido[-1][0], "lon": recorrido[-1][1]}, lectura) >= 5:
            cambios["recorrido"] = [*recorrido, (lectura["lat"], lectura["lon"])][-MAX_RECORRIDO:]
        self._publicar(**cambios)

        previa = self.ultima_encolada
        transcurrido = ahora - previa[1] if previa else math.inf
        recorrida = distancia_metros(previa[0], lectura) if previa else math.inf
        if transcurrido >= INTERVALO_ENVIO or (transcurrido >= INTERVALO_MOVIMIENTO and recorrida >= DISTANCIA_ADELANTO_M):
            self.cola = [*self.cola, lectura][-MAX_PENDIENTES:]
            self.ultima_encolada = (lectura, ahora)
            self._publicar(pendientes=len(self.cola))
            self.pagina.run_task(self.enviar)

    async def correr(self) -> None:
        fallo = await self.gps.permiso()
        if fallo:
            self._publicar(estado=fallo)
            return
        geo = self.gps.servicio()

        def al_cambiar_posicion(evento: ftg.GeolocatorPositionChangeEvent) -> None:
            if evento.position and evento.position.latitude is not None:
                self.al_leer(lectura_desde(evento.position))

        geo.configuration = Gps.configuracion(continua=True)
        geo.on_position_change = al_cambiar_posicion
        geo.on_error = lambda _e: self._publicar(estado="sin_gps")
        geo.update()
        try:
            # El pulso: reintenta lo pendiente y, si el vehículo está quieto y
            # el GPS no entrega lecturas nuevas, pide una.
            while True:
                await asyncio.sleep(INTERVALO_MOVIMIENTO)
                ultima = self.ultima_lectura
                if not ultima or time.monotonic() - ultima[1] >= INTERVALO_ENVIO:
                    lectura, motivo = await self.gps.leer(espera=12)
                    if lectura:
                        self.al_leer(lectura)
                    elif motivo and self.estado["estado"] != "transmitiendo":
                        self._publicar(estado=motivo)
                await self.enviar()
        finally:
            self.detener()

    def detener(self) -> None:
        geo = self.gps.servicio()
        if geo.on_position_change is not None:
            geo.on_position_change = None
            geo.on_error = None
            try:
                geo.update()
            except Exception:  # noqa: BLE001 - la página puede estar cerrándose
                pass
