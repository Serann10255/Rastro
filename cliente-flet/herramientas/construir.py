"""Construye Rastro o Cotejo con `flet build` (APK, Windows o web).

Las dos aplicaciones comparten el código de `src/comun`, pero cada paquete lleva
solo lo suyo: el APK de Rastro no incluye el programa de auditoría, y el de
Cotejo no incluye la operación que audita. Por eso cada construcción se hace
sobre una copia preparada en `build/<app>/`, con su módulo de entrada, su icono
y su nombre de producto, en lugar de construir `src/` tal cual.

Uso, desde la raíz del repositorio:

    cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py rastro apk
    cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py cotejo apk
    cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py rastro windows

La primera vez `flet build` descarga Flutter, el JDK y los componentes del SDK
de Android que falten; tarda. El resultado queda en `cliente-flet/salida/`.

Ojo con el SDK de Android: cuando `flet build` instala un paquete del SDK,
acepta por su cuenta todas las licencias que `sdkmanager --licenses` presente.
Por eso este programa no pasa `--yes`: las licencias conviene aceptarlas antes y
a mano (documentacion/despliegue/cliente-flet.md), y quien quiera que el
instalador conteste por él puede añadir `--yes` a la orden.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"

APLICACIONES = {
    "rastro": {"producto": "Rastro", "descripcion": "Trazabilidad verificable de envíos", "ajena": "cotejo"},
    "cotejo": {"producto": "Cotejo", "descripcion": "Revisión independiente de Rastro", "ajena": "rastro"},
}

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def preparar(app: str) -> Path:
    datos = APLICACIONES[app]
    destino = RAIZ / "build" / app
    if destino.exists():
        try:
            shutil.rmtree(destino)
        except OSError as error:
            sys.exit(
                f"No se pudo borrar {destino}: {error}\n"
                "Suele ser un demonio de Gradle de una construcción interrumpida: "
                "cierre los java.exe de ~/java y repita."
            )
    (destino / "src").mkdir(parents=True)

    shutil.copytree(SRC / "comun", destino / "src" / "comun", ignore=IGNORAR)
    shutil.copytree(SRC / f"{app}_app", destino / "src" / f"{app}_app", ignore=IGNORAR)
    shutil.copy2(SRC / f"{app}.py", destino / "src" / f"{app}.py")

    assets = destino / "src" / "assets"
    shutil.copytree(SRC / "assets" / "fuentes", assets / "fuentes")
    shutil.copy2(SRC / "assets" / f"configuracion-{app}.json", assets / f"configuracion-{app}.json")
    # `flet build` toma el icono de `assets/icon.png`.
    shutil.copy2(SRC / "assets" / "iconos" / f"{app}.png", assets / "icon.png")

    # El pyproject de la copia: el mismo, con el módulo y el producto de esta app.
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    proyecto = tomllib.loads(texto)
    texto = texto.replace(f'name = "{proyecto["project"]["name"]}"', f'name = "{app}"', 1)
    texto = texto.replace(f'description = "{proyecto["project"]["description"]}"', f'description = "{datos["descripcion"]}"', 1)
    texto = texto.replace('product = "Rastro"', f'product = "{datos["producto"]}"', 1)
    texto = texto.replace('module = "rastro"', f'module = "{app}"', 1)
    if app == "cotejo":
        # Cotejo no sale a ruta: no pide la ubicación, ni la cámara, ni el
        # servicio en primer plano. Una aplicación que audita no debería pedir
        # más permisos que los que usa.
        inicio = texto.index("[tool.flet.android.permission]")
        texto = texto[:inicio].rstrip() + "\n"
    (destino / "pyproject.toml").write_text(texto, encoding="utf-8")
    return destino


def detener_gradle(destino: Path) -> None:
    """Detiene los demonios que deja una construcción de Android.

    Gradle y el compilador de Kotlin siguen vivos horas después y, en Windows,
    mantienen abiertos archivos de `build/`: la construcción siguiente no podría
    borrar su copia.
    """
    gradlew = destino / "build" / "flutter" / "android" / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    # `flet build` instala su JDK en ~/java y no lo deja en JAVA_HOME.
    jdks = sorted((Path.home() / "java").glob("*"))
    java = os.environ.get("JAVA_HOME") or (str(jdks[-1]) if jdks else None)
    if not gradlew.exists() or java is None:
        return
    subprocess.call(
        [str(gradlew), "--stop"],
        cwd=gradlew.parent,
        env={**os.environ, "JAVA_HOME": java},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def construir(app: str, objetivo: str, extra: list[str]) -> int:
    destino = preparar(app)
    salida = RAIZ / "salida" / f"{app}-{objetivo}"
    flet = Path(sys.executable).with_name("flet.exe" if sys.platform == "win32" else "flet")
    orden = [
        str(flet),
        "build",
        objetivo,
        "--project",
        app,
        "--product",
        APLICACIONES[app]["producto"],
        "--org",
        "co.rastro",
        "--module-name",
        app,
        "-o",
        str(salida),
        *extra,
    ]
    print("$", " ".join(orden), file=sys.stderr)
    # La consola de Windows (cp1252) se cae al imprimir algunos textos del
    # instalador del SDK; en UTF-8 no.
    entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    codigo = subprocess.call(orden, cwd=destino, env=entorno)
    if objetivo in ("apk", "aab"):
        detener_gradle(destino)
    return codigo


if __name__ == "__main__":
    lector = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    lector.add_argument("app", choices=sorted(APLICACIONES))
    lector.add_argument("objetivo", choices=("apk", "aab", "windows", "web"))
    argumentos, resto = lector.parse_known_args()
    sys.exit(construir(argumentos.app, argumentos.objetivo, resto))
