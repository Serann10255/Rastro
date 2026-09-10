"""Almacen de papeles de trabajo (REQ-03 y REQ-07 de Cotejo).

Dos partes, como describe el apartado 9.3 del documento. Un indice conserva por
cada ejecucion y control el resultado, la conclusion, la identidad de sesion, la
marca de tiempo y la huella criptografica del archivo. El archivo de evidencia,
con la salida literal y sin editar, se guarda aparte.

La separacion permite comparar ejecuciones sin abrir los archivos y conservar la
salida cruda sin transformarla. La huella es lo que hace detectable una
modificacion posterior del archivo: si alguien lo edita, deja de coincidir.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .modelos import PapelDeTrabajo, marca_tiempo

RAIZ_COTEJO = Path(__file__).resolve().parents[1]
DIR_PAPELES = Path(os.getenv("COTEJO_DIR_PAPELES", RAIZ_COTEJO / "papeles"))

NOMBRE_INDICE = "indice.json"


def huella(datos: bytes) -> str:
    """SHA-256 en hexadecimal, la misma funcion que encadena la bitacora auditada."""
    return hashlib.sha256(datos).hexdigest()


def huella_de_archivo(ruta: Path) -> str:
    return huella(ruta.read_bytes())


class AlmacenPapeles:
    """Escribe y lee papeles de trabajo de una ejecucion.

    El ejecutor es el unico componente que escribe aqui. Ningun actor modifica
    los papeles: el informe los referencia, no los edita.
    """

    def __init__(self, ejecucion_id: str, base: Path | None = None) -> None:
        self.ejecucion_id = ejecucion_id
        self.base = Path(base or DIR_PAPELES) / ejecucion_id
        self.evidencias = self.base / "evidencias"
        self.evidencias.mkdir(parents=True, exist_ok=True)
        self._papeles: list[PapelDeTrabajo] = []

    # -- escritura --------------------------------------------------------- #

    def guardar(self, papel: PapelDeTrabajo) -> PapelDeTrabajo:
        """Escribe el archivo de evidencia y calcula su huella.

        La huella se calcula sobre los bytes efectivamente escritos y no sobre
        la estructura en memoria: es la unica forma de que recalcularla despues
        detecte una edicion del archivo.
        """
        nombre = f"{papel.control_id}.json"
        ruta = self.evidencias / nombre

        contenido = {
            "ejecucion_id": self.ejecucion_id,
            "control_id": papel.control_id,
            "control": papel.control,
            "marco": papel.marco,
            "tipo": str(papel.tipo),
            "procedimiento": papel.procedimiento,
            "criterio": papel.criterio,
            "evidencia_esperada": papel.evidencia_esperada,
            "identidad_ejecucion": papel.identidad_ejecucion,
            "iniciado_en": papel.iniciado_en,
            "terminado_en": papel.terminado_en,
            "conclusion": str(papel.conclusion),
            "resumen": papel.resumen,
            "observaciones": papel.observaciones,
            "detalle": papel.detalle,
        }
        ruta.write_text(
            json.dumps(contenido, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

        papel.archivo_evidencia = str(ruta.relative_to(self.base))
        papel.huella_evidencia = huella_de_archivo(ruta)
        self._papeles.append(papel)
        return papel

    def cerrar(self, metadatos: dict) -> Path:
        """Escribe el indice de la ejecucion y lo devuelve."""
        indice = {
            "ejecucion_id": self.ejecucion_id,
            "cerrado_en": marca_tiempo(),
            **metadatos,
            "resumen": self.resumen(),
            "papeles": [
                {
                    "control_id": p.control_id,
                    "tipo": str(p.tipo),
                    "criterio": p.criterio,
                    "conclusion": str(p.conclusion),
                    "resumen": p.resumen,
                    "identidad_ejecucion": p.identidad_ejecucion,
                    "terminado_en": p.terminado_en,
                    "archivo_evidencia": p.archivo_evidencia,
                    "huella_evidencia": p.huella_evidencia,
                }
                for p in self._papeles
            ],
        }
        ruta = self.base / NOMBRE_INDICE
        ruta.write_text(json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8")
        return ruta

    def resumen(self) -> dict[str, int]:
        conteo: dict[str, int] = {}
        for papel in self._papeles:
            conteo[str(papel.conclusion)] = conteo.get(str(papel.conclusion), 0) + 1
        return conteo

    @property
    def papeles(self) -> list[PapelDeTrabajo]:
        return list(self._papeles)


# --------------------------------------------------------------------------- #
# Verificacion de integridad del propio almacen
# --------------------------------------------------------------------------- #


def verificar_almacen(base: Path) -> dict:
    """Recalcula la huella de cada archivo y la compara con la del indice.

    Es la comprobacion de REQ-07: el almacen no impide fisicamente que alguien
    edite un archivo, pero hace que la edicion no pase inadvertida. Declarar esa
    diferencia importa: se detecta la manipulacion, no se previene.
    """
    base = Path(base)
    ruta_indice = base / NOMBRE_INDICE
    if not ruta_indice.is_file():
        return {
            "almacen_integro": False,
            "motivo": f"No existe el indice en {base}",
            "discrepancias": [],
        }

    indice = json.loads(ruta_indice.read_text(encoding="utf-8"))
    discrepancias = []

    for entrada in indice.get("papeles", []):
        ruta = base / entrada["archivo_evidencia"]
        if not ruta.is_file():
            discrepancias.append(
                {
                    "control_id": entrada["control_id"],
                    "tipo": "ARCHIVO_AUSENTE",
                    "archivo": entrada["archivo_evidencia"],
                }
            )
            continue

        actual = huella_de_archivo(ruta)
        if actual != entrada["huella_evidencia"]:
            discrepancias.append(
                {
                    "control_id": entrada["control_id"],
                    "tipo": "HUELLA_DISCORDANTE",
                    "archivo": entrada["archivo_evidencia"],
                    "huella_indice": entrada["huella_evidencia"],
                    "huella_recalculada": actual,
                }
            )

    return {
        "almacen_integro": not discrepancias,
        "ejecucion_id": indice.get("ejecucion_id"),
        "papeles_verificados": len(indice.get("papeles", [])),
        "discrepancias": discrepancias,
        "verificado_en": marca_tiempo(),
    }


def comparar_ejecuciones(base_a: Path, base_b: Path) -> dict:
    """Compara la clasificacion de dos ejecuciones (REQ-08 de Cotejo).

    Es la comprobacion de reproducibilidad: un evaluador distinto ejecuta el
    mismo programa y debe obtener la misma clasificacion para cada control. Se
    comparan las conclusiones y no las huellas de evidencia, porque cada
    ejecucion tiene su propia marca de tiempo y por lo tanto su propia huella.
    """
    def clasificaciones(base: Path) -> dict[str, str]:
        indice = json.loads((Path(base) / NOMBRE_INDICE).read_text(encoding="utf-8"))
        return {p["control_id"]: p["conclusion"] for p in indice["papeles"]}

    a, b = clasificaciones(base_a), clasificaciones(base_b)
    controles = sorted(set(a) | set(b))
    diferencias = [
        {"control_id": c, "ejecucion_a": a.get(c, "AUSENTE"), "ejecucion_b": b.get(c, "AUSENTE")}
        for c in controles
        if a.get(c) != b.get(c)
    ]

    return {
        "reproducible": not diferencias,
        "controles_comparados": len(controles),
        "coincidencias": len(controles) - len(diferencias),
        "diferencias": diferencias,
        "comparado_en": marca_tiempo(),
    }
