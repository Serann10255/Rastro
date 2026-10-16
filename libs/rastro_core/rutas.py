"""Rutas de entrega: el conductor sale con sus guias y comparte su ubicacion.

Una ruta es el recorrido de un conductor con las guias que eligio entregar. Al
iniciarla, cada envio pasa a EN_REPARTO por los caminos que la maquina de
estados ya admite, y mientras la ruta esta abierta el telefono del conductor
envia su posicion. Esa posicion la ven la empresa, en el mapa de seguimiento, y
el destinatario de cada envio en reparto, en la consulta publica.

Lo que este modulo decide, y por que vive aqui y no en un servicio:

- **Que envios pueden salir a ruta.** Solo los que el conductor ya tiene en su
  poder: recolectados, en transito o en reparto. Uno asignado y no recogido no
  esta en el vehiculo; uno detenido por incidencia espera una autorizacion que
  el conductor no puede darse.
- **Como llega cada uno a EN_REPARTO.** Recorriendo el flujo principal, paso a
  paso. No se abre un atajo en la maquina de estados: salir a ruta afirma dos
  hechos -el paquete se mueve y va en ultima milla- y cada uno queda como su
  propio evento, validado igual que si el conductor lo marcara a mano.
- **Que hora vale para una posicion.** La del telefono sirve para ordenar las
  lecturas que llegan atrasadas, pero es manipulable; se acepta solo dentro de
  un intervalo verosimil y se anota siempre la del servidor.
- **Que ve el destinatario.** La posicion, redondeada, y su antiguedad. Ni el
  nombre del conductor ni sus otras paradas: la consulta publica muestra el
  avance del envio, no la operacion de la empresa (REQ-04).

La ubicacion de un trabajador es un dato personal (Ley 1581 de 2012). Por eso
se comparte solo mientras hay una ruta abierta, deja de mostrarse al publico en
cuanto envejece, y el recorrido se conserva un tiempo acotado.
"""

from __future__ import annotations

import datetime as _dt
from enum import StrEnum
from typing import Any

from .errors import ValidacionError
from .ids import ahora_utc, marca_tiempo, nuevo_id_ruta
from .state_machine import ESTADOS_FINALES, FLUJO_PRINCIPAL, Estado, codigo_de


class EstadoRuta(StrEnum):
    ACTIVA = "ACTIVA"
    FINALIZADA = "FINALIZADA"


#: Los envios que el conductor tiene en su poder y puede llevar a la entrega.
ESTADOS_APTOS_PARA_RUTA: frozenset[Estado] = frozenset(
    {Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO}
)

#: Cuanto tiempo se le muestra al destinatario la ultima posicion conocida.
#: Pasado ese tiempo la posicion ya no dice donde esta el paquete, solo donde
#: estuvo el conductor, y mostrarla seria exponerlo sin informar a nadie.
VIGENCIA_PUBLICA_SEGUNDOS = 600

#: Umbrales de la senal que ve la empresa. Con una lectura cada quince segundos,
#: un minuto sin datos ya es un hueco; cinco, una perdida de cobertura.
SENAL_EN_LINEA_SEGUNDOS = 60
SENAL_ATRASADA_SEGUNDOS = 300

#: Cuanto se conserva el recorrido. Es tiempo suficiente para atender un reclamo
#: sobre una entrega; pasado ese plazo, la finalidad que justificaba guardar la
#: ubicacion de una persona se agoto. Lo aplica el propio almacenamiento.
RETENCION_RECORRIDO_DIAS = 30

#: Desfase admitido entre el reloj del telefono y el del servidor.
TOLERANCIA_RELOJ_SEGUNDOS = 120

#: Cuanto se espera antes de dar por abandonado el testigo de una ruta que no
#: llego a guardarse. Mientras una ruta se inicia, su testigo existe y ella
#: todavia no: sin este margen, un segundo toque en el boton veria el testigo
#: sin ruta, lo creeria huerfano y abriria una segunda.
TESTIGO_HUERFANO_SEGUNDOS = 60

#: Posiciones devueltas por consulta. A una cada quince segundos, son mas de
#: seis horas de recorrido.
MAX_POSICIONES_POR_CONSULTA = 1500

#: Decimales de la posicion publica: cuatro son unos once metros, suficiente
#: para ver que el vehiculo se acerca y no tanto como para seguir a una persona.
DECIMALES_POSICION_PUBLICA = 4


# --------------------------------------------------------------------------- #
# Inicio de la ruta
# --------------------------------------------------------------------------- #


def camino_a_reparto(estado: Estado | str) -> tuple[Estado, ...]:
    """Los estados que hay que registrar para llevar un envio a EN_REPARTO.

    Se deriva del flujo principal y no de una lista propia: si manana se
    intercala un estado entre EN_TRANSITO y EN_REPARTO, la ruta lo recorre sin
    tocar este archivo. Cada paso lo valida despues la maquina de estados.
    """
    estado = Estado(estado)
    if estado not in ESTADOS_APTOS_PARA_RUTA:
        raise ValidacionError(
            f"Un envio en {estado} no puede salir a ruta.",
            {"estado": str(estado), "aptos": sorted(str(e) for e in ESTADOS_APTOS_PARA_RUTA)},
        )
    desde = FLUJO_PRINCIPAL.index(estado)
    hasta = FLUJO_PRINCIPAL.index(Estado.EN_REPARTO)
    return FLUJO_PRINCIPAL[desde + 1 : hasta + 1]


def construir_parada(envio: dict, orden: int) -> dict[str, Any]:
    """Lo que el conductor necesita para entregar sin abrir cada envio.

    Es una copia y no una referencia, como el nombre de la tienda en el envio:
    la ruta es el documento de un recorrido, y si manana se corrige una
    direccion, la ruta tiene que seguir diciendo a donde fue el conductor.
    """
    destino = envio.get("destino") or {}
    destinatario = envio.get("destinatario") or {}
    return {
        "envio_id": envio["envio_id"],
        "orden": orden,
        "estado": str(envio["estado"]),
        "codigo_estado": codigo_de(envio["estado"]),
        "destinatario": destinatario.get("nombre", ""),
        "telefono": destinatario.get("telefono", ""),
        "direccion": destino.get("linea", ""),
        "referencia": destino.get("referencia", ""),
        "ciudad": destino.get("ciudad", ""),
        "orden_compra": envio.get("orden_compra", ""),
        "bultos": envio.get("bultos", 1),
        "descripcion": envio.get("descripcion", ""),
        "actualizada_en": marca_tiempo(),
    }


def construir_ruta(
    *, org_id: str, conductor_sub: str, conductor_nombre: str, envios: list[dict]
) -> dict[str, Any]:
    ahora = marca_tiempo()
    return {
        "ruta_id": nuevo_id_ruta(),
        "org_id": org_id,
        "estado": str(EstadoRuta.ACTIVA),
        "conductor_sub": conductor_sub,
        "conductor_nombre": conductor_nombre,
        "iniciada_en": ahora,
        "actualizada_en": ahora,
        "finalizada_en": None,
        "cierre": None,
        "nota_cierre": "",
        "paradas": [construir_parada(envio, indice + 1) for indice, envio in enumerate(envios)],
        "ultima_posicion": None,
        "posiciones": 0,
    }


# --------------------------------------------------------------------------- #
# Posiciones
# --------------------------------------------------------------------------- #


def _leer_hora(valor: str | None) -> _dt.datetime | None:
    if not valor:
        return None
    try:
        hora = _dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    if hora.tzinfo is None:
        return None
    return hora.astimezone(_dt.timezone.utc)


def _escribir_hora(hora: _dt.datetime) -> str:
    """El mismo formato que ``marca_tiempo``: ordenable como texto."""
    return hora.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def normalizar_posicion(
    posicion: dict, *, iniciada_en: str, ahora: _dt.datetime | None = None
) -> dict[str, Any]:
    """Prepara una lectura del telefono para guardarla.

    La hora del dispositivo se respeta si es verosimil -posterior al inicio de
    la ruta y no adelantada al servidor-, porque es lo unico que ordena bien un
    lote de lecturas enviado tras recuperar la senal. Si no lo es, se usa la de
    recepcion y se deja dicho en ``hora_de``: una hora que no se pudo creer no
    debe parecer una hora medida.
    """
    ahora = ahora or ahora_utc()
    recibida_en = _escribir_hora(ahora)
    tolerancia = _dt.timedelta(seconds=TOLERANCIA_RELOJ_SEGUNDOS)
    inicio = _leer_hora(iniciada_en)

    capturada = _leer_hora(posicion.get("capturada_en"))
    verosimil = (
        capturada is not None
        and capturada <= ahora + tolerancia
        and (inicio is None or capturada >= inicio - tolerancia)
    )

    normalizada: dict[str, Any] = {
        "lat": float(posicion["lat"]),
        "lon": float(posicion["lon"]),
        "capturada_en": _escribir_hora(min(capturada, ahora)) if verosimil else recibida_en,
        "recibida_en": recibida_en,
        "hora_de": "dispositivo" if verosimil else "servidor",
    }
    for campo in ("precision_m", "rumbo", "velocidad"):
        if posicion.get(campo) is not None:
            normalizada[campo] = round(float(posicion[campo]), 1)
    return normalizada


def posterior_a(anterior: str | None) -> str:
    """La hora del servidor, o un milisegundo despues de ``anterior`` si no la supera.

    Al salir a ruta, un envio recolectado registra dos eventos seguidos -en
    transito y en reparto- y los dos caen en el mismo milisegundo. El historico
    se ordena por la marca de tiempo, y con dos iguales el desempate es el
    sufijo aleatorio del evento: la mitad de las veces el envio apareceria en
    reparto antes de salir. Separarlos un milisegundo conserva el orden en que
    ocurrieron sin inventar una hora que no paso.
    """
    # Se compara a la resolucion con que se escribe: dos horas distintas en
    # microsegundos pueden ser la misma en milisegundos.
    ahora = ahora_utc()
    ahora = ahora.replace(microsecond=ahora.microsecond // 1000 * 1000)
    previa = _leer_hora(anterior)
    if previa is not None and ahora <= previa:
        ahora = previa + _dt.timedelta(milliseconds=1)
    return _escribir_hora(ahora)


def expiracion_del_recorrido(ahora: _dt.datetime | None = None) -> int:
    """Segundos de epoca en que el almacenamiento puede borrar la posicion."""
    ahora = ahora or ahora_utc()
    return int((ahora + _dt.timedelta(days=RETENCION_RECORRIDO_DIAS)).timestamp())


def la_mas_reciente(actual: dict | None, nuevas: list[dict]) -> dict | None:
    candidatas = [p for p in [actual, *nuevas] if p]
    if not candidatas:
        return None
    return max(candidatas, key=lambda p: (p.get("capturada_en", ""), p.get("recibida_en", "")))


# --------------------------------------------------------------------------- #
# Vistas
# --------------------------------------------------------------------------- #


def edad_en_segundos(iso: str | None, ahora: _dt.datetime | None = None) -> int | None:
    hora = _leer_hora(iso)
    if hora is None:
        return None
    ahora = ahora or ahora_utc()
    return max(0, int((ahora - hora).total_seconds()))


def senal(ruta: dict, ahora: _dt.datetime | None = None) -> dict[str, Any]:
    """Que tan reciente es la ultima posicion, dicho por el servidor.

    Se calcula aqui y no en el navegador porque el reloj del navegador de quien
    mira puede estar desfasado, y un «hace 3 horas» falso dispara una llamada
    al conductor que no hacia falta.
    """
    if ruta.get("estado") != EstadoRuta.ACTIVA:
        return {"estado": "cerrada", "edad_segundos": None}
    ultima = ruta.get("ultima_posicion") or {}
    edad = edad_en_segundos(ultima.get("capturada_en"), ahora)
    if edad is None:
        return {"estado": "sin_datos", "edad_segundos": None}
    if edad <= SENAL_EN_LINEA_SEGUNDOS:
        estado = "en_linea"
    elif edad <= SENAL_ATRASADA_SEGUNDOS:
        estado = "atrasada"
    else:
        estado = "sin_senal"
    return {"estado": estado, "edad_segundos": edad}


def resumen(ruta: dict) -> dict[str, int]:
    paradas = ruta.get("paradas") or []
    cerradas = [p for p in paradas if Estado(p["estado"]) in ESTADOS_FINALES]
    return {
        "total": len(paradas),
        "entregadas": sum(1 for p in paradas if p["estado"] == Estado.ENTREGADO),
        "incidencias": sum(1 for p in paradas if p["estado"] == Estado.INCIDENCIA),
        "cerradas": len(cerradas),
        "pendientes": len(paradas) - len(cerradas),
    }


def vista_ruta(ruta: dict, ahora: _dt.datetime | None = None) -> dict[str, Any]:
    return {**ruta, "resumen": resumen(ruta), "senal": senal(ruta, ahora)}


def ubicacion_publica(
    envio: dict, ruta: dict | None, ahora: _dt.datetime | None = None
) -> dict[str, Any]:
    """Lo que el destinatario ve de la ruta que lleva su envio.

    Solo la posicion y su antiguedad. Se entrega unicamente mientras su envio
    esta en reparto dentro de una ruta abierta y la posicion es reciente: en
    cualquier otro caso, la posicion de la persona que conduce no le dice nada
    sobre su paquete.
    """
    if Estado(envio.get("estado", Estado.CREADO)) is not Estado.EN_REPARTO:
        return {"disponible": False, "motivo": "no_en_reparto"}
    if not ruta or ruta.get("estado") != EstadoRuta.ACTIVA:
        return {"disponible": False, "motivo": "sin_ruta_activa"}
    if not any(p.get("envio_id") == envio.get("envio_id") for p in ruta.get("paradas") or []):
        return {"disponible": False, "motivo": "sin_ruta_activa"}

    ultima = ruta.get("ultima_posicion") or {}
    edad = edad_en_segundos(ultima.get("capturada_en"), ahora)
    if edad is None:
        return {"disponible": False, "motivo": "sin_senal"}
    if edad > VIGENCIA_PUBLICA_SEGUNDOS:
        return {"disponible": False, "motivo": "sin_senal", "edad_segundos": edad}

    posicion: dict[str, Any] = {
        "lat": round(float(ultima["lat"]), DECIMALES_POSICION_PUBLICA),
        "lon": round(float(ultima["lon"]), DECIMALES_POSICION_PUBLICA),
    }
    if ultima.get("precision_m") is not None:
        # Nunca por debajo de lo que se redondeo: anunciar 3 m de precision
        # sobre una coordenada recortada a 11 m seria prometer lo que no hay.
        posicion["precision_m"] = max(15, int(round(float(ultima["precision_m"]))))
    return {
        "disponible": True,
        "posicion": posicion,
        "actualizada_en": ultima.get("capturada_en"),
        "edad_segundos": edad,
    }
