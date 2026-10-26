"""Presentación de fechas y estados, en español de Colombia.

Mismas reglas que `web/src/componentes/ui.tsx`: la fecha legible para leer, la
relativa para saber de un vistazo cuánto hace, y la antigüedad en segundos para
lo que se mueve en vivo (una posición en el mapa).
"""

from __future__ import annotations

from datetime import datetime, timezone

_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")


def leer_fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        fecha = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def texto_estado(estado: str) -> str:
    return (estado or "").replace("_", " ")


def fecha_legible(iso: str | None) -> str:
    """«23 oct 2026, 3:05 p. m.», en la hora local del equipo."""
    fecha = leer_fecha(iso)
    if fecha is None:
        return iso or ""
    local = fecha.astimezone()
    hora = local.hour % 12 or 12
    sufijo = "a. m." if local.hour < 12 else "p. m."
    return f"{local.day} {_MESES[local.month - 1]} {local.year}, {hora}:{local.minute:02d} {sufijo}"


def fecha_corta(iso: str | None) -> str:
    fecha = leer_fecha(iso)
    return fecha.astimezone().strftime("%Y-%m-%d") if fecha else (iso or "")


def fecha_relativa(iso: str | None, ahora: datetime | None = None) -> str:
    """«hace 5 minutos», «ayer», «hace 3 días»."""
    fecha = leer_fecha(iso)
    if fecha is None:
        return ""
    referencia = ahora or datetime.now(timezone.utc)
    segundos = round((referencia - fecha).total_seconds())
    if segundos < 0:
        return "en un momento"
    if segundos < 60:
        return "ahora" if segundos < 10 else f"hace {segundos} segundos"
    minutos = round(segundos / 60)
    if segundos < 3600:
        return "hace 1 minuto" if minutos == 1 else f"hace {minutos} minutos"
    horas = round(segundos / 3600)
    if segundos < 86400:
        return "hace 1 hora" if horas == 1 else f"hace {horas} horas"
    dias = round(segundos / 86400)
    if segundos < 2592000:
        return "ayer" if dias == 1 else f"hace {dias} días"
    meses = round(segundos / 2592000)
    return "el mes pasado" if meses == 1 else f"hace {meses} meses"


def antiguedad(segundos: float | None) -> str:
    """«hace 12 s», «hace 3 min»: para saber si un punto en el mapa está vivo
    hacen falta los segundos, no «hace 1 minuto» durante un minuto entero."""
    if segundos is None:
        return "sin datos"
    s = max(0, round(segundos))
    if s < 5:
        return "ahora"
    if s < 60:
        return f"hace {s} s"
    if s < 3600:
        return f"hace {s // 60} min"
    return f"hace {s // 3600} h {(s % 3600) // 60} min"


def segundos_desde(iso: str | None) -> float | None:
    fecha = leer_fecha(iso)
    return (datetime.now(timezone.utc) - fecha).total_seconds() if fecha else None


def plural(cantidad: int, singular: str, plural_: str | None = None) -> str:
    return f"{cantidad} {singular if cantidad == 1 else (plural_ or singular + 's')}"
