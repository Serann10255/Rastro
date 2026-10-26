"""Genera `src/comun/fichas.py` a partir del sistema de diseño de `design/`.

El sistema de diseño es uno solo y vive en `design/tokens.css` (ADR-008). Las
aplicaciones Flet no leen CSS, así que este programa traduce los colores a un
módulo de Python. El módulo generado se versiona —el APK no lleva `design/`— y
una prueba (`tests/test_fichas.py`) falla si deja de coincidir con el CSS: un
color cambiado en `design/` sin regenerar aquí se nota en la siguiente
ejecución de las pruebas, no en una captura de pantalla meses después.

Uso, desde la raíz del repositorio:

    python cliente-flet/herramientas/generar_fichas.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "cliente-flet" / "src" / "comun" / "fichas.py"

FUENTES = {
    "base": RAIZ / "design" / "tokens.css",
    "rastro": RAIZ / "web" / "src" / "estilos" / "identidad.css",
    "cotejo": RAIZ / "cotejo" / "web" / "src" / "estilos" / "identidad.css",
}

_COLOR = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;")


def _bloque(css: str, selector: str) -> str:
    """El cuerpo del primer bloque cuyo selector es exactamente `selector`."""
    patron = re.compile(r"(^|\n)\s*" + re.escape(selector) + r"\s*\{")
    coincidencia = patron.search(css)
    if not coincidencia:
        return ""
    inicio = coincidencia.end()
    profundidad, indice = 1, inicio
    while profundidad and indice < len(css):
        profundidad += {"{": 1, "}": -1}.get(css[indice], 0)
        indice += 1
    return css[inicio : indice - 1]


def _colores(cuerpo: str) -> dict[str, str]:
    return {nombre: valor.lower() for nombre, valor in _COLOR.findall(cuerpo)}


def _temas(css: str) -> dict[str, dict[str, str]]:
    # El tema oscuro se toma del bloque forzado (`data-tema="oscuro"`), que es
    # idéntico al de la preferencia del sistema y no está anidado en @media.
    return {
        "claro": _colores(_bloque(css, ":root")),
        "oscuro": _colores(_bloque(css, ':root[data-tema="oscuro"]')),
    }


def _colores_por_estado(css: str) -> dict[str, str]:
    """Qué ficha colorea cada estado del envío (`.estado-CREADO { --estado-color: var(--acento) }`)."""
    resultado: dict[str, str] = {}
    for selectores, cuerpo in re.findall(r"((?:\.estado-[A-Z_]+,?\s*)+)\{([^}]*)\}", css):
        ficha = re.search(r"--estado-color:\s*var\(--([a-z0-9-]+)\)", cuerpo)
        if not ficha:
            continue
        for estado in re.findall(r"\.estado-([A-Z_]+)", selectores):
            resultado[estado] = ficha.group(1)
    return resultado


def generar() -> str:
    base_css = FUENTES["base"].read_text(encoding="utf-8")
    base = _temas(base_css)
    marcas = {app: _temas(FUENTES[app].read_text(encoding="utf-8")) for app in ("rastro", "cotejo")}
    estados = _colores_por_estado(base_css)

    def dic(valores: dict[str, str], sangria: int) -> str:
        espacio = " " * sangria
        filas = "".join(f'{espacio}    "{k}": "{v}",\n' for k, v in sorted(valores.items()))
        return "{\n" + filas + espacio + "}"

    lineas = [
        '"""Colores del sistema de diseño, traducidos de `design/` a Python.',
        "",
        "GENERADO por `cliente-flet/herramientas/generar_fichas.py`. No editar a mano:",
        "cambie el CSS de `design/` o el `identidad.css` de la aplicación y regenere.",
        '"""',
        "",
        "# Fichas compartidas por las dos aplicaciones, por tema.",
        "BASE = {",
    ]
    for tema in ("claro", "oscuro"):
        lineas.append(f'    "{tema}": {dic(base[tema], 4)},')
    lineas += ["}", "", "# Lo único que cada aplicación cambia: la marca y, en Cotejo, el acento.", "MARCAS = {"]
    for app, temas in marcas.items():
        lineas.append(f'    "{app}": {{')
        for tema in ("claro", "oscuro"):
            lineas.append(f'        "{tema}": {dic(temas[tema], 8)},')
        lineas.append("    },")
    lineas += ["}", "", "# Ficha que colorea cada estado del envío.", f"COLOR_POR_ESTADO = {dic(estados, 0)}", ""]
    return "\n".join(lineas)


if __name__ == "__main__":
    DESTINO.write_text(generar(), encoding="utf-8")
    print(f"escrito {DESTINO.relative_to(RAIZ)}", file=sys.stderr)
