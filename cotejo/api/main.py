"""Interfaz HTTP del programa de auditoría.

Expone el catálogo, la ejecución del programa y los papeles de trabajo, para que
el auditor pueda operar sin línea de comandos. La línea de comandos sigue siendo
el camino principal —es la que se versiona y la que ejecuta un evaluador
independiente— y esta interfaz consume exactamente las mismas funciones: no hay
una segunda implementación del ejecutor que pudiera divergir.

**Acceso restringido al rol auditor.** El almacén de papeles de trabajo concentra
información sobre las debilidades del sistema auditado y su divulgación
facilitaría un ataque. Se valida el mismo token que emite el proveedor de
identidad de Rastro y se exige el grupo ``auditor``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

RAIZ_COTEJO = Path(__file__).resolve().parents[1]
if str(RAIZ_COTEJO) not in sys.path:
    sys.path.insert(0, str(RAIZ_COTEJO))

from rastro_core.authz import Grupo, normalizar_grupos  # noqa: E402
from rastro_core.errors import NoAutorizadoError, RastroError  # noqa: E402
from rastro_core.security import extraer_token, identidad_desde_token  # noqa: E402

from cotejo.contexto import Contexto, ErrorContexto  # noqa: E402
from cotejo.ejecutor import ErrorCatalogo, cargar_catalogo, cobertura, ejecutar  # noqa: E402
from cotejo.informe import construir_hallazgos, escribir, redactar  # noqa: E402
from cotejo.modelos import marca_tiempo  # noqa: E402
from cotejo.papeles import (  # noqa: E402
    DIR_PAPELES,
    NOMBRE_INDICE,
    comparar_ejecuciones,
    verificar_almacen,
)

app = FastAPI(
    title="cotejo-api",
    description=(
        "Programa de auditoría de sistemas con verificación automatizada de controles "
        "y papeles de trabajo reproducibles."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.exception_handler(RastroError)
async def _manejar_error(_peticion, exc: RastroError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"codigo": exc.codigo, "mensaje": exc.mensaje, "detalle": exc.detalle},
    )


# --------------------------------------------------------------------------- #
# Autorización
# --------------------------------------------------------------------------- #


async def auditor(authorization: str | None = Header(default=None)) -> dict:
    """Exige un token válido del grupo auditor.

    Es el mismo control que Rastro aplica sobre su bitácora, por la misma razón:
    quien no audita no necesita ver dónde está débil el sistema.
    """
    identidad = identidad_desde_token(extraer_token(authorization))
    if Grupo.AUDITOR not in normalizar_grupos(identidad.grupos):
        raise NoAutorizadoError(
            "El almacén de papeles de trabajo está restringido al rol auditor.",
            {"grupos_presentados": sorted(identidad.grupos)},
        )
    return {"sub": identidad.sub, "email": identidad.email, "org_id": identidad.org_id}


# --------------------------------------------------------------------------- #
# Estado y catálogo
# --------------------------------------------------------------------------- #


@app.get("/salud", tags=["operacion"], summary="Estado del programa")
async def salud() -> dict:
    try:
        catalogo = cargar_catalogo()
        controles = len(catalogo["controles"])
        estado_catalogo = "cargado"
    except ErrorCatalogo as exc:
        controles = 0
        estado_catalogo = f"no utilizable: {exc}"

    ctx = Contexto.desde_entorno()
    return {
        "servicio": "cotejo-api",
        "version": "0.1.0",
        "sistema_auditado": "Rastro",
        "entorno": ctx.entorno,
        "url_auditada": ctx.url_api,
        "controles_en_catalogo": controles,
        "catalogo": estado_catalogo,
        "ts": marca_tiempo(),
    }


@app.get("/catalogo", tags=["catalogo"], summary="Matriz de controles")
async def obtener_catalogo(_: dict = Depends(auditor)) -> dict:
    """El criterio de cada control, declarado antes de ejecutar nada."""
    catalogo = cargar_catalogo()
    return {
        "version": catalogo.get("version"),
        "sistema_auditado": catalogo.get("sistema_auditado"),
        "fecha_catalogo": str(catalogo.get("fecha_catalogo", "")),
        "controles": [
            {
                "id": control.id,
                "control": control.control,
                "marco": control.marco,
                "tipo": str(control.tipo),
                "prueba": control.prueba,
                "procedimiento": control.procedimiento,
                "criterio": control.criterio,
                "evidencia_esperada": control.evidencia_esperada,
                "severidad_si_desviado": str(control.severidad_si_desviado),
            }
            for control in catalogo["controles"]
        ],
        "hallazgos_permanentes": [
            {clave: " ".join(str(valor).split()) for clave, valor in entrada.items()}
            for entrada in catalogo.get("hallazgos_permanentes", [])
        ],
    }


# --------------------------------------------------------------------------- #
# Ejecuciones
# --------------------------------------------------------------------------- #


class SolicitudEjecucion(BaseModel):
    solo: list[str] | None = Field(
        default=None,
        description="Identificadores de control a ejecutar. Vacío ejecuta el catálogo completo.",
    )


def _leer_indice(base: Path) -> dict | None:
    ruta = base / NOMBRE_INDICE
    if not ruta.is_file():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _resumen_indice(indice: dict) -> dict:
    papeles = indice.get("papeles", [])
    conteo: dict[str, int] = {}
    for papel in papeles:
        conteo[papel["conclusion"]] = conteo.get(papel["conclusion"], 0) + 1
    return {
        "ejecucion_id": indice.get("ejecucion_id"),
        "cerrado_en": indice.get("cerrado_en"),
        "entorno": indice.get("entorno"),
        "url_api": indice.get("url_api"),
        "identidad_ejecucion": indice.get("identidad_ejecucion"),
        "version_catalogo": indice.get("version_catalogo"),
        "controles": len(papeles),
        "conformes": conteo.get("CONFORME", 0),
        "desviados": conteo.get("DESVIADO", 0),
        "no_ejecutados": conteo.get("NO_EJECUTADA", 0),
    }


@app.get("/ejecuciones", tags=["ejecuciones"], summary="Ejecuciones almacenadas")
async def listar_ejecuciones(_: dict = Depends(auditor)) -> dict:
    if not DIR_PAPELES.is_dir():
        return {"ejecuciones": []}

    ejecuciones = []
    for carpeta in sorted(DIR_PAPELES.iterdir(), reverse=True):
        if not carpeta.is_dir():
            continue
        indice = _leer_indice(carpeta)
        if indice:
            ejecuciones.append(_resumen_indice(indice))
    return {"ejecuciones": ejecuciones}


@app.post("/ejecuciones", status_code=201, tags=["ejecuciones"], summary="Ejecutar el catálogo")
async def crear_ejecucion(
    solicitud: SolicitudEjecucion | None = None, quien: dict = Depends(auditor)
) -> dict:
    """Recorre el catálogo completo en una sola invocación, sin intervención manual.

    Un fallo en un control no detiene el resto: queda marcado como NO_EJECUTADA
    con su motivo. Una ejecución interrumpida produciría papeles incompletos que
    podrían confundirse con pruebas fallidas.
    """
    catalogo = cargar_catalogo()
    ctx = Contexto.desde_entorno()
    try:
        almacen, metadatos = ejecutar(ctx, catalogo, solo=(solicitud.solo if solicitud else None))
    finally:
        ctx.cerrar()

    metadatos["ejecucion_id"] = almacen.ejecucion_id
    metadatos["solicitada_por"] = quien["sub"]
    resumen = cobertura(almacen, catalogo)
    hallazgos = construir_hallazgos(almacen.papeles, catalogo)
    escribir(almacen.base, metadatos, resumen, almacen.papeles, hallazgos)

    return {
        "ejecucion_id": almacen.ejecucion_id,
        "metadatos": metadatos,
        "cobertura": resumen,
        "controles": [papel.como_dict() for papel in almacen.papeles],
        "hallazgos": [hallazgo.como_dict() for hallazgo in hallazgos],
    }


@app.get("/ejecuciones/{ejecucion_id}", tags=["ejecuciones"], summary="Detalle de una ejecución")
async def obtener_ejecucion(ejecucion_id: str, _: dict = Depends(auditor)) -> dict:
    base = _base_segura(ejecucion_id)
    informe = base / "informe.json"
    if not informe.is_file():
        from rastro_core.errors import NoEncontradoError

        raise NoEncontradoError("No existe esa ejecución.")
    return json.loads(informe.read_text(encoding="utf-8"))


@app.get(
    "/ejecuciones/{ejecucion_id}/informe.txt",
    tags=["ejecuciones"],
    summary="Informe en texto plano",
)
async def obtener_informe_texto(ejecucion_id: str, _: dict = Depends(auditor)) -> dict:
    base = _base_segura(ejecucion_id)
    ruta = base / "informe.txt"
    if not ruta.is_file():
        # Se regenera desde el JSON si falta: el informe es una vista, no la
        # evidencia; la evidencia son los papeles de trabajo y sus huellas.
        datos = json.loads((base / "informe.json").read_text(encoding="utf-8"))
        return {"texto": _regenerar_texto(datos)}
    return {"texto": ruta.read_text(encoding="utf-8")}


@app.get(
    "/ejecuciones/{ejecucion_id}/papeles/{control_id}",
    tags=["ejecuciones"],
    summary="Papel de trabajo de un control",
)
async def obtener_papel(ejecucion_id: str, control_id: str, _: dict = Depends(auditor)) -> dict:
    """Devuelve la evidencia literal y recalcula su huella en el momento.

    Que la huella se recalcule al leer, y no se copie del índice, es lo que hace
    que abrir el papel sirva también como comprobación de que nadie lo editó.
    """
    from cotejo.papeles import huella_de_archivo
    from rastro_core.errors import NoEncontradoError

    base = _base_segura(ejecucion_id)
    ruta = base / "evidencias" / f"{_segmento_seguro(control_id)}.json"
    if not ruta.is_file():
        raise NoEncontradoError("No existe ese papel de trabajo.")

    indice = _leer_indice(base) or {}
    registrada = next(
        (p["huella_evidencia"] for p in indice.get("papeles", []) if p["control_id"] == control_id),
        None,
    )
    actual = huella_de_archivo(ruta)

    return {
        "contenido": json.loads(ruta.read_text(encoding="utf-8")),
        "huella_registrada": registrada,
        "huella_recalculada": actual,
        "coincide": registrada == actual,
    }


@app.post(
    "/ejecuciones/{ejecucion_id}/verificacion",
    tags=["ejecuciones"],
    summary="Verificar la integridad del almacén",
)
async def verificar(ejecucion_id: str, _: dict = Depends(auditor)) -> dict:
    """Recalcula la huella de cada archivo y la compara con la del índice.

    El almacén no impide la edición: la hace detectable. Prometer prevención
    donde solo hay detección sería una afirmación que la evidencia no sostiene.
    """
    return verificar_almacen(_base_segura(ejecucion_id))


@app.get("/comparacion", tags=["ejecuciones"], summary="Comparar dos ejecuciones")
async def comparar(
    a: str = Query(description="Identificador de la primera ejecución"),
    b: str = Query(description="Identificador de la segunda ejecución"),
    _: dict = Depends(auditor),
) -> dict:
    """Comprueba que un evaluador distinto obtiene la misma clasificación.

    Se comparan las conclusiones y no las huellas: cada ejecución tiene su propia
    marca de tiempo y, por lo tanto, su propia huella. Lo que debe reproducirse
    es el juicio sobre cada control, no el byte.
    """
    return comparar_ejecuciones(_base_segura(a), _base_segura(b))


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #


def _segmento_seguro(valor: str) -> str:
    """Impide que un identificador salga del directorio de papeles."""
    from rastro_core.errors import ValidacionError

    limpio = (valor or "").strip()
    if not limpio or "/" in limpio or "\\" in limpio or ".." in limpio:
        raise ValidacionError("Identificador no válido.")
    return limpio


def _base_segura(ejecucion_id: str) -> Path:
    from rastro_core.errors import NoEncontradoError

    base = DIR_PAPELES / _segmento_seguro(ejecucion_id)
    if not base.is_dir():
        raise NoEncontradoError("No existe esa ejecución.")
    return base


def _regenerar_texto(datos: dict[str, Any]) -> str:
    from cotejo.modelos import Conclusion, Hallazgo, PapelDeTrabajo, Severidad, TipoPrueba

    papeles = [
        PapelDeTrabajo(
            **{
                **control,
                "tipo": TipoPrueba(control["tipo"]),
                "conclusion": Conclusion(control["conclusion"]),
            }
        )
        for control in datos["controles"]
    ]
    hallazgos = [
        Hallazgo(**{**hallazgo, "severidad": Severidad(hallazgo["severidad"])})
        for hallazgo in datos["hallazgos"]
    ]
    return redactar(datos["metadatos"], datos["cobertura"], papeles, hallazgos)
