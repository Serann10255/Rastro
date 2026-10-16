"""Punto de entrada de Cotejo como función de AWS Lambda.

La aplicación es la misma que corre en local (`main.py`); esto solo resuelve lo
que Lambda cambia:

1. **El disco no dura.** Una función solo puede escribir en ``/tmp``, y ese
   directorio desaparece con el contenedor y no se comparte entre contenedores.
   Los papeles de trabajo viven por eso en un contenedor de S3: antes de cada
   petición se trae lo que falte y después se sube lo que la petición escribió.
   Los archivos viajan byte a byte, de modo que la huella de cada papel se
   recalcula igual en la nube que en el equipo del auditor.
2. **API Gateway corta a los 30 segundos.** Una revisión completa tarda más. La
   petición de ejecutar solo la encarga: la función se invoca a sí misma de
   forma asíncrona, la ejecución corre sin ese límite y la interfaz pregunta por
   su estado.
3. **En la función no hay repositorio.** Los controles de secretos (C-09)
   revisan el código con git, igual que en local. La imagen de la función trae
   git, y antes de cada revisión se clona **el repositorio publicado** —lo que
   cualquiera puede descargar, que es justo lo que C-09 pregunta—, con todo su
   historial.

Cotejo corre así **dentro de la cuenta auditada y con su mismo rol**. Es una
pérdida de independencia que se declara (ADR-015), no un detalle de despliegue.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import boto3

# Se importa como módulo de primer nivel desde su propia carpeta (el manejador
# de la función la añade a la ruta), igual que main.py, que a su vez añade la
# raíz de Cotejo para encontrar el paquete ``cotejo``.
AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import main  # noqa: E402

DIR_PAPELES = Path(os.environ.get("COTEJO_DIR_PAPELES", "/tmp/papeles"))
BUCKET = os.environ["COTEJO_BUCKET_PAPELES"]
PREFIJO = "papeles/"

_s3 = boto3.client("s3")
_lambda = boto3.client("lambda")
_asgi = None


def _adaptador():
    """El adaptador de Lambda a la aplicacion, creado al primer uso.

    Se importa aqui y no arriba porque solo existe en el paquete de la funcion:
    las pruebas locales del almacen no lo necesitan.
    """
    global _asgi
    if _asgi is None:
        from mangum import Mangum

        _asgi = Mangum(main.app, lifespan="off")
    return _asgi


def _traer() -> None:
    """Trae del almacén lo que este contenedor no tiene, o tiene distinto.

    Se compara por tamaño: los papeles se escriben una vez y no se editan, y el
    estado de una ejecución cambia de tamaño al pasar de «en curso» a «lista».
    """
    paginas = _s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIJO)
    for pagina in paginas:
        for objeto in pagina.get("Contents", []):
            relativo = objeto["Key"][len(PREFIJO) :]
            if not relativo or relativo.endswith("/"):
                continue
            destino = DIR_PAPELES / relativo
            if destino.is_file() and destino.stat().st_size == objeto["Size"]:
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            _s3.download_file(BUCKET, objeto["Key"], str(destino))
            # La hora del archivo traído queda en el pasado para que la subida
            # posterior no lo tome por escrito en esta petición.
            os.utime(destino, (0, 0))


def _llevar(desde: float) -> None:
    """Sube lo que se escribió en ``/tmp`` desde ``desde``."""
    if not DIR_PAPELES.is_dir():
        return
    for archivo in DIR_PAPELES.rglob("*"):
        if archivo.is_file() and archivo.stat().st_mtime >= desde:
            clave = PREFIJO + archivo.relative_to(DIR_PAPELES).as_posix()
            _s3.upload_file(str(archivo), BUCKET, clave)


def _lanzar(ejecucion_id: str, solo: list[str] | None, quien: dict) -> None:
    """Encarga la ejecución a una invocación asíncrona de esta misma función.

    El estado «en curso» tiene que estar en el almacén antes de que la interfaz
    pregunte por él desde otro contenedor, de modo que se sube aquí mismo.
    """
    estado = main.DIR_ESTADOS / f"{ejecucion_id}.json"
    _s3.upload_file(str(estado), BUCKET, PREFIJO + estado.relative_to(DIR_PAPELES).as_posix())
    _lambda.invoke(
        FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
        InvocationType="Event",
        Payload=json.dumps(
            {"cotejo": "ejecutar", "ejecucion_id": ejecucion_id, "solo": solo, "quien": quien}
        ).encode("utf-8"),
    )


main.LANZADOR = _lanzar

#: Dónde se clona el código que revisa C-09. De dónde se clona lo dice
#: ``COTEJO_REPOSITORIO_REMOTO``, que el despliegue fija con el remoto del
#: repositorio (``git remote get-url origin``).
DIR_REPOSITORIO = Path("/tmp/repositorio.git")


def _forzar_borrado(funcion, ruta, excepcion) -> None:
    """Borra también lo que git deja de solo lectura (sus paquetes de objetos)."""
    if isinstance(excepcion, FileNotFoundError):
        return
    os.chmod(ruta, stat.S_IWRITE)
    funcion(ruta)


def _preparar_repositorio() -> None:
    """Clona el repositorio publicado para que C-09 lo revise con git.

    Se clona de cero en cada revisión, sin reutilizar el de una anterior: lo que
    se revisa tiene que ser lo publicado en ese momento, no lo que había cuando
    el contenedor arrancó. Es un clon desnudo (``--bare``): trae todas las ramas
    y su historial —C-09b recorre ``--all``— sin desplegar archivos que nadie va
    a leer, y su HEAD es la rama principal del remoto.

    Si el clon falla, C-09 queda sin ejecutar con el error de git sobre esta
    ruta, que es lo honesto: no se revisó.
    """
    remoto = os.environ.get("COTEJO_REPOSITORIO_REMOTO", "").strip()
    if not remoto:
        return
    os.environ["COTEJO_REPOSITORIO"] = str(DIR_REPOSITORIO)
    shutil.rmtree(DIR_REPOSITORIO, onexc=_forzar_borrado)
    try:
        resultado = subprocess.run(
            ["git", "clone", "--bare", "--quiet", remoto, str(DIR_REPOSITORIO)],
            capture_output=True,
            timeout=120,
            # Sin HOME, git busca su configuración en una carpeta que en Lambda
            # no existe; y sin terminal no debe quedarse pidiendo credenciales.
            env={**os.environ, "HOME": "/tmp", "GIT_TERMINAL_PROMPT": "0"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"No se pudo clonar {remoto}: {exc!r}")
        return
    if resultado.returncode != 0:
        print(f"No se pudo clonar {remoto}: {resultado.stderr.decode('utf-8', 'replace')[:500]}")


def manejador(evento: dict, contexto) -> dict | None:
    DIR_PAPELES.mkdir(parents=True, exist_ok=True)
    _traer()
    # Con margen: la hora que el sistema de archivos pone a un archivo es más
    # gruesa que la del reloj, y un papel escrito justo después de este punto
    # podía quedar fechado un poco antes y no subirse. Subir de más lo que se
    # escribió en la petición anterior es inofensivo; lo traído del almacén
    # está fechado en 1970 y nunca entra en el margen.
    inicio = time.time() - 2
    try:
        if evento.get("cotejo") == "ejecutar":
            _preparar_repositorio()
            try:
                main.completar_en_segundo_plano(
                    evento["ejecucion_id"], evento.get("solo"), evento["quien"]
                )
            except Exception as exc:  # noqa: BLE001 - ya quedó anotada como fallida
                # No se relanza: Lambda reintentaría la invocación asíncrona y
                # una revisión repetida a escondidas no es la que se encargó.
                print(f"La ejecución {evento['ejecucion_id']} falló: {exc!r}")
            return None
        return _adaptador()(evento, contexto)
    finally:
        # También si la ejecución falló: el estado «fallida» y los papeles que
        # alcanzaron a escribirse tienen que llegar al almacén.
        _llevar(inicio)
