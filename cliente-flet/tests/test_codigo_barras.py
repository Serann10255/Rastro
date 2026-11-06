"""Code 128B: el mismo codificador que la interfaz web."""

from rastro_app.codigo_barras import PARADA, PATRONES, barras, codificar


def test_cada_patron_mide_once_modulos():
    # La tabla que se copió de la web traía dos patrones de trece módulos que
    # no existen en Code 128 («141142» y «141241») y corría todos los valores
    # desde el 83, incluido el inicio B: ningún lector leía esas guías.
    assert len(PATRONES) == 106
    assert all(sum(int(d) for d in patron) == 11 for patron in PATRONES)
    assert sum(int(d) for d in PARADA) == 13


def test_valores_de_referencia_de_la_norma():
    # ISO/IEC 15417: algunos valores con su patrón, incluidos los de control.
    referencia = {0: "212222", 33: "111323", 64: "111422", 83: "114212", 95: "114113", 99: "113141", 102: "411131"}
    assert all(PATRONES[valor] == patron for valor, patron in referencia.items())
    assert PATRONES[103:] == ("211412", "211214", "211232")  # inicios A, B y C


def test_codifica_con_inicio_control_y_parada():
    # «A» vale 33 en el juego B; control = (104 + 33·1) mod 103 = 34.
    assert codificar("A") == [PATRONES[104], PATRONES[33], PATRONES[34], PARADA]


def test_el_control_pondera_por_posicion():
    # «AB»: (104 + 33·1 + 34·2) mod 103 = 205 mod 103 = 102.
    assert codificar("AB")[-2] == PATRONES[102]


def test_un_caracter_fuera_del_juego_b_no_rompe_el_codigo():
    assert codificar("ñ")[1] == PATRONES[0]


def test_ancho_total_de_un_identificador():
    lista, modulos = barras("9a757182-3c1f-4e2b-8d6a-1b2c3d4e5f60")
    # Inicio + 36 caracteres + control, de once módulos, y la parada de trece.
    assert modulos == 38 * 11 + 13
    assert all(ancho in (1, 2, 3, 4) for _x, ancho in lista)
