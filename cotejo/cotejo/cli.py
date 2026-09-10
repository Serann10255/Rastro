"""Linea de comandos de Cotejo.

    python -m cotejo ejecutar                 # recorre el catalogo completo
    python -m cotejo ejecutar --solo C-05 C-06
    python -m cotejo verificar <ejecucion>    # recalcula las huellas del almacen
    python -m cotejo comparar <ej-a> <ej-b>   # reproducibilidad entre evaluadores
    python -m cotejo catalogo                 # muestra la matriz de controles
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .contexto import Contexto, ErrorContexto
from .ejecutor import ErrorCatalogo, cargar_catalogo, cobertura, ejecutar
from .informe import construir_hallazgos, escribir
from .modelos import Conclusion
from .papeles import DIR_PAPELES, comparar_ejecuciones, verificar_almacen


def _comando_ejecutar(argumentos) -> int:
    try:
        catalogo = cargar_catalogo(argumentos.catalogo)
    except ErrorCatalogo as exc:
        print(f"ERROR de catalogo: {exc}", file=sys.stderr)
        return 2

    try:
        ctx = Contexto.desde_entorno()
    except ErrorContexto as exc:
        print(f"ERROR de contexto: {exc}", file=sys.stderr)
        return 2

    print(f"Cotejo | sistema auditado: {catalogo.get('sistema_auditado')}")
    print(f"Entorno: {ctx.entorno} | interfaz: {ctx.url_api}")
    print(f"Controles del catalogo: {len(catalogo['controles'])}")
    print()

    try:
        almacen, metadatos = ejecutar(
            ctx,
            catalogo,
            base_papeles=argumentos.papeles,
            solo=argumentos.solo,
        )
    finally:
        ctx.cerrar()

    metadatos["ejecucion_id"] = almacen.ejecucion_id
    resumen = cobertura(almacen, catalogo)
    papeles = almacen.papeles

    for papel in papeles:
        print(f"  [{papel.conclusion:>13}] {papel.control_id}  {papel.resumen[:88]}")

    hallazgos = construir_hallazgos(papeles, catalogo)
    rutas = escribir(almacen.base, metadatos, resumen, papeles, hallazgos)

    print()
    print(f"Cobertura: {resumen['cobertura']} controles con resultado")
    print(f"  conformes {resumen['conformes']} | desviados {resumen['desviados']} "
          f"| no ejecutados {resumen['no_ejecutados']}")
    print(f"Hallazgos: {len(hallazgos)} "
          f"({sum(1 for h in hallazgos if h.permanente)} permanentes)")
    print()
    print(f"Papeles de trabajo: {almacen.base}")
    print(f"Informe:            {rutas['texto']}")

    # Codigo de salida: 1 si hay desviaciones, 3 si algo no pudo comprobarse.
    # Distinguirlos importa: no es lo mismo un control que fallo que uno que no
    # se probo, y una integracion automatica no deberia tratarlos igual.
    if resumen["desviados"]:
        return 1
    if resumen["no_ejecutados"]:
        return 3
    return 0


def _comando_verificar(argumentos) -> int:
    base = Path(argumentos.ejecucion)
    if not base.is_absolute() and not base.exists():
        base = DIR_PAPELES / argumentos.ejecucion

    resultado = verificar_almacen(base)
    if resultado["almacen_integro"]:
        print(f"Almacen integro: {resultado['papeles_verificados']} papeles verificados.")
        print("Cada huella recalculada coincide con la registrada en el indice.")
        return 0

    print("ALMACEN NO INTEGRO. Discrepancias encontradas:")
    for discrepancia in resultado.get("discrepancias", []) or []:
        print(f"  - {discrepancia['control_id']}: {discrepancia['tipo']} "
              f"({discrepancia.get('archivo', '')})")
    if not resultado.get("discrepancias"):
        print(f"  {resultado.get('motivo')}")
    return 1


def _comando_comparar(argumentos) -> int:
    def resolver(nombre: str) -> Path:
        ruta = Path(nombre)
        return ruta if ruta.exists() else DIR_PAPELES / nombre

    resultado = comparar_ejecuciones(resolver(argumentos.ejecucion_a), resolver(argumentos.ejecucion_b))
    print(f"Controles comparados: {resultado['controles_comparados']}")
    print(f"Clasificaciones coincidentes: {resultado['coincidencias']}")

    if resultado["reproducible"]:
        print("REPRODUCIBLE: ambas ejecuciones clasifican igual cada control.")
        return 0

    print("NO REPRODUCIBLE. Diferencias:")
    for diferencia in resultado["diferencias"]:
        print(f"  - {diferencia['control_id']}: "
              f"{diferencia['ejecucion_a']} vs {diferencia['ejecucion_b']}")
    return 1


def _comando_catalogo(argumentos) -> int:
    try:
        catalogo = cargar_catalogo(argumentos.catalogo)
    except ErrorCatalogo as exc:
        print(f"ERROR de catalogo: {exc}", file=sys.stderr)
        return 2

    print(f"Catalogo version {catalogo.get('version')} | "
          f"sistema auditado: {catalogo.get('sistema_auditado')}")
    print()
    for control in catalogo["controles"]:
        print(f"{control.id}  [{control.tipo}]  severidad {control.severidad_si_desviado}")
        print(f"    {control.control}")
        print(f"    Marco:    {control.marco}")
        print(f"    Criterio: {control.criterio}")
        print()

    permanentes = catalogo.get("hallazgos_permanentes", [])
    if permanentes:
        print(f"Hallazgos permanentes declarados fuera del alcance automatizado: {len(permanentes)}")
        for entrada in permanentes:
            print(f"  {entrada['id']} (severidad {entrada['severidad']})")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cotejo",
        description="Programa de auditoria de sistemas con papeles de trabajo reproducibles.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    ejecutar_cmd = sub.add_parser("ejecutar", help="Recorre el catalogo de controles")
    ejecutar_cmd.add_argument("--catalogo", type=Path, default=None)
    ejecutar_cmd.add_argument("--papeles", type=Path, default=None, help="Directorio de salida")
    ejecutar_cmd.add_argument("--solo", nargs="*", default=None, help="Identificadores de control")
    ejecutar_cmd.set_defaults(funcion=_comando_ejecutar)

    verificar_cmd = sub.add_parser("verificar", help="Recalcula las huellas de una ejecucion")
    verificar_cmd.add_argument("ejecucion")
    verificar_cmd.set_defaults(funcion=_comando_verificar)

    comparar_cmd = sub.add_parser("comparar", help="Compara dos ejecuciones (reproducibilidad)")
    comparar_cmd.add_argument("ejecucion_a")
    comparar_cmd.add_argument("ejecucion_b")
    comparar_cmd.set_defaults(funcion=_comando_comparar)

    catalogo_cmd = sub.add_parser("catalogo", help="Muestra la matriz de controles")
    catalogo_cmd.add_argument("--catalogo", type=Path, default=None)
    catalogo_cmd.set_defaults(funcion=_comando_catalogo)

    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = construir_parser().parse_args(argv)
    return argumentos.funcion(argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
