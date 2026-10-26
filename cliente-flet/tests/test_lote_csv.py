"""Lectura del archivo del lote: las mismas reglas que la interfaz web."""

from rastro_app.lote_csv import PLANTILLA, analizar, decodificar


def test_la_plantilla_se_lee_entera():
    analisis = analizar(PLANTILLA)
    assert analisis.error is None
    assert len(analisis.filas) == 2
    primera = analisis.filas[0]
    assert primera["destinatario"] == {"nombre": "Laura Mejia Rios", "telefono": "3001110001"}
    assert primera["destino"] == {"linea": "Carrera 7 #32-16", "ciudad": "Bogotá"}
    assert primera["bultos"] == 1 and primera["peso_kg"] == 0.5


def test_comillas_y_comas_dentro_de_un_campo():
    texto = 'destinatario,direccion_destino,descripcion\n"Pardo, Andrés","Calle 45 #13-05","Caja ""frágil"""\n'
    fila = analizar(texto).filas[0]
    assert fila["destinatario"]["nombre"] == "Pardo, Andrés"
    assert fila["descripcion"] == 'Caja "frágil"'


def test_valores_por_omision():
    fila = analizar("destinatario,direccion_destino\nAna,Calle 1\n").filas[0]
    assert fila["destino"]["ciudad"] == "Bogotá"
    assert fila["origen"]["linea"] == "Calle 1"
    assert fila["bultos"] == 1
    assert "telefono" not in fila["destinatario"]


def test_se_omiten_las_filas_sin_destinatario_o_direccion():
    analisis = analizar("destinatario,direccion_destino\nAna,Calle 1\n,Calle 2\nBeto,\n")
    assert len(analisis.filas) == 1
    assert analisis.ignoradas == 2


def test_faltan_columnas_obligatorias():
    assert "destinatario" in analizar("nombre,direccion\nAna,Calle 1\n").error


def test_hace_falta_al_menos_un_envio():
    assert analizar("destinatario,direccion_destino\n").error


def test_un_archivo_guardado_en_cp1252_conserva_las_tildes():
    contenido = "destinatario,direccion_destino\nMaría Peña,Calle 1\n".encode("cp1252")
    assert analizar(decodificar(contenido)).filas[0]["destinatario"]["nombre"] == "María Peña"
