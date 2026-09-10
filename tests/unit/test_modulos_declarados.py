"""Los modulos de la semilla apuntan a rutas que la interfaz define de verdad.

Esta prueba existe por un fallo concreto: al mover el catalogo de modulos del
codigo a la base de datos, la semilla quedo declarando la ruta ``/guias`` cuando
el enrutador la define en ``/envios/guias``. El menu y la barra pintaron un
enlace a una pantalla inexistente, y el usuario recibio un «esa pagina no
existe» al pulsarlo.

Es el precio de mover un dato a la base de datos: aparecen dos fuentes que
pueden discrepar en silencio. Antes la lista estaba escrita en la misma pantalla
que enrutaba, de modo que una ruta mal escrita no compilaba.

La prueba lee las dos fuentes -la semilla y el enrutador- y comprueba que dicen
lo mismo. No sustituye a mirar la pantalla; evita que la discrepancia llegue a
ella.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SEMILLA = RAIZ / "seed" / "modulos.json"
ENRUTADOR = RAIZ / "web" / "src" / "App.tsx"

#: Iconos que el sistema de diseno sabe dibujar. Se leen del propio modulo para
#: no mantener aqui una copia que se desincronice, que es exactamente el
#: problema que esta prueba vigila.
ICONOS = RAIZ / "design" / "marca" / "iconos.tsx"


def _modulos() -> list[dict]:
    return json.loads(SEMILLA.read_text(encoding="utf-8"))["modulos"]


def _rutas_declaradas() -> set[str]:
    """Las rutas que el enrutador de la interfaz define, con sus parametros."""
    fuente = ENRUTADOR.read_text(encoding="utf-8")
    return {ruta for ruta in re.findall(r'path="([^"]+)"', fuente) if ruta.startswith("/")}


def _coincide(ruta: str, patron: str) -> bool:
    """Compara una ruta con un patron del enrutador, tramo a tramo.

    Un tramo que empieza por ``:`` es un parametro y acepta cualquier valor:
    ``/maestros/:recurso`` cubre ``/maestros/tiendas``.
    """
    tramos_ruta = ruta.strip("/").split("/")
    tramos_patron = patron.strip("/").split("/")
    if len(tramos_ruta) != len(tramos_patron):
        return False
    return all(
        p.startswith(":") or p == r for r, p in zip(tramos_ruta, tramos_patron, strict=True)
    )


@pytest.mark.parametrize("modulo", _modulos(), ids=lambda m: m["clave"])
def test_cada_modulo_disponible_apunta_a_una_ruta_que_existe(modulo: dict):
    if not modulo.get("disponible", True):
        pytest.skip("un modulo apagado no lleva a ninguna parte, por definicion")

    ruta = modulo.get("ruta", "")
    assert ruta, f"el modulo '{modulo['clave']}' esta disponible y no declara ruta"

    patrones = _rutas_declaradas()
    assert any(_coincide(ruta, patron) for patron in patrones), (
        f"el modulo '{modulo['clave']}' apunta a {ruta}, que el enrutador no define. "
        f"Rutas declaradas: {sorted(patrones)}"
    )


@pytest.mark.parametrize("modulo", _modulos(), ids=lambda m: m["clave"])
def test_cada_modulo_pide_un_icono_que_el_sistema_sabe_dibujar(modulo: dict):
    """Un icono desconocido no rompe la pantalla -se dibuja el generico- pero
    tampoco deberia llegar a produccion: el generico esta para lo imprevisto."""
    fuente = ICONOS.read_text(encoding="utf-8")
    disponibles = set(re.findall(r"^  ([a-z]+):", fuente, re.MULTILINE))

    assert modulo["icono"] in disponibles, (
        f"el modulo '{modulo['clave']}' pide el icono '{modulo['icono']}', "
        f"que no existe en design/marca/iconos.tsx"
    )


def test_un_modulo_apagado_declara_su_motivo():
    """La misma regla que aplica el repositorio, comprobada sobre la semilla:
    un modulo ausente sin motivo parece un olvido."""
    for modulo in _modulos():
        if not modulo.get("disponible", True):
            assert modulo.get("motivo"), f"'{modulo['clave']}' esta apagado y no dice por que"


def test_las_claves_de_los_modulos_no_se_repiten():
    """Dos registros con la misma clave se sobrescriben en la tabla y el
    segundo gana en silencio."""
    claves = [m["clave"] for m in _modulos()]
    assert len(claves) == len(set(claves))


def test_los_contadores_que_piden_los_modulos_los_resuelve_la_interfaz():
    """El modulo declara que contador quiere; la pantalla lo resuelve. Si pide
    uno que la pantalla no conoce, el numero no aparece y nadie sabe por que."""
    operaciones = (RAIZ / "web" / "src" / "paginas" / "Operaciones.tsx").read_text(encoding="utf-8")
    bloque = operaciones.split("const contadores", 1)[1].split("};", 1)[0]
    conocidos = set(re.findall(r"^\s{4}([a-z_]+):", bloque, re.MULTILINE))

    for modulo in _modulos():
        contador = modulo.get("contador")
        if contador:
            assert contador in conocidos, (
                f"el modulo '{modulo['clave']}' pide el contador '{contador}', "
                f"que Operaciones.tsx no sabe resolver. Conocidos: {sorted(conocidos)}"
            )
