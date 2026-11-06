"""Consulta pública del avance de un envío.

Es el único punto del sistema que responde sin token, y por eso concentra dos
controles: el identificador aleatorio —un consecutivo se recorrería en minutos—
y la vista reducida, que devuelve el avance del envío y no la operación de la
empresa ni la identidad de sus empleados.

Esta pantalla no comparte el armazón del resto: quien llega aquí no tiene
cuenta, y mostrarle una navegación de operación solo lo confundiría.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta
from comun.formato import antiguedad, fecha_legible, fecha_relativa, texto_estado
from comun.http import ErrorApi
from comun.marca import LogotipoRastro
from rastro_app.consultas import REFRESCO_PUBLICO
from rastro_app.contexto import use_ancho, use_app
from rastro_app.estructura import SelectorTema
from rastro_app.mapa import Mapa, Marcador

FLUJO_PRINCIPAL = ("CREADO", "ASIGNADO", "RECOLECTADO", "EN_TRANSITO", "EN_REPARTO", "ENTREGADO")


@ft.component
def Rastreo() -> ft.Control:
    app = use_app()
    ancho = use_ancho()
    p = ui.paleta()
    # El enlace directo (/rastreo?envio=...) permite compartir el avance por
    # mensaje sin dictar el identificador, que es largo justamente por ser
    # aleatorio.
    inicial = (parse_qs(urlparse(app.pagina.route or "").query).get("envio") or [""])[0]
    entrada, poner_entrada = ft.use_state(inicial)
    entrada_ref = ft.use_ref(lambda: inicial)
    consultado, poner_consultado = ft.use_state(inicial or None)

    consulta = use_consulta(
        app.almacen,
        ("publico", consultado or ""),
        lambda: app.api.consulta_publica(consultado),
        habilitada=bool(consultado),
    )

    def escribir(valor: str):
        entrada_ref.current = valor
        poner_entrada(valor)

    def buscar():
        identificador = entrada_ref.current.strip()
        if identificador:
            poner_consultado(identificador)
            app.ir(f"/rastreo?envio={identificador}", reemplazar=True)

    datos = consulta.datos if consultado else None
    partes: list[ft.Control] = [
        ui.Encabezado("Consultar un envío", "Escriba el identificador de rastreo que le entregaron. No hace falta crear una cuenta."),
        ui.Tarjeta(
            [
                ui.Campo(
                    "Identificador de rastreo",
                    entrada,
                    escribir,
                    sugerencia="00000000-0000-4000-8000-000000000000",
                    ayuda="Son 36 caracteres con guiones. Puede pegarlo tal cual lo recibió.",
                    al_enviar=buscar,
                ),
                ft.Row([ui.Boton("Consultar", buscar, cargando=consulta.refrescando, grande=True, icono=ft.Icons.SEARCH)]),
            ]
        ),
    ]
    if consultado and consulta.error:
        partes.append(ErrorConsulta(consulta.error))
    elif consultado and consulta.cargando:
        partes.append(ui.Esqueleto(alto=256))
    elif datos:
        envio = datos["envio"]
        partes.append(
            ui.Tarjeta(
                ProgresoEnvio(envio["estado"]),
                titulo=envio.get("destinatario_nombre", ""),
                ayuda=f"Destino: {envio.get('destino_ciudad', '')}",
                acciones=[ui.EtiquetaEstado(envio["estado"], con_punto=True)],
            )
        )
        if envio["estado"] == "EN_REPARTO":
            partes.append(UbicacionEnVivo(envio["envio_id"]))
        partes.append(ui.Tarjeta([PasoPublico(e) for e in datos.get("eventos", [])], titulo="Avance"))
        partes.append(
            ui.Texto(
                f"Consultado el {fecha_legible(datos.get('consultado_en'))}. Se muestra el avance del envío; los "
                "datos de operación de la empresa y la identidad de sus empleados no forman parte de esta consulta.",
                tono="texto-tenue",
                tamano=d.T_XS,
            )
        )

    barra = ft.Container(
        content=ft.Row(
            [
                LogotipoRastro(24),
                ft.Text("Rastro", size=d.T_LG, weight=ft.FontWeight.W_800),
                ft.Text("consulta de envío", size=d.T_XS, color=p["texto-suave"], expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                SelectorTema(),
                ui.Boton("Acceso", lambda: app.ir("/acceso"), variante="secundario", ayuda="Acceso de operación"),
            ],
            spacing=d.E2,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E3, vertical=d.E1),
        bgcolor=p["superficie"],
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
    )
    return ft.SafeArea(
        ft.Column(
            [
                barra,
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    ft.Column(partes, spacing=d.E4),
                                    width=min(768, ancho - 2 * d.E4),
                                    padding=ft.Padding.symmetric(vertical=d.E5),
                                )
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
    )


@ft.component
def UbicacionEnVivo(envio_id: str) -> ft.Control:
    """Dónde va el vehículo que lleva el envío, mientras va en reparto.

    Solo la posición y su antigüedad: quién conduce y qué otras entregas lleva
    no son del destinatario. Si la última posición es vieja, no se muestra nada
    que parezca en vivo: un punto quieto de hace una hora le diría que el
    paquete está parado allí."""
    app = use_app()
    ancho = use_ancho()
    ubicacion = use_consulta(
        app.almacen,
        ("publico-ubicacion", envio_id),
        lambda: app.api.ubicacion_publica(envio_id),
        intervalo=REFRESCO_PUBLICO,
    )
    datos = ubicacion.datos

    # Si dice que ya no va en reparto, se entregó o se detuvo mientras la
    # pantalla estaba abierta: se relee el histórico para mostrarlo.
    def releer():
        if datos and datos.get("motivo") == "no_en_reparto":
            app.almacen.invalidar("publico")

    ft.use_effect(releer, [datos.get("motivo") if datos else None])

    if not datos:
        return ft.Container()
    if not datos.get("disponible"):
        return ui.Texto(
            "El vehículo no ha reportado su posición en los últimos minutos. Volverá a aparecer aquí en cuanto lo haga."
            if datos.get("motivo") == "sin_senal"
            else "La ubicación en vivo aparece cuando el mensajero sale a ruta con su envío.",
            tono="texto-suave",
        )
    posicion = datos["posicion"]
    return ui.Tarjeta(
        [
            Mapa(
                (Marcador("vehiculo", posicion["lat"], posicion["lon"], precision=posicion.get("precision_m")),),
                seguir="vehiculo",
                teselas=app.configuracion.get("teselas"),
                ancho=min(768, ancho - 2 * d.E4) - 2 * d.E4,
            ),
            ui.Texto(
                "Se muestra solo mientras su envío está en reparto. No incluye quién lo lleva ni sus otras entregas.",
                tono="texto-tenue",
                tamano=d.T_XS,
            ),
        ],
        titulo="Su envío va en camino",
        ayuda=f"Posición del vehículo {antiguedad(datos.get('edad_segundos'))}. Se actualiza sola.",
    )


@ft.component
def ErrorConsulta(error: BaseException) -> ft.Control:
    if isinstance(error, ErrorApi) and error.estado == 422:
        return ui.Aviso(
            "Debe ser un identificador de 36 caracteres con guiones. Revise que esté completo y que no se haya "
            "cortado al copiarlo.",
            tono="alerta",
            titulo="El identificador no tiene el formato esperado",
        )
    if isinstance(error, ErrorApi) and error.estado == 404:
        return ui.Aviso(
            "Compruebe que lo copió completo. Si acaba de recibirlo, espere unos minutos: el envío puede no "
            "estar registrado todavía.",
            tono="alerta",
            titulo="No encontramos un envío con ese identificador",
        )
    return ui.Aviso(str(error) or "Inténtelo de nuevo en unos momentos.", tono="error", titulo="No fue posible consultar el envío")


@ft.component
def ProgresoEnvio(estado_actual: str) -> ft.Control:
    """Progreso sobre el flujo principal. La incidencia no aparece como un paso
    más porque no lo es: es una desviación, y ponerla en la misma línea daría a
    entender que el envío avanzó cuando se detuvo."""
    p = ui.paleta()
    if estado_actual == "INCIDENCIA":
        return ui.Aviso("Se reportó una incidencia. La empresa debe autorizar la reanudación.", tono="alerta", titulo="El envío está detenido")
    indice = FLUJO_PRINCIPAL.index(estado_actual) if estado_actual in FLUJO_PRINCIPAL else -1
    pasos = []
    for posicion, estado in enumerate(FLUJO_PRINCIPAL):
        alcanzado = posicion <= indice
        pasos.append(
            ft.Column(
                [
                    ft.Container(height=6, border_radius=3, bgcolor=d.color_de_estado(p, estado) if alcanzado else p["fondo-sutil"]),
                    ft.Text(
                        texto_estado(estado),
                        size=d.T_XS,
                        color=p["texto"] if alcanzado else p["texto-tenue"],
                        weight=ft.FontWeight.W_700 if posicion == indice else None,
                    ),
                ],
                spacing=d.E1,
                col={"xs": 4, "sm": 2},
            )
        )
    return ft.ResponsiveRow(pasos, breakpoints=d.PUNTOS_DE_CORTE, spacing=d.E1, run_spacing=d.E2)


@ft.component
def PasoPublico(evento: dict) -> ft.Control:
    p = ui.paleta()
    color = d.color_de_estado(p, evento["estado"])
    lineas: list[ft.Control] = [
        ft.Text(texto_estado(evento["estado"]), size=d.T_SM, weight=ft.FontWeight.W_700, color=color),
        ui.Texto(f"{fecha_legible(evento.get('ts'))} · {fecha_relativa(evento.get('ts'))}", tono="texto-suave", tamano=d.T_XS),
    ]
    if evento.get("nota"):
        lineas.append(ft.Text(evento["nota"], size=d.T_SM))
    if evento.get("tiene_evidencia"):
        lineas.append(ui.Texto("Con evidencia de entrega registrada", tono="texto-suave", tamano=d.T_XS))
    return ft.Container(
        ft.Column(lineas, spacing=2),
        padding=ft.Padding.only(left=d.E3, bottom=d.E2),
        border=ft.Border(left=ft.BorderSide(3, color)),
    )
