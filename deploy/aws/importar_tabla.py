"""Importa a DynamoDB los registros exportados por ``migrar.sh exportar``.

Se hace en Python y no con la interfaz de linea de comandos porque la escritura
por lotes exige agrupar de a 25 elementos y reintentar los que el servicio
devuelve sin procesar. Ignorar esos elementos produciria una migracion
silenciosamente incompleta, que en la bitacora significa una cadena rota.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import boto3

TAMANO_LOTE = 25
MAX_REINTENTOS = 6


def importar(tabla: str, archivo: Path, region: str) -> int:
    cliente = boto3.client("dynamodb", region_name=region)
    items = json.loads(archivo.read_text(encoding="utf-8"))
    if not items:
        print(f"  [ok] {tabla}: no hay registros que importar")
        return 0

    escritos = 0
    for inicio in range(0, len(items), TAMANO_LOTE):
        lote = [{"PutRequest": {"Item": item}} for item in items[inicio : inicio + TAMANO_LOTE]]
        pendientes = {tabla: lote}

        for intento in range(MAX_REINTENTOS):
            respuesta = cliente.batch_write_item(RequestItems=pendientes)
            pendientes = respuesta.get("UnprocessedItems") or {}
            if not pendientes:
                break
            # Espera creciente: el servicio limita la escritura, no la rechaza.
            time.sleep(2**intento * 0.1)
        else:
            restantes = sum(len(v) for v in pendientes.values())
            raise RuntimeError(
                f"{tabla}: {restantes} registros no se pudieron escribir tras {MAX_REINTENTOS} intentos. "
                "La migracion esta incompleta y no debe darse por buena."
            )

        escritos += len(lote)

    print(f"  [ok] {tabla}: {escritos} registros importados")
    return escritos


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Uso: importar_tabla.py <tabla> <archivo.json> <region>", file=sys.stderr)
        return 2
    importar(argv[1], Path(argv[2]), argv[3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
