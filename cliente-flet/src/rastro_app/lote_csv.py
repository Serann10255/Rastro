"""Lectura del archivo de envíos para el registro en lote.

Las reglas son las de la interfaz web (`EnvioNuevo.tsx`): las mismas columnas,
los mismos valores por omisión y las mismas filas omitidas, para que un archivo
que funciona en una funcione en la otra. Lo que cambia es el lector: aquí se usa
el módulo `csv` de la biblioteca estándar, que ya entiende comillas, comas y
saltos de línea dentro de un campo. En el navegador hubo que escribirlo a mano;
en Python escribirlo a mano sería reinventar lo que viene con el lenguaje.

El archivo se valida en el dispositivo antes de enviar nada: el operador ve los
errores por fila sin que el lote salga del equipo.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

COLUMNAS = (
    "destinatario",
    "telefono",
    "direccion_destino",
    "ciudad_destino",
    "direccion_origen",
    "descripcion",
    "orden_compra",
    "bultos",
    "peso_kg",
    "valor_declarado",
    "fecha_estimada",
)

PLANTILLA = (
    ",".join(COLUMNAS)
    + "\nLaura Mejia Rios,3001110001,Carrera 7 #32-16,Bogotá,Calle 100 #15-20,"
    "Sobre con documentos,OC-2026-1001,1,0.5,80000,2026-09-15"
    + "\nAndres Pardo Leon,3001110002,Calle 45 #13-05,Bogotá,Calle 100 #15-20,"
    "Caja de muestras,OC-2026-1002,2,3.2,150000,2026-09-15\n"
)

CIUDAD_POR_OMISION = "Bogotá"


@dataclass
class Analisis:
    filas: list[dict[str, Any]] = field(default_factory=list)
    ignoradas: int = 0
    error: str | None = None


def _numero(texto: str) -> float:
    try:
        return float(texto)
    except ValueError:
        return 0.0


def decodificar(contenido: bytes) -> str:
    """El texto del archivo. Una hoja de cálculo en Windows guarda en cp1252 si
    no se le pide UTF-8, y una tilde mal leída cambia un nombre."""
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="replace")


def analizar(texto: str) -> Analisis:
    contenido = texto.strip()
    if not contenido:
        return Analisis()

    lineas = [fila for fila in csv.reader(io.StringIO(contenido)) if any(c.strip() for c in fila)]
    if len(lineas) < 2:
        return Analisis(error="Hace falta la fila de nombres de columna y al menos un envío.")

    cabecera = [c.strip().lower() for c in lineas[0]]
    if "destinatario" not in cabecera or "direccion_destino" not in cabecera:
        return Analisis(
            error="El archivo debe tener al menos las columnas «destinatario» y «direccion_destino»."
        )

    resultado = Analisis()
    for celdas in lineas[1:]:

        def valor(nombre: str) -> str:
            if nombre not in cabecera:
                return ""
            indice = cabecera.index(nombre)
            return celdas[indice].strip() if indice < len(celdas) else ""

        destinatario = valor("destinatario")
        direccion = valor("direccion_destino")
        if not destinatario or not direccion:
            resultado.ignoradas += 1
            continue

        ciudad = valor("ciudad_destino") or CIUDAD_POR_OMISION
        fila: dict[str, Any] = {
            "origen": {"linea": valor("direccion_origen") or direccion, "ciudad": ciudad},
            "destino": {"linea": direccion, "ciudad": ciudad},
            "destinatario": {"nombre": destinatario},
            "bultos": int(_numero(valor("bultos"))) or 1,
            "peso_kg": _numero(valor("peso_kg")),
            "valor_declarado": _numero(valor("valor_declarado")),
        }
        if valor("telefono"):
            fila["destinatario"]["telefono"] = valor("telefono")
        for campo in ("descripcion", "orden_compra", "fecha_estimada"):
            if valor(campo):
                fila[campo] = valor(campo)
        resultado.filas.append(fila)

    return resultado
