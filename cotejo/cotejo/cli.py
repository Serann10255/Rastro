"""Linea de comandos de Cotejo.

    python -m cotejo ejecutar                 # recorre el catalogo completo
    python -m cotejo ejecutar --solo C-05 C-06
    python -m cotejo verificar <ejecucion>    # recalcula las huellas del almacen
    python -m cotejo comparar <ej-a> <ej-b>   # reproducibilidad entre evaluadores
    python -m cotejo catalogo                 # muestra la matriz de controles
    python -m cotejo glosario                 # explica cada termino del oficio

La consola dice lo mismo que la interfaz web y con las mismas palabras: las dos
leen el lenguaje llano del catalogo en lugar de escribir cada una el suyo. Que
la palabra llana vaya primero y el termino tecnico detras no es una concesion,
es el orden en que se lee: quien mira la salida de reojo necesita saber si algo
se rompio antes de acordarse de que significa NO_EJECUTADA.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from .contexto import Contexto, ErrorContexto
from .ejecutor import ErrorCatalogo, cargar_catalogo, cobertura, ejecutar
from .informe import construir_hallazgos, escribir, frase_de_resultado
from .modelos import Conclusion, en_palabras
from .papeles import DIR_PAPELES, comparar_ejecuciones, verificar_almacen

#: Ancho de la consola. El mismo del informe, para que un bloque copiado de una
#: a otro no cambie de forma.
ANCHO = 78


def _parrafo(texto: str, sangria: int = 0) -> None:
    """Imprime un parrafo envuelto. Una linea de 300 caracteres no se lee."""
    if not texto:
        return
    relleno = " " * sangria
    print(
        textwrap.fill(
            texto, ANCHO - sangria, initial_indent=relleno, subsequent_indent=relleno
        )
    )


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
    print()
    _parrafo(catalogo.get("que_es_esto", ""))
    print()
    print(f"Voy a comprobar {len(catalogo['controles'])} cosas, una por una:")
    for control in catalogo["controles"]:
        print(f"  {control.id}  {control.pregunta}")
    print()
    print("Cada una responde BIEN, MAL o SIN REVISAR. Vamos:")
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
        # La palabra llana primero y el termino tecnico entre parentesis: quien
        # mira la consola de reojo necesita saber si algo se rompio antes de
        # acordarse de que significa NO_EJECUTADA.
        print(f"  [{en_palabras(papel.conclusion):^11}] {papel.control_id}  {papel.pregunta}")
        print(f"                {papel.resumen}")
        print()

    hallazgos = construir_hallazgos(papeles, catalogo)
    rutas = escribir(almacen.base, metadatos, resumen, papeles, hallazgos)

    print("-" * 72)
    _parrafo(frase_de_resultado(metadatos, resumen))
    print()
    print(
        f"En terminos de auditoria: cobertura {resumen['cobertura']} | "
        f"conformes {resumen['conformes']} | desviados {resumen['desviados']} | "
        f"no ejecutados {resumen['no_ejecutados']}"
    )
    permanentes = sum(1 for h in hallazgos if h.permanente)
    print(
        f"Hallazgos: {len(hallazgos)} ({permanentes} permanentes, que se reportan "
        "siempre porque el entorno impide corregirlos)"
    )
    print()
    print(f"Las pruebas guardadas estan en: {almacen.base}")
    print(f"El informe completo esta en:    {rutas['texto']}")

    # Codigo de salida: 1 si hay desviaciones, 3 si algo no pudo comprobarse.
    # Distinguirlos importa: no es lo mismo un control que fallo que uno que no
    # se probo, y una integracion automatica no deberia tratarlos igual.
    print()
    if resumen["desviados"]:
        print("Termino con codigo 1: algo salio mal y esta explicado en el informe.")
        return 1
    if resumen["no_ejecutados"]:
        print(
            "Termino con codigo 3: nada salio mal, pero quedaron cosas sin revisar. "
            "No es lo mismo, y por eso no es el codigo 0."
        )
        return 3
    print("Termino con codigo 0: se reviso todo y todo cumplio.")
    return 0


def _comando_verificar(argumentos) -> int:
    base = Path(argumentos.ejecucion)
    if not base.is_absolute() and not base.exists():
        base = DIR_PAPELES / argumentos.ejecucion

    resultado = verificar_almacen(base)
    if resultado["almacen_integro"]:
        print(f"NADIE LAS HA TOCADO: {resultado['papeles_verificados']} pruebas comprobadas.")
        _parrafo(
            "A cada prueba guardada se le vuelve a calcular su sello y sale el "
            "mismo que se anoto el dia que se ejecuto. Si alguien hubiera "
            "cambiado una sola letra de un archivo, el sello no cuadraria."
        )
        print()
        print("En terminos de auditoria: almacen integro, huellas coincidentes.")
        return 0

    print("OJO: ALGUNA PRUEBA FUE MODIFICADA DESPUES DE GUARDARSE.")
    _parrafo(
        "El sello que sale ahora no es el que se anoto al ejecutarla. El almacen "
        "no impide que se edite un archivo: lo que hace es que se note."
    )
    print()
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

    if resultado["reproducible"]:
        print("SALE LO MISMO LAS DOS VECES.")
        _parrafo(
            f"Las {resultado['controles_comparados']} cosas revisadas dan la misma "
            "respuesta en las dos ejecuciones. Eso es lo que se busca: si el "
            "resultado dependiera de quien ejecuta el programa, no seria una "
            "medida sino una opinion."
        )
        print()
        print("En terminos de auditoria: reproducible.")
        return 0

    print("NO SALE LO MISMO. Estas cosas cambiaron de respuesta:")
    for diferencia in resultado["diferencias"]:
        print(f"  - {diferencia['control_id']}: "
              f"{en_palabras(diferencia['ejecucion_a'])} la primera vez, "
              f"{en_palabras(diferencia['ejecucion_b'])} la segunda")
    print()
    _parrafo(
        "Una diferencia no significa que el programa este mal: puede que el "
        "sistema auditado haya cambiado entre una ejecucion y otra. Hay que "
        "abrir las dos pruebas y compararlas antes de concluir."
    )
    print()
    print(
        f"En terminos de auditoria: no reproducible "
        f"({resultado['coincidencias']} de {resultado['controles_comparados']} coinciden)."
    )
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
    _parrafo(catalogo.get("que_es_esto", ""))
    print()
    print("Esto es lo que se comprueba, y se escribe ANTES de comprobarlo:")
    print()

    for control in catalogo["controles"]:
        print(f"{control.id}  {control.pregunta}")
        _parrafo(control.en_simple, sangria=4)
        _parrafo(f"Si fallara: {control.si_falla}", sangria=4)
        print(f"    [{control.tipo}] severidad {control.severidad_si_desviado} | {control.marco}")
        _parrafo(f"Criterio: {control.criterio}", sangria=4)
        print()

    permanentes = catalogo.get("hallazgos_permanentes", [])
    if permanentes:
        print("Cosas que ya sabemos que estan mal y que aqui no se pueden arreglar:")
        print()
        for entrada in permanentes:
            print(f"{entrada['id']}  (severidad {entrada['severidad']})")
            _parrafo(" ".join(str(entrada.get("en_simple", "")).split()), sangria=4)
            print()
    return 0


def _comando_glosario(argumentos) -> int:
    """Las palabras del oficio, explicadas una sola vez y en un solo sitio."""
    try:
        catalogo = cargar_catalogo(argumentos.catalogo)
    except ErrorCatalogo as exc:
        print(f"ERROR de catalogo: {exc}", file=sys.stderr)
        return 2

    entradas = catalogo.get("glosario", [])
    if not entradas:
        print("El catalogo no declara glosario.")
        return 0

    print("DICCIONARIO")
    _parrafo(
        "Los terminos de auditoria no se sustituyen: son los que espera leer un "
        "tercero. Pero nadie deberia necesitar saberlos para entender que dice "
        "una pantalla."
    )
    print()
    for entrada in entradas:
        titulo = entrada["termino"]
        if entrada.get("tambien_llamado"):
            titulo += f"  (tambien: {entrada['tambien_llamado']})"
        print(titulo)
        _parrafo(" ".join(str(entrada.get("en_simple", "")).split()), sangria=4)
        print()
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

    glosario_cmd = sub.add_parser(
        "glosario", help="Explica cada palabra del oficio sin vocabulario tecnico"
    )
    glosario_cmd.add_argument("--catalogo", type=Path, default=None)
    glosario_cmd.set_defaults(funcion=_comando_glosario)

    return parser


def main(argv: list[str] | None = None) -> int:
    _consola_en_utf8()
    argumentos = construir_parser().parse_args(argv)
    return argumentos.funcion(argumentos)


def _consola_en_utf8() -> None:
    """Escribe en UTF-8 cuando la consola lo permite.

    Las preguntas del catalogo llevan signo de apertura, y una consola de
    Windows con una pagina de codigos antigua lo pinta como un rombo. Con
    `errors="replace"` el programa nunca se detiene por no poder imprimir un
    caracter: un informe de auditoria que se cae al escribir un acento seria un
    problema mayor que el acento.
    """
    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    raise SystemExit(main())
