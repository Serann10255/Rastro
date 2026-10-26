"""Estado del servidor en las pantallas: consultas con caché, refresco e
invalidación tras una escritura.

La interfaz web usa React Query para esto, y la razón sigue valiendo aquí: el
conductor trabaja con conectividad intermitente, y el reintento, la
invalidación después de escribir y el «recargando sin borrar lo que ya se ve»
tienen que estar en un solo sitio. Escritos a mano en cada pantalla es donde
aparecen las incoherencias.

Esto es lo mínimo de React Query que las pantallas usan, no una copia completa:

- `use_consulta` lee una clave, la guarda en el almacén de la sesión y, si se le
  pide, la refresca cada cierto tiempo mientras la pantalla esté montada.
- `Almacen.invalidar("envios", "tablero")` vuelve a pedir toda consulta abierta
  cuya clave empiece por esos nombres. Es lo que se llama tras una escritura.
- Solo se reintenta lo que puede resolverse solo: un 403 o un 404 no cambian
  por insistir.

El almacén es de la sesión (uno por página abierta), no del módulo: en el modo
web varios navegadores comparten el proceso.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import flet as ft

from comun.http import ErrorApi

Clave = tuple


class Almacen:
    def __init__(self) -> None:
        self._datos: dict[Clave, Any] = {}
        self._momentos: dict[Clave, float] = {}
        self._oyentes: dict[Clave, set[Callable[[], None]]] = {}

    def leer(self, clave: Clave) -> Any:
        return self._datos.get(clave)

    def guardar(self, clave: Clave, valor: Any) -> None:
        self._datos[clave] = valor
        self._momentos[clave] = time.monotonic()

    def edad(self, clave: Clave) -> float | None:
        momento = self._momentos.get(clave) if clave in self._datos else None
        return None if momento is None else time.monotonic() - momento

    def suscribir(self, clave: Clave, oyente: Callable[[], None]) -> Callable[[], None]:
        self._oyentes.setdefault(clave, set()).add(oyente)
        return lambda: self._oyentes.get(clave, set()).discard(oyente)

    def invalidar(self, *prefijos: str) -> None:
        """Vuelve a pedir las consultas abiertas cuya clave empieza por alguno
        de los prefijos, y olvida las cerradas para que no se muestren viejas."""
        for clave in list(self._datos):
            if clave and clave[0] in prefijos:
                del self._datos[clave]
                self._momentos.pop(clave, None)
        for clave, oyentes in list(self._oyentes.items()):
            if clave and clave[0] in prefijos:
                for oyente in list(oyentes):
                    oyente()

    def vaciar(self) -> None:
        self._datos.clear()
        self._momentos.clear()


def _reintentar(intentos: int, error: BaseException) -> bool:
    if isinstance(error, ErrorApi):
        if error.codigo == "SIN_CONEXION":
            return intentos < 3
        if 400 <= error.estado < 500:
            return False
    return intentos < 2


@dataclass
class Consulta:
    datos: Any
    error: BaseException | None
    cargando: bool
    """Todavía no hay datos que mostrar."""
    refrescando: bool
    """Se está pidiendo otra vez, con los datos anteriores aún en pantalla."""
    recargar: Callable[[], Any]


def use_consulta(
    almacen: Almacen,
    clave: Clave,
    funcion: Callable[[], Awaitable[Any]],
    *,
    habilitada: bool = True,
    intervalo: float | None = None,
    transformar: Callable[[Any, Any], Any] | None = None,
    vigencia: float | None = None,
) -> Consulta:
    """Lee `clave` con `funcion` y la mantiene al día.

    `transformar(previo, nuevo)` permite combinar la respuesta con lo que ya
    había, para las consultas que piden solo lo nuevo (el recorrido de una ruta).

    `vigencia` (segundos) evita volver a pedir al montar algo que cambia poco
    —el catálogo de estados, los módulos—: dentro de ella vale lo guardado.
    """
    estado, poner_estado = ft.use_state(
        lambda: {"datos": almacen.leer(clave), "error": None, "refrescando": False, "pedida": False}
    )
    # `use_ref` llama a su argumento si es una función: se envuelve para guardar
    # la función y no su resultado.
    funcion_ref = ft.use_ref(lambda: funcion)
    funcion_ref.current = funcion
    transformar_ref = ft.use_ref(lambda: transformar)
    transformar_ref.current = transformar

    async def cargar() -> None:
        poner_estado(lambda e: {**e, "refrescando": True})
        intentos = 0
        while True:
            try:
                nuevo = await funcion_ref.current()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - se muestra en la pantalla
                if _reintentar(intentos, error):
                    intentos += 1
                    await asyncio.sleep(min(2**intentos, 8))
                    continue
                poner_estado(lambda e, fallo=error: {**e, "error": fallo, "refrescando": False, "pedida": True})
                return
            previo = almacen.leer(clave)
            valor = transformar_ref.current(previo, nuevo) if transformar_ref.current else nuevo
            almacen.guardar(clave, valor)
            poner_estado(lambda e: {**e, "datos": valor, "error": None, "refrescando": False, "pedida": True})
            return

    async def ciclo() -> None:
        if not habilitada:
            return
        edad = almacen.edad(clave)
        if not (vigencia and edad is not None and edad < vigencia):
            await cargar()
        while intervalo:
            await asyncio.sleep(intervalo)
            await cargar()

    # La limpieza vacía es necesaria: sin ella Flet no cancela el ciclo al
    # desmontar la pantalla, y seguiría preguntando al servidor sin nadie mirando.
    ft.use_effect(ciclo, [clave, habilitada, intervalo], cleanup=lambda: None)

    def suscribir():
        return almacen.suscribir(clave, lambda: ft.context.page.run_task(cargar))

    ft.use_effect(suscribir, [clave])

    datos = estado["datos"] if estado["datos"] is not None else almacen.leer(clave)
    return Consulta(
        datos=datos,
        error=estado["error"],
        cargando=habilitada and datos is None and estado["error"] is None,
        refrescando=estado["refrescando"],
        recargar=lambda: ft.context.page.run_task(cargar),
    )


@dataclass
class Mutacion:
    ejecutar: Callable[..., Awaitable[Any]]
    pendiente: bool
    error: BaseException | None
    limpiar: Callable[[], None]


def use_mutacion(funcion: Callable[..., Awaitable[Any]]) -> Mutacion:
    """Una escritura con su estado: pendiente y último error. El error se
    muestra junto al formulario que lo produjo; por eso se guarda aquí y no se
    lanza a una notificación que desaparece."""
    estado, poner_estado = ft.use_state(lambda: {"pendiente": False, "error": None})
    # `use_ref` llama a su argumento si es una función: se envuelve para guardar
    # la función y no su resultado.
    funcion_ref = ft.use_ref(lambda: funcion)
    funcion_ref.current = funcion

    async def ejecutar(*args: Any, **kwargs: Any) -> Any:
        poner_estado({"pendiente": True, "error": None})
        try:
            resultado = await funcion_ref.current(*args, **kwargs)
        except Exception as error:
            poner_estado({"pendiente": False, "error": error})
            raise
        poner_estado({"pendiente": False, "error": None})
        return resultado

    return Mutacion(
        ejecutar=ejecutar,
        pendiente=estado["pendiente"],
        error=estado["error"],
        limpiar=lambda: poner_estado({"pendiente": False, "error": None}),
    )


@dataclass
class Formulario:
    valores: dict[str, Any]
    """Lo que se dibuja: los valores del último render."""
    actual: dict[str, Any]
    """Lo que leen los manejadores: siempre al día, aunque el render no lo esté."""
    poner: Callable[[str], Callable[[Any], None]]
    reemplazar: Callable[[dict[str, Any]], None]


def use_formulario(inicial: dict[str, Any]) -> Formulario:
    """El estado de un formulario.

    Un manejador que leyera el estado del último render podría enviar un valor
    viejo: si se pulsa Enter justo después de escribir, el evento de envío llega
    antes de que la pantalla se vuelva a dibujar con la última tecla. Por eso
    los manejadores leen `actual`, un diccionario que se actualiza en cada
    pulsación, y la pantalla dibuja `valores`.
    """
    valores, poner_valores = ft.use_state(lambda: dict(inicial))
    ref = ft.use_ref(lambda: dict(inicial))

    def poner(campo: str) -> Callable[[Any], None]:
        def cambiar(valor: Any) -> None:
            ref.current[campo] = valor
            poner_valores(dict(ref.current))

        return cambiar

    def reemplazar(nuevos: dict[str, Any]) -> None:
        ref.current.clear()
        ref.current.update(nuevos)
        poner_valores(dict(ref.current))

    return Formulario(valores=valores, actual=ref.current, poner=poner, reemplazar=reemplazar)
