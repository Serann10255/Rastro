"""Guías en PDF, compuestas en el dispositivo.

La interfaz web imprime con el navegador (`@media print`). Una aplicación de
escritorio o de teléfono no tiene ese recurso, así que aquí se escribe el PDF
directamente: una guía por página de 100 × 150 mm, el tamaño de las etiquetas de
las impresoras térmicas de guías.

Se escribe a mano por la misma razón que el código de barras: el formato que
hace falta son rectángulos y texto en las fuentes estándar del lector, que caben
en unas pocas líneas. Una biblioteca de composición sería una dependencia más
que empaquetar en el APK y que auditar.

Qué datos salen en la guía lo decide el servidor (`POST /envios/etiquetas`), no
este módulo. En particular, la guía no lleva el valor declarado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rastro_app.codigo_barras import barras

MM = 72 / 25.4
ANCHO = 100 * MM
ALTO = 150 * MM
MARGEN = 6 * MM

# Anchos de Helvetica en milésimas de cuerpo (métricas AFM estándar), para
# partir líneas sin salirse de la etiqueta. Lo que no está aquí se mide como
# una letra media.
_ANCHOS = dict(
    zip(
        " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
        (
            278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
            556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
            1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
            667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
            333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
            556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
        ),
    )
)


def ancho_texto(texto: str, cuerpo: float, negrita: bool = False) -> float:
    unidades = sum(_ANCHOS.get(c, 556) for c in texto)
    # La negrita es algo más ancha; medirla con holgura evita que se salga.
    return unidades * cuerpo / 1000 * (1.07 if negrita else 1.0)


def partir(texto: str, ancho: float, cuerpo: float, negrita: bool = False) -> list[str]:
    """Parte el texto en líneas que caben en `ancho`. Una palabra más larga que
    la línea se corta por caracteres: una dirección sin espacios no puede
    desbordar la etiqueta."""
    lineas: list[str] = []
    actual = ""
    for palabra in texto.split():
        candidata = f"{actual} {palabra}".strip()
        if ancho_texto(candidata, cuerpo, negrita) <= ancho:
            actual = candidata
            continue
        if actual:
            lineas.append(actual)
        actual = palabra
        while ancho_texto(actual, cuerpo, negrita) > ancho and len(actual) > 1:
            corte = len(actual) - 1
            while corte > 1 and ancho_texto(actual[:corte], cuerpo, negrita) > ancho:
                corte -= 1
            lineas.append(actual[:corte])
            actual = actual[corte:]
    if actual:
        lineas.append(actual)
    return lineas


def _cadena(texto: str) -> str:
    """Cadena literal de PDF en WinAnsi: cubre las tildes y la eñe del español."""
    codificado = texto.encode("cp1252", errors="replace").decode("latin-1")
    return "(" + codificado.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


class _Lienzo:
    """Las órdenes de dibujo de una página, con el origen arriba a la izquierda
    como en la pantalla: es más fácil de leer que el origen abajo del PDF."""

    def __init__(self) -> None:
        self.ordenes: list[str] = []

    def texto(self, x: float, y: float, texto: str, cuerpo: float, fuente: str = "F1", gris: float = 0) -> None:
        self.ordenes.append(
            f"BT {gris:.2f} g /{fuente} {cuerpo:.2f} Tf {x:.2f} {ALTO - y:.2f} Td {_cadena(texto)} Tj ET"
        )

    def rectangulo(self, x: float, y: float, ancho: float, alto: float, gris: float = 0) -> None:
        self.ordenes.append(f"{gris:.2f} g {x:.3f} {ALTO - y - alto:.3f} {ancho:.3f} {alto:.3f} re f")

    def linea(self, x1: float, y: float, x2: float, gris: float = 0.6) -> None:
        self.ordenes.append(f"{gris:.2f} G 0.6 w {x1:.2f} {ALTO - y:.2f} m {x2:.2f} {ALTO - y:.2f} l S")

    def contenido(self) -> bytes:
        return "\n".join(self.ordenes).encode("latin-1")


def _fecha(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso or ""


def _guia(etiqueta: dict[str, Any]) -> bytes:
    lienzo = _Lienzo()
    util = ANCHO - 2 * MARGEN
    y = MARGEN

    # Cabecera: quién envía y cuándo.
    lienzo.texto(MARGEN, y + 10, etiqueta.get("empresa", "")[:40], 11, "F2")
    if etiqueta.get("empresa_nit"):
        lienzo.texto(MARGEN, y + 21, f"NIT {etiqueta['empresa_nit']}", 7.5, gris=0.25)
    derecha = [_fecha(etiqueta.get("creado_en", ""))]
    if etiqueta.get("fecha_estimada"):
        derecha.append(f"Entrega: {etiqueta['fecha_estimada']}")
    for indice, texto in enumerate(derecha):
        lienzo.texto(ANCHO - MARGEN - ancho_texto(texto, 7.5), y + 9 + indice * 10, texto, 7.5)
    y += 28
    lienzo.linea(MARGEN, y, ANCHO - MARGEN)
    y += 8

    # Código de barras a todo el ancho, con su texto debajo para quien no
    # tiene lector.
    envio_id = etiqueta.get("envio_id", "")
    lista, modulos = barras(envio_id)
    modulo = util / modulos
    alto_barras = 18 * MM
    for x, ancho in lista:
        lienzo.rectangulo(MARGEN + x * modulo, y, ancho * modulo, alto_barras)
    y += alto_barras + 10
    cuerpo_id = 8.2
    lienzo.texto(MARGEN + (util - len(envio_id) * cuerpo_id * 0.6) / 2, y, envio_id, cuerpo_id, "F3")
    y += 10
    lienzo.linea(MARGEN, y, ANCHO - MARGEN)
    y += 12

    # Destinatario: lo que el mensajero lee en la puerta.
    lienzo.texto(MARGEN, y, "DESTINATARIO", 6.5, "F2", gris=0.35)
    y += 14
    for linea in partir(etiqueta.get("destinatario", ""), util, 13, negrita=True)[:2]:
        lienzo.texto(MARGEN, y, linea, 13, "F2")
        y += 15
    for campo in ("direccion", "referencia"):
        for linea in partir(etiqueta.get(campo) or "", util, 9.5)[:3]:
            lienzo.texto(MARGEN, y, linea, 9.5)
            y += 12
    ciudad = etiqueta.get("ciudad", "")
    lienzo.texto(MARGEN, y, ciudad, 9.5, "F2")
    if etiqueta.get("telefono"):
        lienzo.texto(MARGEN + ancho_texto(ciudad, 9.5, True) + 4, y, f"· Tel. {etiqueta['telefono']}", 9.5)
    y += 8
    lienzo.linea(MARGEN, y, ANCHO - MARGEN)
    y += 12

    # Origen y transportista en dos columnas.
    mitad = util / 2
    columnas = (
        ("ORIGEN", etiqueta.get("tienda_nombre") or etiqueta.get("origen", "")),
        ("TRANSPORTISTA", etiqueta.get("transportista") or "por asignar"),
    )
    alto_columnas = 0
    for indice, (termino, valor) in enumerate(columnas):
        x = MARGEN + indice * mitad
        lienzo.texto(x, y, termino, 6.5, "F2", gris=0.35)
        lineas = partir(valor, mitad - 6, 8.5)[:3]
        for numero, linea in enumerate(lineas):
            lienzo.texto(x, y + 12 + numero * 10.5, linea, 8.5)
        alto_columnas = max(alto_columnas, 12 + len(lineas) * 10.5)
    y += alto_columnas + 4

    if etiqueta.get("descripcion"):
        lienzo.texto(MARGEN, y, "CONTENIDO", 6.5, "F2", gris=0.35)
        y += 12
        for linea in partir(etiqueta["descripcion"], util, 8.5)[:3]:
            lienzo.texto(MARGEN, y, linea, 8.5)
            y += 10.5

    # Pie: bultos, peso y orden de compra, siempre abajo.
    pie_y = ALTO - MARGEN - 4
    lienzo.linea(MARGEN, pie_y - 14, ANCHO - MARGEN)
    bultos = int(etiqueta.get("bultos") or 1)
    partes = [f"{bultos} bulto{'' if bultos == 1 else 's'}"]
    if float(etiqueta.get("peso_kg") or 0) > 0:
        partes.append(f"{etiqueta['peso_kg']} kg")
    if etiqueta.get("orden_compra"):
        partes.append(f"OC {etiqueta['orden_compra']}")
    lienzo.texto(MARGEN, pie_y, "   ·   ".join(partes), 9, "F2")
    return lienzo.contenido()


def componer(etiquetas: list[dict[str, Any]]) -> bytes:
    """Un PDF con una guía por página."""
    objetos: list[bytes] = []

    def agregar(cuerpo: bytes) -> int:
        objetos.append(cuerpo)
        return len(objetos)

    catalogo = agregar(b"")  # se completa al final, cuando se conocen las páginas
    paginas = agregar(b"")
    fuentes = {
        nombre: agregar(
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} /Encoding /WinAnsiEncoding >>".encode()
        )
        for nombre, base in (("F1", "Helvetica"), ("F2", "Helvetica-Bold"), ("F3", "Courier"))
    }
    recursos = " ".join(f"/{nombre} {numero} 0 R" for nombre, numero in fuentes.items())

    hijas = []
    for etiqueta in etiquetas:
        contenido = _guia(etiqueta)
        flujo = agregar(b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream")
        hijas.append(
            agregar(
                (
                    f"<< /Type /Page /Parent {paginas} 0 R /MediaBox [0 0 {ANCHO:.2f} {ALTO:.2f}] "
                    f"/Resources << /Font << {recursos} >> >> /Contents {flujo} 0 R >>"
                ).encode()
            )
        )

    objetos[catalogo - 1] = f"<< /Type /Catalog /Pages {paginas} 0 R >>".encode()
    objetos[paginas - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{h} 0 R' for h in hijas)}] /Count {len(hijas)} >>".encode()
    )

    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicion in posiciones:
        salida += f"{posicion:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root {catalogo} 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(salida)
