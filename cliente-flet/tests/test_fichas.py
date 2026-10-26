"""Los colores de Flet salen del sistema de diseño de `design/`, no de una copia."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_fichas_py_coincide_con_el_css():
    especificacion = importlib.util.spec_from_file_location("generar_fichas", RAIZ / "herramientas" / "generar_fichas.py")
    generador = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(generador)
    actual = (RAIZ / "src" / "comun" / "fichas.py").read_text(encoding="utf-8")
    assert actual == generador.generar(), "Regenere con cliente-flet/herramientas/generar_fichas.py"


def test_cada_estado_tiene_color():
    from comun.fichas import BASE, COLOR_POR_ESTADO

    estados = {"CREADO", "ASIGNADO", "RECOLECTADO", "EN_TRANSITO", "EN_REPARTO", "ENTREGADO", "INCIDENCIA", "DEVUELTO", "CANCELADO"}
    assert estados <= set(COLOR_POR_ESTADO)
    assert all(ficha in BASE["claro"] for ficha in COLOR_POR_ESTADO.values())
