"""Configuración en tiempo de ejecución.

La regla es la misma que en la interfaz web (ADR-005): la dirección de la API
**no se escribe en el código**. Trasladar el sistema a otra cuenta no puede
exigir recompilar ni volver a empaquetar (REQ-09). La interfaz web lo resuelve
con `configuracion.json` servido junto al sitio; una aplicación instalada no
tiene sitio del que leerlo, así que aquí hay tres fuentes, por orden:

1. **La dirección que el usuario fijó en el propio dispositivo**, desde la
   pantalla de acceso («Conexión»). Es lo que permite apuntar un APK ya
   instalado a otra cuenta sin reconstruirlo. La aplica la aplicación al
   arrancar, porque las preferencias del dispositivo solo se leen con la
   página abierta.
2. **Un archivo indicado en una variable de entorno** (`RASTRO_CONFIGURACION`,
   `COTEJO_CONFIGURACION`): ruta o URL de un `configuracion.json`. Sirve en
   escritorio y en el modo web, por ejemplo para apuntar a la pila local.
3. **El `configuracion.json` empaquetado** en `assets/`. Lo escribe el
   despliegue igual que el de la interfaz web.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

ASSETS = Path(__file__).resolve().parent.parent / "assets"

registro = logging.getLogger(__name__)


def cargar(aplicacion: str, por_omision: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """La configuración de `aplicacion` («rastro» o «cotejo») y de dónde salió."""
    variable = f"{aplicacion.upper()}_CONFIGURACION"
    origen = os.environ.get(variable, "").strip()
    datos: dict[str, Any] = {}

    if origen:
        try:
            if origen.startswith(("http://", "https://")):
                respuesta = httpx.get(origen, timeout=8)
                respuesta.raise_for_status()
                datos = respuesta.json()
            else:
                datos = json.loads(Path(origen).read_text(encoding="utf-8"))
            return {**por_omision, **datos}, f"{variable}={origen}"
        except (OSError, ValueError, httpx.HTTPError) as error:
            # Se sigue con el archivo empaquetado, pero se dice: una variable
            # mal escrita no debería pasar inadvertida.
            registro.warning("No se pudo leer %s (%s): %s", variable, origen, error)

    empaquetado = ASSETS / f"configuracion-{aplicacion}.json"
    try:
        datos = json.loads(empaquetado.read_text(encoding="utf-8"))
        return {**por_omision, **datos}, f"assets/{empaquetado.name}"
    except (OSError, ValueError):
        return dict(por_omision), "valores por omisión"
