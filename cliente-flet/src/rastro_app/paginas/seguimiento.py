"""Seguimiento: dónde van los conductores en ruta, en vivo.

El mapa se refresca cada diez segundos con la última posición de cada ruta
abierta. Elegir una ruta dibuja su recorrido y lista sus paradas con el estado
de cada una. No hay botones que cambien nada: esta pantalla mira; lo que se hace
con un envío se hace en su detalle.

Ver dónde está una persona es leer un dato personal suyo. El servidor deja
constancia de cada apertura en la bitácora —una por pantalla cada pocos minutos,
gracias al testigo, no una por refresco— y la pantalla lo dice.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta
from comun.formato import antiguedad, fecha_legible, fecha_relativa
from rastro_app.consultas import REFRESCO_SEGUIMIENTO, use_estados_finales
from rastro_app.contexto import mensaje_de_error, use_ancho, use_app
from rastro_app.estructura import ancho_contenido
from rastro_app.mapa import Mapa, Marcador, Trazo

SENAL = {
    "en_linea": ("En línea", "exito"),
    "atrasada": ("Señal atrasada", "alerta"),
    "sin_senal": ("Sin señal", "tenue"),
    "sin_datos": ("Esperando la primera posición", "tenue"),
    "cerrada": ("Finalizada", "tenue"),
}


def _primer_nombre(nombre: str) -> str:
    return (nombre or "").strip().split(" ")[0]


def use_testigo():
    """El testigo de la última consulta registrada en la bitácora. Vive lo que
    vive la pantalla: abrirla de nuevo es otra consulta, y se registra."""
    return ft.use_ref(lambda: None)


@ft.component
def Seguimiento() -> ft.Control:
    app = use_app()
    ancho = use_ancho()
    vista, poner_vista = ft.use_state("activas")
    seleccionada, poner_seleccionada = ft.use_state(None)
    testigo_lista = use_testigo()
    testigo_ruta = use_testigo()

    async def pedir_rutas():
        datos = await app.api.rutas(vista, testigo_lista.current)
        testigo_lista.current = datos.get("testigo")
        return datos

    rutas = use_consulta(
        app.almacen,
        ("rutas", "lista", vista),
        pedir_rutas,
        # Solo las activas se mueven: refrescar las finalizadas cada diez
        # segundos sería pagar invocaciones por nada.
        intervalo=REFRESCO_SEGUIMIENTO if vista == "activas" else None,
    )

    async def pedir_recorrido():
        """La primera consulta trae el recorrido entero; las siguientes, solo
        lo posterior a la última posición conocida."""
        previo = app.almacen.leer(("rutas", "recorrido", seleccionada))
        desde = previo["posiciones"][-1]["capturada_en"] if previo and previo.get("posiciones") else None
        datos = await app.api.ruta(seleccionada, desde=desde, testigo=testigo_ruta.current)
        testigo_ruta.current = datos.get("testigo")
        return {**datos, "desde": desde}

    def combinar(previo, nuevo):
        if nuevo.get("desde") and previo:
            return {"ruta": nuevo["ruta"], "posiciones": previo["posiciones"] + nuevo["posiciones"]}
        return {"ruta": nuevo["ruta"], "posiciones": nuevo["posiciones"]}

    recorrido = use_consulta(
        app.almacen,
        ("rutas", "recorrido", seleccionada or ""),
        pedir_recorrido,
        habilitada=bool(seleccionada),
        intervalo=REFRESCO_SEGUIMIENTO if vista == "activas" else None,
        transformar=combinar,
    )

    lista = (rutas.datos or {}).get("rutas", [])
    elegida = next((r for r in lista if r["ruta_id"] == seleccionada), None) or (
        (recorrido.datos or {}).get("ruta") if seleccionada else None
    )
    marcadores = tuple(
        Marcador(
            id=r["ruta_id"],
            lat=r["ultima_posicion"]["lat"],
            lon=r["ultima_posicion"]["lon"],
            etiqueta=_primer_nombre(r.get("conductor_nombre", "")),
            tono=SENAL.get(r["senal"]["estado"], ("", "tenue"))[1],
            seleccionado=r["ruta_id"] == seleccionada,
            precision=r["ultima_posicion"].get("precision_m") if r["ruta_id"] == seleccionada else None,
        )
        for r in lista
        if r.get("ultima_posicion")
    )
    posiciones = (recorrido.datos or {}).get("posiciones", []) if seleccionada else []
    trazos = (Trazo(seleccionada, tuple((p["lat"], p["lon"]) for p in posiciones)),) if seleccionada and len(posiciones) > 1 else ()

    def cambiar_vista(nueva: str):
        poner_vista(nueva)
        poner_seleccionada(None)

    if rutas.cargando:
        mapa: ft.Control = ui.Esqueleto(alto=360)
    elif not marcadores and not trazos:
        mapa = ui.Tarjeta(
            ui.Vacio(
                "No hay conductores en ruta" if vista == "activas" else "Sin posiciones para mostrar",
                "Cuando un conductor sale a ruta desde Entregas, aparece aquí con su posición."
                if vista == "activas"
                else "Las rutas finalizadas conservan su recorrido treinta días.",
            )
        )
    else:
        mapa = Mapa(
            marcadores,
            trazos,
            encuadre=seleccionada or f"todas-{vista}",
            teselas=app.configuracion.get("teselas"),
            alto=480 if ancho >= d.PUNTOS_DE_CORTE["lg"] else 340,
            ancho=ancho_contenido(ancho) * (7 / 12 if ancho >= d.PUNTOS_DE_CORTE["lg"] else 1),
            al_seleccionar=poner_seleccionada,
        )

    panel: list[ft.Control] = [
        ui.GrupoSegmentado(vista, [("activas", "En curso"), ("finalizadas", "Finalizadas")], cambiar_vista, etiqueta="Rutas")
    ]
    if elegida:
        panel.append(
            DetalleRuta(
                elegida,
                cargando=recorrido.cargando,
                posiciones=len(posiciones),
                al_volver=lambda: poner_seleccionada(None),
            )
        )
    elif rutas.cargando:
        panel.append(ui.ListaEsqueleto(3))
    elif not lista:
        panel.append(
            ui.Tarjeta(
                ui.Vacio(
                    "Ninguna ruta en curso" if vista == "activas" else "Ninguna ruta finalizada",
                    "Las rutas aparecen en cuanto un conductor sale con sus guías."
                    if vista == "activas"
                    else "Aquí quedan las rutas cerradas, con su recorrido y el estado de cada parada.",
                )
            )
        )
    else:
        panel += [TarjetaRuta(r, lambda r=r: poner_seleccionada(r["ruta_id"]), key=r["ruta_id"]) for r in lista]

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Seguimiento",
            "Conductores en ruta y su última posición. El mapa se actualiza solo cada diez segundos.",
            [ui.Boton("Actualizar", rutas.recargar, variante="secundario", cargando=rutas.refrescando, icono=ft.Icons.REFRESH)],
        ),
        ui.Texto(
            "La ubicación de una persona es un dato personal: la apertura de esta pantalla queda en la bitácora "
            "con su nombre.",
            tono="texto-tenue",
            tamano=d.T_XS,
        ),
    ]
    if rutas.error:
        partes.append(ui.Aviso(mensaje_de_error(rutas.error), tono="error"))
    partes.append(
        ft.ResponsiveRow(
            [
                ft.Container(mapa, col={"xs": 12, "lg": 7}),
                ft.Column(panel, spacing=d.E3, col={"xs": 12, "lg": 5}),
            ],
            breakpoints=d.PUNTOS_DE_CORTE,
            spacing=d.E4,
            run_spacing=d.E4,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )
    return ft.Column(partes, spacing=d.E4)


@ft.component
def Senal(ruta: dict) -> ft.Control:
    p = ui.paleta()
    estado = ruta["senal"]["estado"]
    texto, tono = SENAL.get(estado, (estado, "tenue"))
    color = {"exito": p["exito"], "alerta": p["alerta"]}.get(tono, p["texto-tenue"])
    edad = ruta["senal"].get("edad_segundos")
    if edad is not None and estado != "cerrada":
        texto += f" · {antiguedad(edad)}"
    return ft.Row(
        [ft.Container(width=8, height=8, border_radius=4, bgcolor=color), ft.Text(texto, size=d.T_XS, color=color, weight=ft.FontWeight.W_600)],
        spacing=d.E1,
        tight=True,
    )


@ft.component
def Avance(ruta: dict) -> ft.Control:
    p = ui.paleta()
    resumen = ruta["resumen"]
    total = resumen["total"] or 0
    texto = (
        f"{resumen['entregadas']} entregada{'' if resumen['entregadas'] == 1 else 's'} · "
        f"{resumen['pendientes']} pendiente{'' if resumen['pendientes'] == 1 else 's'}"
        + (f" · {resumen['incidencias']} con novedad" if resumen.get("incidencias") else "")
        + f" · {total} en total"
    )
    return ft.Column(
        [
            ft.ProgressBar(value=(resumen["cerradas"] / total) if total else 0, color=p["exito"], bgcolor=p["fondo-sutil"], bar_height=6, border_radius=3),
            ft.Text(texto, size=d.T_XS, color=p["texto-suave"]),
        ],
        spacing=d.E1,
    )


@ft.component
def TarjetaRuta(ruta: dict, al_elegir) -> ft.Control:
    p = ui.paleta()
    momento = (
        f"Salió {fecha_relativa(ruta['iniciada_en'])}"
        if ruta["estado"] == "ACTIVA"
        else f"Finalizó {fecha_relativa(ruta.get('finalizada_en') or ruta.get('actualizada_en'))}"
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [ft.Text(ruta.get("conductor_nombre", ""), size=d.T_MD, weight=ft.FontWeight.W_600, expand=True), Senal(ruta)],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                Avance(ruta),
                ui.Texto(momento, tono="texto-tenue", tamano=d.T_XS),
            ],
            spacing=d.E2,
        ),
        padding=d.E3,
        bgcolor=p["superficie"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_MD,
        on_click=lambda _e: al_elegir(),
        ink=True,
    )


@ft.component
def DetalleRuta(ruta: dict, cargando: bool, posiciones: int, al_volver) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    es_final = use_estados_finales()
    paradas = sorted(ruta.get("paradas", []), key=lambda parada: (es_final(parada["estado"]), parada["orden"]))
    if ruta["estado"] == "ACTIVA":
        ayuda = f"Salió el {fecha_legible(ruta['iniciada_en'])}"
    else:
        ayuda = (
            f"Del {fecha_legible(ruta['iniciada_en'])} al {fecha_legible(ruta.get('finalizada_en') or ruta.get('actualizada_en'))}"
            + (" · terminada con paradas abiertas" if ruta.get("cierre") == "manual" else "")
        )
    nota = "Cargando el recorrido…" if cargando else f"{posiciones} posiciones en el recorrido dibujado."
    if (ruta.get("ultima_posicion") or {}).get("hora_de") == "servidor":
        nota += " La última hora es la de recepción: la del teléfono no era creíble."

    filas = [
        ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(f"{parada['orden']}  {parada['destinatario']}", size=d.T_SM, weight=ft.FontWeight.W_600, expand=True),
                            ui.EtiquetaEstado(parada["estado"], parada.get("codigo_estado")),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ui.Texto(parada.get("direccion", "") + (f" · {parada['ciudad']}" if parada.get("ciudad") else ""), tono="texto-suave", tamano=d.T_XS),
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(vertical=d.E2, horizontal=d.E2),
            border=ft.Border(left=ft.BorderSide(3, d.color_de_estado(p, parada["estado"]))),
            on_click=lambda _e, i=parada["envio_id"]: app.ir(f"/envios/{i}"),
            ink=True,
        )
        for parada in paradas
    ]
    return ui.Tarjeta(
        [Senal(ruta), Avance(ruta), ui.Texto(nota, tono="texto-tenue", tamano=d.T_XS), *filas],
        titulo=ruta.get("conductor_nombre", ""),
        ayuda=ayuda,
        acciones=[ui.Boton("Ver todas", al_volver, variante="sutil")],
    )
