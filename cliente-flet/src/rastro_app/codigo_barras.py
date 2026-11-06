"""Código de barras Code 128B.

Es el mismo codificador que usa la interfaz web (`web/src/componentes/codigo-barras.tsx`),
escrito otra vez en Python porque esta aplicación no ejecuta TypeScript. Se
mantiene sin dependencia por la misma razón que allí: son 107 patrones y una
suma de control, y una biblioteca para eso arrastra su propia cadena de
suministro en un proyecto que se audita a sí mismo.

El módulo solo calcula las barras. Quien las dibuja —la pantalla con un lienzo
de Flet, el PDF con rectángulos— decide la escala.
"""

from __future__ import annotations

PATRONES = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211",
    "411212", "421112", "421211", "212141", "214121", "412121", "111143", "111341",
    "131141", "114113", "114311", "411113", "411311", "113141", "114131", "311141",
    "411131", "211412", "211214", "211232",
)

INICIO_B = 104
PARADA = "2331112"


def codificar(texto: str) -> list[str]:
    """La secuencia de símbolos del texto, con inicio, dígito de control y parada.

    El dígito de control es lo que hace que un lector rechace una lectura
    parcial en vez de devolver un identificador equivocado.
    """
    # El juego B cubre del espacio (32) a la tilde (126). Lo que no entra se
    # sustituye por un espacio: una guía con un carácter cambiado sigue siendo
    # escaneable, una sin código no.
    valores = [ord(c) - 32 if 32 <= ord(c) <= 126 else 0 for c in texto]
    suma = INICIO_B + sum(valor * (indice + 1) for indice, valor in enumerate(valores))
    return [PATRONES[INICIO_B], *(PATRONES[v] for v in valores), PATRONES[suma % 103], PARADA]


def barras(texto: str) -> tuple[list[tuple[int, int]], int]:
    """Las barras negras como (posición, ancho) en módulos, y el ancho total.

    Los dígitos de cada patrón alternan barra y espacio, empezando por barra.
    """
    resultado: list[tuple[int, int]] = []
    x = 0
    for simbolo in codificar(texto):
        for indice, digito in enumerate(simbolo):
            ancho = int(digito)
            if indice % 2 == 0:
                resultado.append((x, ancho))
            x += ancho
    return resultado, x
