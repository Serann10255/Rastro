"""Centro de operaciones y catálogo de estados.

La lista de módulos **sale de la base de datos**, no de una constante escrita
aquí: dos empresas pueden tener contratado un conjunto distinto, y dar de alta
uno nuevo no puede exigir reconstruir la aplicación.

Los módulos que todavía no existen aparecen igualmente, marcados como no
disponibles y con la razón. Ocultarlos daría a entender que el sistema no los
contempla; decir qué falta y por qué es lo que permite planear.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from rastro_app.consultas import use_catalogo_estados, use_envios, use_estados_finales, use_maestro, use_modulos
from rastro_app.contexto import icono, use_app, use_sesion


@ft.component
def TarjetaModulo(modulo: dict, contador: int | None, activo: bool) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    nombre: list[ft.Control] = [ft.Text(modulo["nombre"], size=d.T_MD, weight=ft.FontWeight.W_700)]
    if contador is not None:
        nombre.append(ui.Insignia(str(contador)))
    textos: list[ft.Control] = [
        ft.Row(nombre, spacing=d.E2, wrap=True),
        ft.Text(modulo.get("descripcion", ""), size=d.T_SM, color=p["texto-suave"]),
    ]
    if not activo and modulo.get("motivo"):
        textos.append(ft.Text(modulo["motivo"], size=d.T_XS, color=p["alerta"], italic=True))
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    ft.Icon(icono(modulo.get("icono", "")), size=20, color=p["acento"] if activo else p["texto-tenue"]),
                    width=40,
                    height=40,
                    border_radius=d.R_MD,
                    bgcolor=p["acento-suave"] if activo else p["fondo-sutil"],
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(textos, spacing=d.E1, expand=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=d.E3,
        ),
        padding=d.E4,
        bgcolor=p["superficie"] if activo else p["superficie-hundida"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_LG,
        opacity=1 if activo else 0.8,
        on_click=(lambda _e: app.ir(modulo["ruta"])) if activo and modulo.get("ruta") else None,
        ink=activo,
    )


@ft.component
def Operaciones() -> ft.Control:
    sesion = use_sesion()
    modulos = use_modulos()
    envios = use_envios()
    tiendas = use_maestro("tiendas")
    clientes = use_maestro("clientes")
    transportistas = use_maestro("transportistas")
    catalogo = use_catalogo_estados()
    es_final = use_estados_finales()

    # Los contadores los resuelve la interfaz porque son datos que ya tiene: el
    # módulo solo declara cuál le corresponde. Pedir al servidor un recuento por
    # módulo serían catorce consultas para pintar un menú.
    contadores = {
        "envios_abiertos": sum(1 for e in (envios.datos or {}).get("envios", []) if not es_final(e["estado"])),
        "tiendas": (tiendas.datos or {}).get("total"),
        "clientes": (clientes.datos or {}).get("total"),
        "transportistas": (transportistas.datos or {}).get("total"),
        "estados": len((catalogo.datos or {}).get("estados", [])) or None,
    }
    visibles = [m for m in (modulos.datos or {}).get("modulos", []) if sesion.tiene_grupo(*m.get("grupos", []))]
    disponibles = [m for m in visibles if m.get("disponible")]
    pendientes = [m for m in visibles if not m.get("disponible")]
    columnas = {"xs": 12, "md": 6, "xl": 4}

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Operaciones",
            "Módulos de la organización. Solo aparecen los que corresponden a su rol: ofrecerle un acceso "
            "que el servidor va a rechazar solo produce intentos fallidos y ruido en la auditoría.",
        )
    ]
    if modulos.error:
        partes.append(ui.Aviso("No fue posible cargar los módulos de la organización.", tono="error"))
    if modulos.cargando:
        partes.append(ui.Cargando("Cargando módulos…"))
    else:
        partes.append(
            ui.Rejilla(
                [
                    TarjetaModulo(m, contadores.get(m.get("contador") or ""), True, key=m["clave"])
                    for m in disponibles
                ],
                columnas,
            )
        )
    if pendientes:
        partes.append(
            ui.Tarjeta(
                ui.Rejilla([TarjetaModulo(m, None, False, key=m["clave"]) for m in pendientes], columnas),
                titulo="Módulos no disponibles",
                ayuda="Se listan con la razón en lugar de ocultarse: saber qué falta y por qué es lo que permite planear.",
            )
        )
    return ft.Column(partes, spacing=d.E4)


@ft.component
def CatalogoEstados() -> ft.Control:
    """Cada estado tiene un código numérico único: es lo que viaja en los
    archivos de intercambio, donde un nombre en texto es frágil."""
    catalogo = use_catalogo_estados()
    p = ui.paleta()
    filas = []
    for estado in (catalogo.datos or {}).get("estados", []):
        cierre: ft.Control = (
            ui.Insignia("exitoso" if estado.get("exitoso") else "por excepción", "exito" if estado.get("exitoso") else "peligro")
            if estado.get("final")
            else ft.Text("—", color=p["texto-tenue"])
        )
        filas.append(
            [
                ft.Text(str(estado["codigo"]), weight=ft.FontWeight.W_700, color=d.color_de_estado(p, estado["estado"])),
                ft.Text(estado["estado"], font_family=d.FUENTE_MONO, size=d.T_SM),
                estado.get("etiqueta", ""),
                (estado.get("fase") or "").capitalize(),
                ft.Text(estado.get("descripcion", ""), size=d.T_SM, width=320),
                cierre,
            ]
        )
    return ft.Column(
        [
            ui.Encabezado(
                "Catálogo de estados",
                "Cada estado tiene un código numérico único. El código existe por una razón operativa: es lo "
                "que viaja en los archivos de intercambio con transportistas y clientes, donde un nombre en "
                "texto es frágil —cambia con el idioma y con quién escriba el archivo— mientras que un número no.",
            ),
            ui.Aviso(
                "Dejan sitio para intercalar estados sin renumerar los existentes, que obligaría a reprocesar "
                "todo el histórico.",
                tono="info",
                titulo="Los saltos de diez son deliberados",
            ),
            *([ui.Aviso("No fue posible cargar el catálogo.", tono="error")] if catalogo.error else []),
            ui.Tarjeta(
                ui.Cargando()
                if catalogo.cargando
                else ui.TablaDesplazable(["Código", "Estado", "Etiqueta", "Fase", "Descripción", "Cierre"], filas, ancho_minimo=860)
            ),
        ],
        spacing=d.E4,
    )
