"""Listado de órdenes con búsqueda, filtros, selección múltiple y exportación.

El filtro por organización y por conductor lo aplica el servidor, no esta
pantalla: el despachador ve los de su empresa y el conductor solo los que tiene
asignados. Lo que se filtra aquí es presentación sobre lo que el servidor ya
decidió entregar.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.formato import fecha_relativa
from rastro_app.consultas import use_catalogo_estados, use_envios, use_estados_finales
from rastro_app.contexto import BarraFija, mensaje_de_error, use_app, use_sesion

FILTROS = [
    ("activos", "En curso"),
    ("sin_asignar", "Sin asignar"),
    ("incidencia", "Incidencia"),
    ("cerrados", "Cerrados"),
    ("todos", "Todos"),
]


def _aplica(envio: dict, filtro: str, es_final) -> bool:
    """Qué estados cierran un envío lo dice el catálogo del servidor, no una
    lista escrita aquí."""
    if filtro == "activos":
        return not es_final(envio["estado"])
    if filtro == "sin_asignar":
        return envio["estado"] == "CREADO"
    if filtro == "incidencia":
        return envio["estado"] == "INCIDENCIA"
    if filtro == "cerrados":
        return es_final(envio["estado"])
    return True


@ft.component
def Envios() -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    envios = use_envios()
    catalogo = use_catalogo_estados()
    es_final = use_estados_finales()

    filtro, poner_filtro = ft.use_state("activos")
    estado_exacto, poner_estado_exacto = ft.use_state("")
    busqueda, poner_busqueda = ft.use_state("")
    seleccion, poner_seleccion = ft.use_state(frozenset())
    exportando, poner_exportando = ft.use_state(False)

    # Quien no puede asignar solo ve los suyos: es el mismo criterio que aplica
    # el servidor, y sigue valiendo para un rol que la empresa cree mañana.
    solo_conductor = not sesion.puede("envio:asignar")
    puede_generar_guias = sesion.puede("envio:consultar")

    termino = busqueda.strip().lower()
    todos = (envios.datos or {}).get("envios", [])
    visibles = [
        e
        for e in todos
        if (e["estado"] == estado_exacto if estado_exacto else _aplica(e, filtro, es_final))
        and (
            not termino
            or termino
            in " ".join(
                str(x or "")
                for x in (
                    e.get("destinatario"),
                    e.get("destino"),
                    e.get("envio_id"),
                    e.get("orden_compra"),
                    e.get("cliente_nombre"),
                    e.get("conductor_nombre"),
                    e.get("codigo_estado"),
                )
            ).lower()
        )
    ]
    todos_seleccionados = bool(visibles) and all(e["envio_id"] in seleccion for e in visibles)

    async def exportar():
        poner_exportando(True)
        try:
            nombre, contenido = await app.api.exportar_envios()
            ruta = await ft.FilePicker().save_file(
                dialog_title="Guardar la exportación", file_name=nombre, src_bytes=contenido
            )
            if ruta or app.pagina.web:
                app.avisar("Archivo guardado.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")
        finally:
            poner_exportando(False)

    # La barra de selección va fija al pie: marcar veinte órdenes e imprimir sus
    # guías es la operación diaria, y no puede exigir bajar al final de la lista.
    def mostrar_barra():
        if not seleccion:
            app.poner_barra(None)
            return
        cantidad = len(seleccion)
        app.poner_barra(
            BarraFija(
                f"{cantidad} envío{'' if cantidad == 1 else 's'} seleccionado{'' if cantidad == 1 else 's'}",
                (
                    ("Generar guías", lambda: app.ir("/envios/guias", envios_guias=sorted(seleccion)), "primario"),
                    ("Cancelar", lambda: poner_seleccion(frozenset()), "secundario"),
                ),
            )
        )

    ft.use_effect(mostrar_barra, [seleccion], cleanup=lambda: app.poner_barra(None))

    def alternar(envio_id: str):
        poner_seleccion(lambda previa: previa - {envio_id} if envio_id in previa else previa | {envio_id})

    acciones = [ui.Boton("Exportar CSV", exportar, variante="secundario", cargando=exportando, icono=ft.Icons.DOWNLOAD)]
    if sesion.puede("envio:crear"):
        acciones.append(ui.Boton("Registrar", lambda: app.ir("/envios/nuevo"), icono=ft.Icons.ADD))

    opciones_estado = [("", "Usar filtro rápido")] + [
        (e["estado"], f"{e['codigo']} · {e['etiqueta']}") for e in (catalogo.datos or {}).get("estados", [])
    ]
    filtros = ui.Tarjeta(
        [
            ui.Rejilla(
                [
                    ui.Campo(
                        "Buscar",
                        busqueda,
                        poner_busqueda,
                        sugerencia="Destinatario, dirección, guía, orden de compra o código",
                    ),
                    ui.Selector(
                        "Estado exacto",
                        estado_exacto,
                        opciones_estado,
                        poner_estado_exacto,
                        ayuda="El código es el que viaja en los archivos de intercambio.",
                    ),
                    ft.Row(
                        [ui.Boton("Actualizar", envios.recargar, variante="secundario", cargando=envios.refrescando, icono=ft.Icons.REFRESH)]
                    ),
                ],
                {"xs": 12, "md": 6, "lg": 4},
            ),
            *([ui.GrupoSegmentado(filtro, FILTROS, poner_filtro)] if not estado_exacto else []),
        ]
    )

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Mis envíos" if solo_conductor else "Órdenes",
            "Solo aparecen los envíos que le fueron asignados. El filtro lo aplica el servidor."
            if solo_conductor
            else "Envíos de su organización. Los datos de otras empresas no son alcanzables desde aquí.",
            acciones,
        ),
        filtros,
    ]
    if envios.error:
        partes.append(ui.Aviso(mensaje_de_error(envios.error), tono="error"))

    if envios.cargando:
        partes.append(ui.ListaEsqueleto(5))
    elif not visibles:
        partes.append(
            ui.Tarjeta(
                ui.Vacio(
                    "Ningún envío coincide" if busqueda else "No hay envíos en este filtro",
                    "Pruebe con otro término o cambie el filtro."
                    if busqueda
                    else "Cuando el despachador le asigne un envío, aparecerá aquí."
                    if solo_conductor
                    else "Registre un envío para empezar.",
                    ui.Boton("Limpiar búsqueda", lambda: poner_busqueda(""), variante="secundario") if busqueda else None,
                )
            )
        )
    else:
        cabecera: list[ft.Control] = [ui.Texto(f"{len(visibles)} de {(envios.datos or {}).get('total', 0)} envíos", tono="texto-suave")]
        if puede_generar_guias:
            cabecera.append(
                ui.Boton(
                    "Quitar selección" if todos_seleccionados else "Seleccionar todo",
                    lambda: poner_seleccion(frozenset() if todos_seleccionados else frozenset(e["envio_id"] for e in visibles)),
                    variante="sutil",
                )
            )
        partes.append(ft.Row(cabecera, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True))
        partes.append(
            ft.Column(
                [
                    FilaEnvio(
                        e,
                        mostrar_conductor=not solo_conductor,
                        seleccionable=puede_generar_guias,
                        seleccionado=e["envio_id"] in seleccion,
                        al_alternar=alternar,
                        key=e["envio_id"],
                    )
                    for e in visibles
                ],
                spacing=d.E2,
            )
        )

    return ft.Column(partes, spacing=d.E4)


@ft.component
def FilaEnvio(envio: dict, mostrar_conductor: bool, seleccionable: bool, seleccionado: bool, al_alternar) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    lineas: list[ft.Control] = [
        ft.Row(
            [
                ft.Text(envio["destinatario"], size=d.T_MD, weight=ft.FontWeight.W_600, expand=True),
                ui.EtiquetaEstado(envio["estado"], envio.get("codigo_estado"), con_punto=True),
            ],
            spacing=d.E2,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        ui.Texto(
            envio.get("destino", "") + (f" · {envio['ciudad_destino']}" if envio.get("ciudad_destino") else ""),
            tono="texto-suave",
            seleccionable=False,
        ),
    ]
    if envio.get("orden_compra") or envio.get("cliente_nombre"):
        partes = [x for x in (envio.get("cliente_nombre"), f"OC {envio['orden_compra']}" if envio.get("orden_compra") else None) if x]
        lineas.append(ui.Texto(" · ".join(partes), tono="texto-suave", seleccionable=False))
    lineas.append(
        ft.Row(
            [
                ft.Text(envio["envio_id"], size=d.T_XS, font_family=d.FUENTE_MONO, color=p["texto-tenue"], expand=True, selectable=True),
                ft.Text(
                    (f"{envio['conductor_nombre']} · " if mostrar_conductor and envio.get("conductor_nombre") else "")
                    + fecha_relativa(envio.get("actualizado_en")),
                    size=d.T_XS,
                    color=p["texto-tenue"],
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )
    cuerpo = ft.Container(
        content=ft.Column(lineas, spacing=d.E1),
        expand=True,
        on_click=lambda _e: app.ir(f"/envios/{envio['envio_id']}"),
        padding=ft.Padding.symmetric(vertical=d.E1),
    )
    fila: list[ft.Control] = []
    if seleccionable:
        fila.append(ft.Checkbox(value=seleccionado, on_change=lambda _e: al_alternar(envio["envio_id"])))
    fila.append(cuerpo)
    return ft.Container(
        content=ft.Row(fila, vertical_alignment=ft.CrossAxisAlignment.START, spacing=d.E2),
        padding=ft.Padding.symmetric(horizontal=d.E3, vertical=d.E2),
        bgcolor=p["superficie"],
        border=ft.Border(
            left=ft.BorderSide(4, d.color_de_estado(p, envio["estado"])),
            top=ft.BorderSide(1, p["borde"]),
            right=ft.BorderSide(1, p["borde"]),
            bottom=ft.BorderSide(1, p["borde"]),
        ),
        border_radius=d.R_MD,
    )
