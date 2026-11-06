"""Tablero de la empresa.

Los indicadores los calcula el servidor y no esta pantalla: un tablero calculado
en el cliente obliga a enviarle todos los envíos, que es lento y entrega datos
que la pantalla no necesita mostrar.

Cada rol llega buscando algo distinto: el despachador quiere ver qué está
atascado, el conductor su siguiente parada, el auditor si la cadena sigue
íntegra.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_mutacion
from comun.formato import fecha_relativa, texto_estado
from rastro_app.consultas import use_envios
from rastro_app.contexto import mensaje_de_error, use_app, use_sesion


@ft.component
def Panel() -> ft.Control:
    sesion = use_sesion()
    dias, poner_dias = ft.use_state("30")
    solo_auditor = sesion.tiene_grupo("auditor") and not sesion.tiene_grupo("administrador", "despachador", "conductor")
    empresa = sesion.empresa or {}
    usuario = sesion.usuario

    descripcion = f"{usuario.get('nombre', '')}, opera con el rol {', '.join(sesion.grupos)}."
    if empresa.get("ciudad"):
        descripcion += f" {empresa['ciudad']}, {empresa.get('departamento', '')}."
    descripcion += " Cada operación queda registrada con su identidad y su marca de tiempo."

    acciones = None
    if not solo_auditor:
        acciones = [
            ui.GrupoSegmentado(
                dias, [("7", "7 días"), ("30", "30 días"), ("90", "90 días")], poner_dias, etiqueta="Periodo"
            )
        ]

    return ft.Column(
        [
            ui.Encabezado(empresa.get("nombre") or "Panel", descripcion, acciones),
            PanelAuditor() if solo_auditor else PanelOperacion(int(dias)),
        ],
        spacing=d.E5,
    )


@ft.component
def PanelOperacion(dias: int) -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    tablero = use_consulta(app.almacen, ("tablero", dias), lambda: app.api.tablero(dias))

    if tablero.error and not tablero.datos:
        return ui.Aviso(mensaje_de_error(tablero.error), tono="error")
    if tablero.cargando or not tablero.datos:
        return ft.Column(
            [ui.Rejilla([ui.Esqueleto(alto=104) for _ in range(4)]), ui.Esqueleto(alto=320)], spacing=d.E4
        )

    datos = tablero.datos
    es_conductor = datos.get("alcance") == "propios"
    atencion = datos.get("atencion") or {}
    tasa = datos.get("tasa_entrega")

    metricas = ui.Rejilla(
        [
            ui.Metrica(
                "Asignados a usted" if es_conductor else "En curso",
                datos["totales"]["abiertos"],
                "Envíos que aún no se cerraron",
                "acento",
            ),
            ui.Metrica(
                "Entregados",
                datos["totales"]["entregados"],
                "Sin envíos cerrados todavía" if tasa is None else f"{tasa}% de los cerrados",
                "exito",
            ),
            ui.Metrica(
                "Con incidencia",
                atencion.get("con_incidencia", 0),
                "Detenidos, requieren autorización",
                "peligro" if atencion.get("con_incidencia") else None,
            ),
            ui.Metrica(
                "Sin recoger" if es_conductor else "Sin asignar",
                atencion.get("sin_asignar", 0),
                "Esperan mensajero",
                "alerta" if atencion.get("sin_asignar") else None,
            ),
        ],
        {"xs": 12, "sm": 6, "lg": 3},
    )

    partes: list[ft.Control] = [metricas]
    if atencion.get("estancados"):
        partes.append(
            ui.Aviso(
                [
                    ft.Text(
                        "Llevan más de dos días sin cambiar de estado. No aparecen como incidencia porque "
                        "nadie las reportó: están detenidos sin que el sistema lo sepa.",
                        size=d.T_SM,
                    ),
                    *[
                        ft.TextButton(
                            f"{e.get('destinatario') or e['envio_id']} — "
                            f"{texto_estado(e['estado']).lower()}, {fecha_relativa(e.get('actualizado_en'))}",
                            on_click=lambda _e, i=e["envio_id"]: app.ir(f"/envios/{i}"),
                        )
                        for e in atencion.get("detalle_estancados", [])[:5]
                    ],
                ],
                tono="alerta",
                titulo=f"{atencion['estancados']} envíos sin movimiento",
            )
        )

    derecha: list[ft.Control] = [
        ui.Tarjeta(
            SerieDiaria(datos.get("serie_diaria") or []),
            titulo=f"Movimiento de los últimos {datos['ventana']['dias']} días",
            ayuda="Creados frente a entregados, día a día.",
        )
    ]
    equipo = datos.get("equipo")
    if equipo:
        derecha.append(
            ui.Tarjeta(
                [
                    ft.Row(
                        [ui.Texto(g["grupo"].capitalize(), seleccionable=False), ui.Insignia(str(g["cantidad"]))],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                    for g in equipo.get("por_grupo", [])
                ],
                titulo="Equipo",
                ayuda=f"{equipo['activos']} de {equipo['usuarios']} cuentas activas.",
                acciones=[ui.Boton("Administrar", lambda: app.ir("/administracion"), variante="secundario")]
                if sesion.tiene_grupo("administrador")
                else None,
            )
        )

    partes.append(
        ui.DoblePanel(
            [
                ui.Tarjeta(
                    DesglosePorEstado(datos),
                    titulo="Dónde están los envíos",
                    ayuda="Todos los estados del catálogo, incluidos los que están en cero: un estado "
                    "vacío también es información.",
                )
            ],
            derecha,
        )
    )
    return ft.Column(partes, spacing=d.E4)


@ft.component
def DesglosePorEstado(tablero: dict) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    por_estado = tablero.get("por_estado") or []
    if tablero["totales"]["envios"] == 0:
        return ui.Vacio(
            "Sin envíos todavía",
            "Registre el primero para ver la distribución del proceso.",
            ui.Boton("Registrar envío", lambda: app.ir("/envios/nuevo")),
        )
    maximo = max([1, *(e["cantidad"] for e in por_estado)])
    filas = []
    for entrada in por_estado:
        color = d.color_de_estado(p, entrada["estado"])
        filas.append(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                spans=[
                                    ft.TextSpan(f"{entrada['codigo']} ", ft.TextStyle(color=p["texto-tenue"])),
                                    ft.TextSpan(entrada.get("etiqueta") or texto_estado(entrada["estado"])),
                                ],
                                size=d.T_SM,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(str(entrada["cantidad"]), size=d.T_SM, color=p["texto-suave"]),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ProgressBar(
                        value=entrada["cantidad"] / maximo,
                        color=color,
                        bgcolor=p["fondo-sutil"],
                        bar_height=8,
                        border_radius=999,
                    ),
                ],
                spacing=d.E1,
            )
        )
    return ft.Column(filas, spacing=d.E3)


@ft.component
def SerieDiaria(serie: list) -> ft.Control:
    """Barras dibujadas con contenedores: no hace falta una biblioteca de
    gráficos para dos series de treinta valores."""
    p = ui.paleta()
    if not serie:
        return ui.Vacio("Sin datos en el periodo")
    maximo = max([1, *(max(dia["creados"], dia["entregados"]) for dia in serie)])
    alto = 140

    def barra(valor: int, color: str, opacidad: float = 1.0) -> ft.Control:
        return ft.Container(
            height=max(2, alto * valor / maximo) if valor else 2,
            bgcolor=ft.Colors.with_opacity(opacidad, color) if valor else p["fondo-sutil"],
            expand=True,
            border_radius=ft.BorderRadius.only(top_left=2, top_right=2),
        )

    columnas = [
        ft.Container(
            ft.Row(
                [barra(dia["creados"], p["acento"], 0.55), barra(dia["entregados"], p["exito"])],
                spacing=1,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            expand=True,
            height=alto,
            alignment=ft.Alignment.BOTTOM_CENTER,
            tooltip=f"{dia['fecha']}: {dia['creados']} creados, {dia['entregados']} entregados",
        )
        for dia in serie
    ]
    return ft.Column(
        [
            ft.Row(columnas, spacing=2, vertical_alignment=ft.CrossAxisAlignment.END, height=alto),
            ft.Row(
                [
                    ft.Row([ft.Container(width=10, height=10, bgcolor=ft.Colors.with_opacity(0.55, p["acento"]), border_radius=2), ui.Texto("Creados", tamano=d.T_XS, seleccionable=False)], spacing=d.E1, tight=True),
                    ft.Row([ft.Container(width=10, height=10, bgcolor=p["exito"], border_radius=2), ui.Texto("Entregados", tamano=d.T_XS, seleccionable=False)], spacing=d.E1, tight=True),
                    ui.Texto(f"{serie[0]['fecha']} a {serie[-1]['fecha']}", tono="texto-tenue", tamano=d.T_XS),
                ],
                wrap=True,
                spacing=d.E4,
            ),
        ],
        spacing=d.E3,
    )


# --------------------------------------------------------------------------- #
# Auditor
# --------------------------------------------------------------------------- #


@ft.component
def PanelAuditor() -> ft.Control:
    app = use_app()
    bitacora = use_consulta(app.almacen, ("bitacora", "todos"), lambda: app.api.bitacora())
    envios = use_envios()
    verificacion, poner_verificacion = ft.use_state(None)
    verificar = use_mutacion(app.api.verificar_bitacora)

    async def ejecutar_verificacion():
        try:
            poner_verificacion(await verificar.ejecutar())
        except Exception:  # noqa: BLE001 - se muestra en la tarjeta
            pass

    registros = (bitacora.datos or {}).get("registros", [])
    rechazos = [r for r in registros if r.get("resultado") == "DENY"]

    def valor_o_esqueleto(valor):
        return ui.Esqueleto(alto=32, ancho=48) if bitacora.cargando else valor

    integridad = "sin verificar"
    nota = "Ejecute la verificación"
    color = None
    if verificacion:
        integridad = "íntegra" if verificacion["cadena_valida"] else "rota"
        nota = f"{verificacion['registros_verificados']} registros recalculados"
        color = "exito" if verificacion["cadena_valida"] else "peligro"

    if verificacion:
        ruptura = verificacion.get("punto_de_ruptura") or {}
        detalle_verificacion: list[ft.Control] = [
            ui.Aviso(
                f"{verificacion['registros_verificados']} registros recalculados, secuencias "
                f"{verificacion.get('primera_seq')} a {verificacion.get('ultima_seq')}."
                if verificacion["cadena_valida"]
                else f"Ruptura en la secuencia {ruptura.get('seq', ruptura.get('seq_esperada'))}: "
                f"{ruptura.get('descripcion', '')}",
                tono="exito" if verificacion["cadena_valida"] else "error",
                titulo="La cadena verifica" if verificacion["cadena_valida"] else "La cadena está rota",
            ),
            ft.TextButton("Ver la bitácora completa", on_click=lambda: app.ir("/bitacora")),
        ]
    else:
        detalle_verificacion = [
            ui.Texto(
                "La verificación no se ejecuta sola: es un procedimiento de auditoría y debe quedar "
                "constancia de quién lo ejecutó y cuándo. Al pulsar, la consulta también se registra.",
                tono="texto-suave",
            )
        ]
    if verificar.error:
        detalle_verificacion.insert(0, ui.Aviso(mensaje_de_error(verificar.error), tono="error"))

    lista_envios = (envios.datos or {}).get("envios", [])[:8]
    return ft.Column(
        [
            ui.Rejilla(
                [
                    ui.Metrica("Registros en bitácora", valor_o_esqueleto(len(registros)), "Cada operación deja un eslabón", "acento"),
                    ui.Metrica(
                        "Intentos rechazados",
                        valor_o_esqueleto(len(rechazos)),
                        "Operaciones denegadas y registradas",
                        "peligro" if rechazos else None,
                    ),
                    ui.Metrica("Integridad de la cadena", integridad, nota, color),
                ],
                {"xs": 12, "md": 4},
            ),
            ui.Tarjeta(
                detalle_verificacion,
                titulo="Verificación de integridad",
                ayuda="Recalcula la cadena de funciones hash completa y señala el punto exacto de ruptura, si lo hay.",
                acciones=[ui.Boton("Verificar ahora", ejecutar_verificacion, cargando=verificar.pendiente)],
            ),
            ui.Tarjeta(
                [FilaEnvioSimple(e) for e in lista_envios] if lista_envios else ui.Vacio("Sin envíos"),
                titulo="Envíos de la organización",
                ayuda="El auditor consulta el estado del sistema; no lo modifica.",
            ),
        ],
        spacing=d.E4,
    )


@ft.component
def FilaEnvioSimple(envio: dict) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(envio["destinatario"], size=d.T_SM, weight=ft.FontWeight.W_600, expand=True),
                        ui.EtiquetaEstado(envio["estado"], envio.get("codigo_estado")),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Text(envio.get("destino", ""), size=d.T_XS, color=p["texto-suave"]),
            ],
            spacing=2,
        ),
        padding=d.E3,
        border=ft.Border(left=ft.BorderSide(3, d.color_de_estado(p, envio["estado"])), bottom=ft.BorderSide(1, p["borde"])),
        on_click=lambda _e: app.ir(f"/envios/{envio['envio_id']}"),
        ink=True,
    )
