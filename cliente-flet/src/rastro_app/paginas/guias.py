"""Generación de guías con código de barras.

El servidor decide qué datos salen en la guía; esta pantalla los compone. En la
web se imprimen con el navegador; aquí se guardan como PDF, una guía por página
de 100 × 150 mm, que es lo que imprime una impresora térmica de guías y lo que
abre cualquier visor (ver `guias_pdf.py`).

La guía no lleva el valor declarado: pegarlo por fuera de la caja le dice a
cualquiera cuánto vale lo que hay dentro.
"""

from __future__ import annotations

import flet as ft
import flet.canvas as cv

from comun import diseno as d
from comun import ui
from comun.datos import use_mutacion
from comun.formato import fecha_corta
from rastro_app.codigo_barras import barras
from rastro_app.contexto import mensaje_de_error, use_app
from rastro_app.guias_pdf import componer


@ft.component
def Guias() -> ft.Control:
    app = use_app()
    identificadores, _ = ft.use_state(lambda: list(app.tomar("envios_guias", []) or []))
    datos, poner_datos = ft.use_state(None)
    guardando, poner_guardando = ft.use_state(False)
    pedir = use_mutacion(app.api.etiquetas)

    async def cargar():
        # Se pide una sola vez al llegar: las guías no cambian mientras se miran.
        if identificadores:
            try:
                poner_datos(await pedir.ejecutar(identificadores))
            except Exception:  # noqa: BLE001 - se muestra en la pantalla
                pass

    ft.use_effect(cargar, [], cleanup=lambda: None)

    async def guardar_pdf():
        poner_guardando(True)
        try:
            contenido = componer(datos["etiquetas"])
            nombre = "guia.pdf" if len(datos["etiquetas"]) == 1 else f"guias-{len(datos['etiquetas'])}.pdf"
            ruta = await ft.FilePicker().save_file(dialog_title="Guardar las guías", file_name=nombre, src_bytes=contenido)
            if ruta or app.pagina.web:
                app.avisar("Guías guardadas en PDF.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")
        finally:
            poner_guardando(False)

    if not identificadores:
        return ui.Tarjeta(
            ui.Vacio(
                "No hay envíos seleccionados",
                "Elija los envíos en el listado y pulse «Generar guías».",
                ui.Boton("Ir al listado", lambda: app.ir("/envios")),
            )
        )

    etiquetas = (datos or {}).get("etiquetas", [])
    partes: list[ft.Control] = [
        ui.Encabezado(
            "Guías",
            (f"{len(etiquetas)} guías listas." if datos else "Preparando las guías…")
            + " Se guardan en PDF, una por página de 100 × 150 mm, lista para la impresora de guías.",
            [
                ui.Boton("Guardar PDF", guardar_pdf, cargando=guardando, deshabilitado=not etiquetas, icono=ft.Icons.PICTURE_AS_PDF),
                ui.Boton("Volver", lambda: app.volver("/envios"), variante="secundario"),
            ],
        )
    ]
    if pedir.error:
        partes.append(ui.Aviso(mensaje_de_error(pedir.error), tono="error", titulo="No se pudieron generar las guías"))
    if datos and datos.get("no_encontrados"):
        partes.append(
            ui.Aviso(
                "No existen o no pertenecen a su organización. El sistema responde igual en ambos casos: decir "
                "cuál es confirmaría que el otro existe.",
                tono="alerta",
                titulo=f"{len(datos['no_encontrados'])} envíos sin guía",
            )
        )
    if pedir.pendiente:
        partes.append(ui.Esqueleto(alto=320))
    if etiquetas:
        partes.append(ui.Rejilla([GuiaEnPantalla(e, key=e["envio_id"]) for e in etiquetas], {"xs": 12, "md": 6, "xl": 4}))
    return ft.Column(partes, spacing=d.E4)


@ft.component
def CodigoBarras(valor: str, alto: float = 56) -> ft.Control:
    """El código dibujado a escala del ancho disponible, siempre en negro sobre
    blanco: un lector no lee las barras claras sobre fondo oscuro."""
    lista, modulos = barras(valor)
    ancho, poner_ancho = ft.use_state(320.0)
    escala = ancho / modulos
    return ft.Container(
        content=cv.Canvas(
            shapes=[cv.Rect(x * escala, 0, a * escala, alto, paint=ft.Paint(color="#000000")) for x, a in lista],
            height=alto,
            on_resize=lambda e: poner_ancho(e.width) if e.width else None,
            expand=True,
        ),
        bgcolor="#ffffff",
        height=alto,
    )


@ft.component
def GuiaEnPantalla(etiqueta: dict) -> ft.Control:
    """La guía tal como sale en el PDF: fondo blanco y texto negro, también con
    el tema oscuro, porque es una vista previa de papel."""
    negro, gris = "#16202c", "#55637a"

    def termino(texto: str) -> ft.Text:
        return ft.Text(texto.upper(), size=10, weight=ft.FontWeight.W_700, color=gris)

    def valor(texto: str, **extra) -> ft.Text:
        return ft.Text(texto, size=d.T_SM, color=negro, selectable=True, **extra)

    bultos = int(etiqueta.get("bultos") or 1)
    pie = [f"{bultos} bulto{'' if bultos == 1 else 's'}"]
    if float(etiqueta.get("peso_kg") or 0) > 0:
        pie.append(f"{etiqueta['peso_kg']} kg")
    if etiqueta.get("orden_compra"):
        pie.append(f"OC {etiqueta['orden_compra']}")

    linea_ciudad = etiqueta.get("ciudad", "") + (f" · Tel. {etiqueta['telefono']}" if etiqueta.get("telefono") else "")
    contenido: list[ft.Control] = [
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(etiqueta.get("empresa", ""), size=d.T_MD, weight=ft.FontWeight.W_800, color=negro),
                        *([ft.Text(f"NIT {etiqueta['empresa_nit']}", size=10, color=gris)] if etiqueta.get("empresa_nit") else []),
                    ],
                    spacing=0,
                    expand=True,
                ),
                ft.Column(
                    [
                        ft.Text(fecha_corta(etiqueta.get("creado_en")), size=10, color=negro),
                        *([ft.Text(f"Entrega: {etiqueta['fecha_estimada']}", size=10, color=negro)] if etiqueta.get("fecha_estimada") else []),
                    ],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        CodigoBarras(etiqueta["envio_id"]),
        ft.Text(etiqueta["envio_id"], size=11, font_family=d.FUENTE_MONO, color=negro, text_align=ft.TextAlign.CENTER, selectable=True),
        ft.Divider(height=1, color="#c3ccd9"),
        termino("Destinatario"),
        ft.Text(etiqueta.get("destinatario", ""), size=d.T_LG, weight=ft.FontWeight.W_800, color=negro),
        valor(etiqueta.get("direccion", "")),
        *([valor(etiqueta["referencia"])] if etiqueta.get("referencia") else []),
        valor(linea_ciudad, weight=ft.FontWeight.W_600),
        ft.Divider(height=1, color="#c3ccd9"),
        ft.Row(
            [
                ft.Column([termino("Origen"), valor(etiqueta.get("tienda_nombre") or etiqueta.get("origen", ""))], spacing=2, expand=True),
                ft.Column([termino("Transportista"), valor(etiqueta.get("transportista") or "por asignar")], spacing=2, expand=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
    ]
    if etiqueta.get("descripcion"):
        contenido += [termino("Contenido"), valor(etiqueta["descripcion"])]
    contenido += [ft.Divider(height=1, color="#c3ccd9"), ft.Text("   ·   ".join(pie), size=d.T_SM, weight=ft.FontWeight.W_700, color=negro)]
    return ft.Container(
        content=ft.Column(contenido, spacing=d.E2, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        bgcolor="#ffffff",
        padding=d.E4,
        border=ft.Border.all(1, "#c3ccd9"),
        border_radius=d.R_MD,
    )
