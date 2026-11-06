"""Entregas: el conductor elige sus guías, sale a ruta y entrega.

Son dos pantallas en una dirección. Sin ruta abierta, la selección: las guías
que el conductor tiene en su poder, para marcar las que lleva en el vehículo.
Con ruta abierta, el modo ruta: su posición, las paradas pendientes y las dos
acciones de la calle —entregar y reportar una novedad—. Cuál se ve lo dice el
servidor (`/rutas/activa`), no un estado guardado en el teléfono: si la
aplicación se cierra a mitad del recorrido, al volver aparece la ruta tal como
quedó.

Mientras la ruta está abierta, el teléfono comparte su ubicación con la empresa
y con los destinatarios de los envíos en reparto. La pantalla lo dice antes de
salir y mientras dura: compartir la ubicación de una persona es algo que esa
persona tiene que saber que está pasando.
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import quote

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_formulario, use_mutacion
from comun.formato import antiguedad, fecha_legible, fecha_relativa
from rastro_app.consultas import REFRESCO_RUTA_PROPIA, TRAS_ESCRIBIR, use_envios, use_estados_finales
from rastro_app.contexto import BarraFija, mensaje_de_error, use_ancho, use_app, use_sesion
from rastro_app.estructura import ancho_contenido
from rastro_app.evidencia import PasosCarga, VistaPrevia, cargar, elegir_foto
from rastro_app.mapa import Mapa, Marcador, Trazo
from rastro_app.ubicacion import Transmisor, mensaje_fallo


@ft.component
def Entregas() -> ft.Control:
    app = use_app()
    testigo = ft.use_ref(lambda: None)

    async def pedir():
        datos = await app.api.ruta_activa(testigo.current)
        testigo.current = datos.get("testigo")
        return datos

    activa = use_consulta(app.almacen, ("rutas", "activa"), pedir, intervalo=REFRESCO_RUTA_PROPIA)

    if activa.cargando:
        return ft.Column([ui.Esqueleto(alto=80), ui.ListaEsqueleto(4)], spacing=d.E4)
    if activa.error and not activa.datos:
        return ui.Tarjeta(
            ui.Vacio(
                "No se pudo saber si tiene una ruta abierta",
                mensaje_de_error(activa.error),
                ui.Boton("Reintentar", activa.recargar, variante="secundario"),
            )
        )
    ruta = activa.datos.get("ruta")
    if ruta:
        return ModoRuta(ruta, key=ruta["ruta_id"])
    return SeleccionDeGuias(tuple(activa.datos.get("estados_aptos") or ()))


# =========================================================================== #
# Selección de guías
# =========================================================================== #


@ft.component
def SeleccionDeGuias(aptos: tuple) -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    envios = use_envios()
    seleccion, poner_seleccion = ft.use_state(frozenset())
    busqueda, poner_busqueda = ft.use_state("")
    fallo, poner_fallo = ft.use_state(None)
    localizando, poner_localizando = ft.use_state(False)

    # Una ruta solo lleva envíos de quien la conduce, lo diga o no el listado:
    # a quien ve toda la operación el servidor le devuelve los de todos.
    propios = [e for e in (envios.datos or {}).get("envios", []) if e.get("conductor_sub") == sesion.usuario.get("sub")]
    termino = busqueda.strip().lower()

    def coincide(envio: dict) -> bool:
        if not termino:
            return True
        texto = " ".join(str(envio.get(c) or "") for c in ("destinatario", "destino", "ciudad_destino", "envio_id", "orden_compra"))
        return termino in texto.lower()

    para_entregar = [e for e in propios if e["estado"] in aptos]
    por_recoger = [e for e in propios if e["estado"] == "ASIGNADO"]
    detenidos = [e for e in propios if e["estado"] == "INCIDENCIA"]
    visibles = [e for e in para_entregar if coincide(e)]
    todos_marcados = bool(visibles) and all(e["envio_id"] in seleccion for e in visibles)
    # Lo seleccionado que sigue siendo apto: si una guía cambió de estado por
    # otro lado, no debe colarse en la ruta desde una selección vieja.
    elegidos = tuple(e["envio_id"] for e in para_entregar if e["envio_id"] in seleccion)

    async def iniciar_ruta(identificadores, ubicacion):
        resultado = await app.api.iniciar_ruta(list(identificadores), ubicacion)
        app.almacen.invalidar(*TRAS_ESCRIBIR)
        return resultado

    iniciar = use_mutacion(iniciar_ruta)

    async def salir():
        poner_fallo(None)
        poner_localizando(True)
        lectura, motivo = await app.gps.leer(espera=15)
        poner_localizando(False)
        # Sin permiso no se sale: es lo único que el modo ruta no puede suplir.
        # Sin señal sí: la posición llega en cuanto el teléfono la consiga.
        if motivo and motivo != "sin_gps":
            poner_fallo(motivo)
            return
        try:
            resultado = await iniciar.ejecutar(elegidos, lectura)
            total = resultado["ruta"]["resumen"]["total"]
            app.avisar(f"Ruta iniciada con {total} guía{'' if total == 1 else 's'}. Su ubicación se está compartiendo.", "exito")
            poner_seleccion(frozenset())
        except Exception:  # noqa: BLE001 - se muestra junto al botón
            pass

    def mostrar_barra():
        if not elegidos:
            app.poner_barra(None)
            return
        app.poner_barra(
            BarraFija(
                f"{len(elegidos)} guía{'' if len(elegidos) == 1 else 's'} para esta ruta",
                (
                    ("Buscando su ubicación…" if localizando else "Salir a ruta", salir, "primario"),
                    ("Quitar", lambda: poner_seleccion(frozenset()), "secundario"),
                ),
            )
        )

    ft.use_effect(mostrar_barra, [elegidos, localizando], cleanup=lambda: app.poner_barra(None))

    def alternar(envio_id: str):
        poner_seleccion(lambda previa: previa - {envio_id} if envio_id in previa else previa | {envio_id})

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Entregas",
            "Marque las guías que lleva en el vehículo y salga a ruta. Mientras la ruta esté abierta, la empresa "
            "ve dónde va y cada destinatario ve acercarse su paquete.",
        ),
        ui.Aviso(
            "Su posición, solo mientras la ruta esté abierta. La empresa la ve en el mapa de seguimiento; el "
            "destinatario de cada envío en reparto ve la del vehículo, sin su nombre ni sus otras entregas. Al "
            "terminar la ruta, deja de compartirse.",
            tono="info",
            titulo="Qué se comparte y con quién",
        ),
    ]
    if envios.error:
        partes.append(ui.Aviso(mensaje_de_error(envios.error), tono="error"))

    if envios.cargando:
        partes.append(ui.ListaEsqueleto(4))
    elif not para_entregar and not por_recoger:
        partes.append(
            ui.Tarjeta(
                ui.Vacio(
                    "No tiene guías para entregar",
                    "Cuando le asignen envíos y los recoja, aparecerán aquí para salir a ruta.",
                    ui.Boton("Actualizar", envios.recargar, variante="secundario", cargando=envios.refrescando),
                )
            )
        )
    else:
        if detenidos:
            partes.append(
                ui.Aviso(
                    "No pueden salir a ruta hasta que la empresa autorice continuar.",
                    tono="alerta",
                    titulo=f"{len(detenidos)} detenido{'' if len(detenidos) == 1 else 's'} por incidencia",
                )
            )
        contenido: list[ft.Control] = []
        if len(para_entregar) > 4:
            contenido.append(ui.Campo("Buscar", busqueda, poner_busqueda, sugerencia="Destinatario, dirección o guía"))
        if not para_entregar:
            contenido.append(ui.Vacio("Aún no tiene guías en su poder", "Marque como recogidas las de abajo cuando las tenga en el vehículo."))
        elif not visibles:
            contenido.append(ui.Vacio("Ninguna guía coincide", "Pruebe con otro término."))
        else:
            contenido += [
                FilaGuia(e, e["envio_id"] in seleccion, alternar, key=e["envio_id"]) for e in visibles
            ]
        partes.append(
            ui.Tarjeta(
                contenido,
                titulo=f"Para entregar ({len(para_entregar)})",
                ayuda="Las que ya tiene en su poder: recolectadas, en tránsito o en reparto.",
                acciones=[
                    ui.Boton(
                        "Quitar todas" if todos_marcados else "Marcar todas",
                        lambda: poner_seleccion(frozenset() if todos_marcados else frozenset(e["envio_id"] for e in visibles)),
                        variante="sutil",
                    )
                ]
                if visibles
                else None,
            )
        )
        if por_recoger:
            partes.append(
                ui.Tarjeta(
                    [FilaPorRecoger(e, key=e["envio_id"]) for e in por_recoger],
                    titulo=f"Por recoger ({len(por_recoger)})",
                    ayuda="Asignadas a usted pero todavía no en su poder. Márquelas al tenerlas en el vehículo.",
                )
            )

    if fallo:
        titulo, texto = mensaje_fallo(fallo, app.pagina.web)
        partes.append(ui.Aviso(texto, tono="alerta" if fallo == "sin_gps" else "error", titulo=titulo))
    if iniciar.error:
        partes.append(ui.Aviso(mensaje_de_error(iniciar.error), tono="error", titulo="No se inició la ruta"))
    return ft.Column(partes, spacing=d.E4)


@ft.component
def FilaGuia(envio: dict, marcada: bool, al_alternar) -> ft.Control:
    p = ui.paleta()
    return ft.Container(
        content=ft.Row(
            [
                ft.Checkbox(value=marcada, on_change=lambda _e: al_alternar(envio["envio_id"])),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(envio["destinatario"], size=d.T_MD, weight=ft.FontWeight.W_600, expand=True),
                                ui.EtiquetaEstado(envio["estado"], envio.get("codigo_estado")),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        ui.Texto(envio.get("destino", "") + (f" · {envio['ciudad_destino']}" if envio.get("ciudad_destino") else ""), tono="texto-suave"),
                        ui.Texto(envio["envio_id"], tono="texto-tenue", tamano=d.T_XS, mono=True),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=ft.Padding.symmetric(vertical=d.E2),
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
        on_click=lambda _e: al_alternar(envio["envio_id"]),
    )


@ft.component
def FilaPorRecoger(envio: dict) -> ft.Control:
    app = use_app()
    p = ui.paleta()

    async def operacion():
        lectura, _motivo = await app.gps.leer(espera=8)
        datos = {"estado": "RECOLECTADO"}
        if lectura:
            datos["ubicacion"] = {"lat": lectura["lat"], "lon": lectura["lon"]}
        await app.api.registrar_evento(envio["envio_id"], datos)
        app.almacen.invalidar(*TRAS_ESCRIBIR)

    registrar = use_mutacion(operacion)

    async def recoger():
        try:
            await registrar.ejecutar()
            app.avisar(f"Recogido: {envio['destinatario']}.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")

    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(envio["destinatario"], size=d.T_MD, weight=ft.FontWeight.W_600),
                        ui.Texto(envio.get("destino", "") + (f" · {envio['ciudad_destino']}" if envio.get("ciudad_destino") else ""), tono="texto-suave"),
                        ui.Texto(envio["envio_id"], tono="texto-tenue", tamano=d.T_XS, mono=True),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ui.Boton("Recogido", recoger, variante="secundario", cargando=registrar.pendiente),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=ft.Padding.symmetric(vertical=d.E2),
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
    )


# =========================================================================== #
# Modo ruta
# =========================================================================== #

TEXTO_TRANSMISION = {
    "preparando": "Buscando señal GPS…",
    "transmitiendo": "Compartiendo su ubicación",
    "sin_permiso": "Ubicación bloqueada: permítala en los ajustes del teléfono para Rastro",
    "sin_gps": "Sin señal GPS. Se reintenta sola",
    "no_compatible": "Este equipo no entrega la ubicación",
    "detenida": "La ruta terminó: ya no se comparte su ubicación",
}


def use_transmision(ruta_id: str, al_terminar) -> dict:
    """La transmisión de la ubicación mientras la pantalla del modo ruta esté
    montada. Al desmontarse se cancela y deja de escuchar el GPS."""
    app = use_app()
    estado, poner_estado = ft.use_state(
        lambda: {"estado": "preparando", "posicion": None, "recorrido": [], "ultimo_envio": None, "pendientes": 0, "sin_conexion": False}
    )

    async def correr():
        transmisor = Transmisor(app.pagina, app.api, app.gps, ruta_id, poner_estado, al_terminar)
        await transmisor.correr()

    ft.use_effect(correr, [ruta_id], cleanup=lambda: None)
    return estado


def use_pantalla_encendida() -> str:
    """En Android la transmisión sigue con la pantalla apagada gracias al
    servicio en primer plano; en el navegador y en escritorio no, así que allí
    se pide mantener la pantalla encendida mientras la ruta esté abierta."""
    app = use_app()
    estado, poner_estado = ft.use_state("inactiva")
    android = app.pagina.platform == ft.PagePlatform.ANDROID and not app.pagina.web
    candado = ft.use_ref(lambda: None)

    async def pedir():
        if android:
            poner_estado("segundo_plano")
            return
        try:
            candado.current = ft.Wakelock()
            await candado.current.enable()
            poner_estado("encendida")
        except Exception:  # noqa: BLE001 - el navegador puede negarlo
            poner_estado("rechazada")

    async def soltar():
        if candado.current is not None:
            try:
                await candado.current.disable()
            except Exception:  # noqa: BLE001 - la página puede estar cerrándose
                pass

    ft.use_effect(pedir, [], cleanup=soltar)
    return estado


@ft.component
def ModoRuta(ruta: dict) -> ft.Control:
    app = use_app()
    ancho = use_ancho()
    es_final = use_estados_finales()
    confirmar_cierre, poner_confirmar_cierre = ft.use_state(False)
    entregando, poner_entregando = ft.use_state(None)
    reportando, poner_reportando = ft.use_state(None)

    transmision = use_transmision(ruta["ruta_id"], lambda: app.almacen.invalidar("rutas"))
    pantalla = use_pantalla_encendida()

    async def finalizar_ruta():
        await app.api.finalizar_ruta(ruta["ruta_id"])
        app.almacen.invalidar(*TRAS_ESCRIBIR)

    finalizar = use_mutacion(finalizar_ruta)

    async def terminar():
        try:
            await finalizar.ejecutar()
            poner_confirmar_cierre(False)
            app.avisar("Ruta terminada. Su ubicación dejó de compartirse.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")

    abiertas = [parada for parada in ruta.get("paradas", []) if not es_final(parada["estado"])]
    cerradas = [parada for parada in ruta.get("paradas", []) if es_final(parada["estado"])]
    resumen = ruta["resumen"]
    posicion = transmision["posicion"]
    ubicacion_actual = {"lat": posicion["lat"], "lon": posicion["lon"]} if posicion else None

    async def pedir_terminar():
        if abiertas:
            poner_confirmar_cierre(True)
        else:
            await terminar()

    if pantalla in ("rechazada",):
        nota_pantalla = "Mantenga la pantalla encendida: con la pantalla apagada, el equipo deja de enviar su ubicación."
    elif pantalla == "encendida":
        nota_pantalla = "La pantalla se mantiene encendida mientras la ruta está abierta."
    elif pantalla == "segundo_plano":
        nota_pantalla = "La ubicación se sigue compartiendo con la pantalla apagada; la notificación de Rastro lo indica."
    else:
        nota_pantalla = ""

    mapa = Mapa(
        (Marcador("yo", posicion["lat"], posicion["lon"], precision=posicion.get("precision_m")),) if posicion else (),
        (Trazo("recorrido", tuple(transmision["recorrido"])),) if len(transmision["recorrido"]) > 1 else (),
        seguir="yo",
        teselas=app.configuracion.get("teselas"),
        alto=300,
        ancho=ancho_contenido(ancho) * (0.5 if ancho >= d.PUNTOS_DE_CORTE["lg"] else 1),
    )

    paradas: list[ft.Control] = []
    if not abiertas:
        paradas.append(
            ui.Aviso(
                "Termine la ruta para dejar de compartir su ubicación.",
                tono="exito",
                titulo="Todas las paradas están cerradas",
                acciones=[ui.Boton("Terminar ruta", terminar, cargando=finalizar.pendiente)],
            )
        )
    else:
        paradas.append(ui.Texto(f"{len(abiertas)} parada{'' if len(abiertas) == 1 else 's'} pendiente{'' if len(abiertas) == 1 else 's'}", tono="texto-suave"))
    paradas += [
        TarjetaParada(parada, lambda parada=parada: poner_entregando(parada), lambda parada=parada: poner_reportando(parada), key=parada["envio_id"])
        for parada in abiertas
    ]
    if cerradas:
        paradas.append(
            ft.ExpansionTile(
                title=ft.Text(f"Cerradas ({len(cerradas)})", size=d.T_SM, weight=ft.FontWeight.W_600),
                controls=[TarjetaParada(parada, None, None, key=parada["envio_id"]) for parada in cerradas],
            )
        )

    ModalEntrega(entregando, ubicacion_actual, lambda: poner_entregando(None))
    ModalNovedad(reportando, ubicacion_actual, lambda: poner_reportando(None))
    ui.use_confirmacion(
        confirmar_cierre,
        "¿Terminar la ruta?",
        f"Paradas sin cerrar: {len(abiertas)}. Conservan su estado, y las que sigan en reparto podrá llevarlas en "
        "otra ruta. La empresa y los destinatarios dejarán de ver su ubicación.",
        "Terminar ruta",
        terminar,
        lambda: poner_confirmar_cierre(False),
        cargando=finalizar.pendiente,
    )

    return ft.Column(
        [
            ui.Encabezado(
                "Ruta en curso",
                f"Salió {fecha_relativa(ruta['iniciada_en'])} · paradas cerradas: {resumen['cerradas']} de {resumen['total']}",
                [ui.Boton("Terminar ruta", pedir_terminar, variante="secundario", cargando=finalizar.pendiente)],
            ),
            ft.ProgressBar(value=(resumen["cerradas"] / resumen["total"]) if resumen["total"] else 0, bar_height=6, border_radius=3),
            ft.ResponsiveRow(
                [
                    ft.Column(
                        [EstadoDeTransmision(transmision), mapa, *([ui.Texto(nota_pantalla, tono="texto-tenue", tamano=d.T_XS)] if nota_pantalla else [])],
                        spacing=d.E3,
                        col={"xs": 12, "lg": 6},
                    ),
                    ft.Column(paradas, spacing=d.E3, col={"xs": 12, "lg": 6}),
                ],
                breakpoints=d.PUNTOS_DE_CORTE,
                spacing=d.E4,
                run_spacing=d.E4,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ],
        spacing=d.E4,
    )


@ft.component
def EstadoDeTransmision(transmision: dict) -> ft.Control:
    p = ui.paleta()
    web = use_app().pagina.web
    # Los textos que envejecen solos («enviada hace 8 s») se renuevan cada
    # cinco segundos sin esperar a la siguiente lectura.
    _tic, poner_tic = ft.use_state(0)

    async def reloj():
        while True:
            await asyncio.sleep(5)
            poner_tic(lambda t: t + 1)

    ft.use_effect(reloj, [], cleanup=lambda: None)

    estado = transmision["estado"]
    if estado == "transmitiendo" and not transmision["sin_conexion"]:
        tono = "exito"
    elif estado in ("sin_permiso", "no_compatible"):
        tono = "peligro"
    else:
        tono = "alerta"
    detalle: list[str] = []
    if estado == "transmitiendo":
        if transmision["ultimo_envio"]:
            detalle.append(f"enviada {antiguedad(time.time() - transmision['ultimo_envio'])}")
        if (transmision["posicion"] or {}).get("precision_m"):
            detalle.append(f"±{round(transmision['posicion']['precision_m'])} m")
    if transmision["sin_conexion"]:
        pendientes = transmision["pendientes"]
        detalle.append(f"sin conexión: {pendientes} posici{'ón' if pendientes == 1 else 'ones'} en espera")

    return ft.Container(
        content=ft.Row(
            [
                ft.Container(width=12, height=12, border_radius=6, bgcolor=p[tono]),
                ft.Column(
                    [
                        ft.Text(
                            "Ubicación bloqueada: permítala para este sitio en los ajustes del navegador"
                            if estado == "sin_permiso" and web
                            else TEXTO_TRANSMISION.get(estado, estado),
                            size=d.T_SM,
                            weight=ft.FontWeight.W_700,
                        ),
                        *([ft.Text(" · ".join(detalle), size=d.T_XS, color=p["texto-suave"])] if detalle else []),
                    ],
                    spacing=0,
                    expand=True,
                ),
            ],
            spacing=d.E3,
        ),
        padding=d.E3,
        bgcolor=p[f"{tono}-suave"],
        border=ft.Border.all(1, p[f"{tono}-borde"]),
        border_radius=d.R_MD,
    )


def enlace_como_llegar(parada: dict) -> str:
    """«Cómo llegar» abre el navegador de mapas que el conductor ya usa. La
    dirección sale del sistema solo cuando él lo pulsa, hacia la aplicación que
    él elige: el sistema no geocodifica direcciones ni se las envía a nadie por
    su cuenta (ADR-013)."""
    destino = ", ".join(x for x in (parada.get("direccion"), parada.get("ciudad")) if x)
    return f"https://www.google.com/maps/search/?api=1&query={quote(destino)}"


@ft.component
def TarjetaParada(parada: dict, al_entregar, al_reportar) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    en_reparto = parada["estado"] == "EN_REPARTO"
    extras = " · ".join(
        x
        for x in (
            f"{parada['bultos']} bultos" if (parada.get("bultos") or 1) > 1 else "",
            parada.get("descripcion", ""),
            f"OC {parada['orden_compra']}" if parada.get("orden_compra") else "",
        )
        if x
    )
    lineas: list[ft.Control] = [
        ft.Row(
            [
                ft.Container(
                    ft.Text(str(parada["orden"]), size=d.T_SM, weight=ft.FontWeight.W_800),
                    width=28,
                    height=28,
                    border_radius=14,
                    bgcolor=p["acento-suave"],
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(parada["destinatario"], size=d.T_MD, weight=ft.FontWeight.W_700),
                        ui.Texto(
                            " · ".join(x for x in (parada.get("direccion"), parada.get("referencia"), parada.get("ciudad")) if x),
                            tono="texto-suave",
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ui.EtiquetaEstado(parada["estado"], parada.get("codigo_estado")),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=d.E2,
        )
    ]
    if extras:
        lineas.append(ui.Texto(extras, tono="texto-tenue", tamano=d.T_XS))
    if parada["estado"] == "INCIDENCIA":
        lineas.append(ui.Texto("Detenida por una novedad. Continuarla lo autoriza la empresa.", tamano=d.T_XS))
    if parada["estado"] == "ENTREGADO":
        lineas.append(ui.Texto(f"Entregada {fecha_legible(parada.get('actualizada_en'))}", tono="texto-tenue", tamano=d.T_XS))
    if al_entregar or al_reportar:
        acciones: list[ft.Control] = []
        if parada.get("telefono"):
            acciones.append(ft.OutlinedButton("Llamar", icon=ft.Icons.CALL, url=f"tel:{parada['telefono']}", height=d.TACTIL))
        acciones += [
            ft.OutlinedButton("Cómo llegar", icon=ft.Icons.DIRECTIONS, url=enlace_como_llegar(parada), height=d.TACTIL),
            ui.Boton("Detalle", lambda: app.ir(f"/envios/{parada['envio_id']}"), variante="sutil"),
        ]
        if en_reparto and al_reportar:
            acciones.append(ui.Boton("Novedad", al_reportar, variante="secundario"))
        if en_reparto and al_entregar:
            acciones.append(ui.Boton("Entregar", al_entregar, icono=ft.Icons.CHECK))
        lineas.append(ft.Row(acciones, wrap=True, spacing=d.E2, run_spacing=d.E2))
    return ft.Container(
        content=ft.Column(lineas, spacing=d.E2),
        padding=d.E3,
        bgcolor=p["superficie"],
        border=ft.Border(
            left=ft.BorderSide(4, d.color_de_estado(p, parada["estado"])),
            top=ft.BorderSide(1, p["borde"]),
            right=ft.BorderSide(1, p["borde"]),
            bottom=ft.BorderSide(1, p["borde"]),
        ),
        border_radius=d.R_MD,
    )


# --------------------------------------------------------------------------- #
# Entrega y novedad
# --------------------------------------------------------------------------- #


def ModalEntrega(parada: dict | None, ubicacion: dict | None, al_cerrar) -> None:
    """Foto, nota y confirmación. Si la foto ya subió y lo que falló fue el
    registro, reintentar no vuelve a subirla: se conserva la evidencia
    confirmada."""
    app = use_app()
    archivo, poner_archivo = ft.use_state(None)
    fase, poner_fase = ft.use_state("inactiva")
    evidencia_id, poner_evidencia_id = ft.use_state(None)
    formulario = use_formulario({"nota": ""})
    estado_ref = ft.use_ref(lambda: {"archivo": None, "evidencia": None})
    ultima, poner_ultima = ft.use_state(None)

    if parada is not ultima:
        poner_ultima(parada)
        estado_ref.current = {"archivo": None, "evidencia": None}
        poner_archivo(None)
        poner_evidencia_id(None)
        poner_fase("inactiva")
        formulario.reemplazar({"nota": ""})

    async def subir():
        archivo_actual = estado_ref.current["archivo"]
        resultado = await cargar(app.api, parada["envio_id"], archivo_actual, poner_fase)
        return resultado["evidencia_id"]

    carga = use_mutacion(subir)

    async def registrar_entrega(evidencia):
        datos = {"estado": "ENTREGADO", "evidencia_id": evidencia}
        if formulario.actual["nota"].strip():
            datos["nota"] = formulario.actual["nota"].strip()
        if ubicacion:
            datos["ubicacion"] = ubicacion
        await app.api.registrar_evento(parada["envio_id"], datos)
        app.almacen.invalidar(*TRAS_ESCRIBIR)

    registrar = use_mutacion(registrar_entrega)
    ocupado = carga.pendiente or registrar.pendiente

    async def elegir():
        elegido = await elegir_foto()
        if elegido:
            estado_ref.current["archivo"] = elegido
            poner_archivo(elegido)

    async def confirmar():
        try:
            evidencia = estado_ref.current["evidencia"]
            if not evidencia:
                if not estado_ref.current["archivo"]:
                    return
                evidencia = await carga.ejecutar()
                estado_ref.current["evidencia"] = evidencia
                poner_evidencia_id(evidencia)
            await registrar.ejecutar(evidencia)
            app.avisar(f"Entregado a {parada['destinatario']}.", "exito")
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra en el formulario
            poner_fase("inactiva")

    contenido: list[ft.Control] = []
    if parada:
        if evidencia_id:
            contenido.append(ui.Aviso("La foto ya está guardada. Falta registrar la entrega.", tono="exito"))
        else:
            contenido += [
                ft.Row([ui.Boton("Tomar o elegir la foto" if not archivo else "Cambiar la foto", elegir, variante="secundario", icono=ft.Icons.PHOTO_CAMERA)]),
                ui.Texto("Sin foto no se puede dar por entregado. Va cifrada al almacenamiento.", tono="texto-tenue", tamano=d.T_XS),
                VistaPrevia(archivo),
            ]
        contenido.append(ui.Campo("Nota", formulario.valores["nota"], formulario.poner("nota"), opcional=True, multilinea=True, filas=2, sugerencia="Recibió en portería"))
        if carga.pendiente:
            contenido.append(PasosCarga(fase))
        if carga.error:
            contenido.append(ui.Aviso(mensaje_de_error(carga.error), tono="error", titulo="La foto no se guardó"))
        if registrar.error:
            contenido.append(ui.Aviso(mensaje_de_error(registrar.error), tono="error", titulo="La entrega no se registró"))
        if not ubicacion:
            contenido.append(ui.Texto("Sin lectura de GPS en este momento: la entrega se registra sin coordenadas.", tono="texto-tenue", tamano=d.T_XS))

    ui.use_modal(
        parada is not None,
        f"Entregar a {(parada or {}).get('destinatario', '')}",
        contenido,
        al_cerrar,
        ayuda=(parada or {}).get("direccion"),
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario", deshabilitado=ocupado),
            ui.Boton("Confirmar entrega", confirmar, cargando=ocupado, deshabilitado=not archivo and not evidencia_id),
        ],
        bloqueado=ocupado,
    )


def ModalNovedad(parada: dict | None, ubicacion: dict | None, al_cerrar) -> None:
    app = use_app()
    formulario = use_formulario({"nota": ""})
    ultima, poner_ultima = ft.use_state(None)
    if parada is not ultima:
        poner_ultima(parada)
        formulario.reemplazar({"nota": ""})

    async def reportar_novedad():
        datos = {"estado": "INCIDENCIA", "nota": formulario.actual["nota"].strip()}
        if ubicacion:
            datos["ubicacion"] = ubicacion
        await app.api.registrar_evento(parada["envio_id"], datos)
        app.almacen.invalidar(*TRAS_ESCRIBIR)

    registrar = use_mutacion(reportar_novedad)

    async def reportar():
        if len(formulario.actual["nota"].strip()) < 3:
            return
        try:
            await registrar.ejecutar()
            app.avisar("Novedad reportada. La empresa decide cómo continuar.", "exito")
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra en el formulario
            pass

    contenido: list[ft.Control] = [
        ui.Campo(
            "¿Qué pasó?",
            formulario.valores["nota"],
            formulario.poner("nota"),
            multilinea=True,
            filas=3,
            sugerencia="Nadie atiende en la dirección",
        )
    ]
    if registrar.error:
        contenido.append(ui.Aviso(mensaje_de_error(registrar.error), tono="error", titulo="La novedad no se registró"))
    ui.use_modal(
        parada is not None,
        f"Novedad con {(parada or {}).get('destinatario', '')}",
        contenido,
        al_cerrar,
        ayuda="La parada queda detenida. Continuarla o devolver el paquete lo decide la empresa.",
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario", deshabilitado=registrar.pendiente),
            ui.Boton(
                "Reportar novedad",
                reportar,
                variante="peligro",
                cargando=registrar.pendiente,
                deshabilitado=len(formulario.valores["nota"].strip()) < 3,
            ),
        ],
        bloqueado=registrar.pendiente,
    )
