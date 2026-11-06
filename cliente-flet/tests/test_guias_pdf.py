"""Guías en PDF: un documento válido, una guía por página y sin valor declarado."""

import re

from rastro_app.guias_pdf import ANCHO, MARGEN, ancho_texto, componer, partir

ETIQUETA = {
    "envio_id": "9a757182-3c1f-4e2b-8d6a-1b2c3d4e5f60",
    "empresa": "Mensajería Andes S.A.S.",
    "empresa_nit": "901.455.782-3",
    "destinatario": "Laura Mejía Ríos",
    "direccion": "Carrera 7 #32-16 apartamento 1204 torre norte conjunto residencial",
    "ciudad": "Bogotá",
    "telefono": "3001110001",
    "bultos": 2,
    "peso_kg": 3.2,
    "orden_compra": "OC-2026-1001",
    "creado_en": "2026-10-23T15:00:00Z",
    # La guía no debe imprimirlo aunque llegue: va pegada a la caja.
    "valor_declarado": 987654321,
}


def test_es_un_pdf_con_una_pagina_por_guia():
    pdf = componer([ETIQUETA, {**ETIQUETA, "envio_id": "b31c04a7-0000-4000-8000-000000000001"}])
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"/Count 2" in pdf
    assert len(re.findall(rb"/Type /Page\b", pdf)) == 2


def test_la_tabla_de_referencias_apunta_a_cada_objeto():
    pdf = componer([ETIQUETA])
    inicio = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
    assert pdf[inicio:].startswith(b"xref")
    posiciones = [int(p) for p in re.findall(rb"(\d{10}) 00000 n", pdf)]
    for numero, posicion in enumerate(posiciones, start=1):
        assert pdf[posicion:].startswith(f"{numero} 0 obj".encode())


def test_no_imprime_el_valor_declarado():
    assert b"987654321" not in componer([ETIQUETA])


def test_las_tildes_viajan_en_winansi():
    assert "Mejía".encode("cp1252") in componer([ETIQUETA])


def test_una_palabra_mas_larga_que_la_linea_se_corta():
    lineas = partir("x" * 200, 100, 10)
    assert len(lineas) > 1
    assert all(ancho_texto(linea, 10) <= 100 for linea in lineas)


def test_las_lineas_caben_en_la_etiqueta():
    util = ANCHO - 2 * MARGEN
    for linea in partir(ETIQUETA["direccion"], util, 9.5):
        assert ancho_texto(linea, 9.5) <= util
