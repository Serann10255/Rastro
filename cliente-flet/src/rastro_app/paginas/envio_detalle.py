"""Detalle del envío: histórico, punto de control, asignación y evidencia.

Las acciones que se muestran salen de lo que el servidor dice que es posible
(`/transiciones`) y no de una copia de la máquina de estados escrita aquí: dos
fuentes de verdad acaban diciendo cosas distintas, y la del cliente se queda
atrás sin que nadie lo note hasta ver un rechazo inexplicable.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_formulario, use_mutacion
from comun.formato import fecha_legible, fecha_relativa, texto_estado
from rastro_app.consultas import TRAS_ESCRIBIR, use_mensajeros
from rastro_app.contexto import mensaje_de_error, use_app, use_sesion
from rastro_app.evidencia import PasosCarga, VistaPrevia, cargar, elegir_foto


@ft.component
def EnvioDetalle() -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    envio_id = ft.use_route_params().get("envio_id", "")
    recien_creado, _ = ft.use_state(lambda: app.tomar("recien_creado", False))

    detalle = use_consulta(app.almacen, ("envio", envio_id), lambda: app.api.consultar_envio(envio_id))
    transiciones = use_consulta(app.almacen, ("transiciones", envio_id), lambda: app.api.transiciones(envio_id))
    puede_descargar = sesion.puede("evidencia:descargar")
    evidencias = use_consulta(
        app.almacen,
        ("evidencias", envio_id),
        lambda: app.api.listar_evidencias(envio_id),
        habilitada=puede_descargar,
    )

    if detalle.cargando:
        return ft.Column([ui.Esqueleto(alto=120), ui.Esqueleto(alto=320)], spacing=d.E4)
    if detalle.error and not detalle.datos:
        return ui.Tarjeta(
            ui.Vacio(
                "No se pudo abrir el envío",
                mensaje_de_error(detalle.error),
                ui.Boton("Volver a la lista", lambda: app.ir("/envios"), variante="secundario"),
            )
        )

    envio = detalle.datos["envio"]
    eventos = detalle.datos.get("eventos") or []
    datos_transiciones = transiciones.datos or {}
    detalle_transiciones = datos_transiciones.get("detalle_transiciones") or []
    puede_registrar = bool(datos_transiciones.get("transiciones"))
    confirmadas = envio.get("evidencias") or []

    destino = envio["destino"]
    encabezado = ft.Row(
        [
            ft.Column(
                [
                    ui.Titulo(envio["destinatario"]["nombre"]),
                    ui.Texto(
                        " · ".join(x for x in (destino.get("linea"), destino.get("referencia"), destino.get("ciudad")) if x),
                        tono="texto-suave",
                    ),
                ],
                spacing=d.E1,
                expand=True,
            ),
            ui.EtiquetaEstado(envio["estado"], envio.get("codigo_estado"), con_punto=True),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    acciones_id: list[ft.Control] = [ui.BotonCopiar(envio["envio_id"])]
    if sesion.puede("envio:asignar"):
        acciones_id.append(
            ui.Boton(
                "Generar guía",
                lambda: app.ir("/envios/guias", envios_guias=[envio["envio_id"]]),
                variante="secundario",
                icono=ft.Icons.QR_CODE_2,
            )
        )

    def con_referencia(direccion: dict) -> str:
        return direccion.get("linea", "") + (f" · {direccion['referencia']}" if direccion.get("referencia") else "")

    bultos = envio.get("bultos") or 1
    izquierda: list[ft.Control] = [
        ui.Tarjeta(
            [
                ft.Text(envio["envio_id"], size=d.T_BASE, font_family=d.FUENTE_MONO, selectable=True),
                ft.TextButton(
                    "Ver como lo ve el destinatario",
                    icon=ft.Icons.OPEN_IN_NEW,
                    on_click=lambda: app.ir(f"/rastreo?envio={envio['envio_id']}"),
                ),
            ],
            titulo="Identificador de rastreo",
            ayuda="Aleatorio y no consecutivo, para que nadie pueda recorrer los envíos de la empresa desde "
            "el punto público.",
            acciones=acciones_id,
        ),
        ui.Tarjeta(
            LineaDeTiempo(eventos),
            titulo="Histórico",
            ayuda=f"{len(eventos)} punto{'' if len(eventos) == 1 else 's'} de control, cada uno atribuido a un responsable.",
        ),
        ui.Tarjeta(
            ui.Rejilla(
                [
                    ui.Dato("Origen", con_referencia(envio["origen"])),
                    ui.Dato("Destino", con_referencia(destino)),
                    ui.Dato(
                        "Destinatario",
                        envio["destinatario"]["nombre"]
                        + (f" · {envio['destinatario']['telefono']}" if envio["destinatario"].get("telefono") else ""),
                    ),
                    ui.Dato("Mensajero", envio.get("conductor_nombre") or "sin asignar"),
                    ui.Dato("Cliente", envio.get("cliente_nombre") or "—"),
                    ui.Dato("Tienda de origen", envio.get("tienda_nombre") or "—"),
                    ui.Dato("Estación actual", envio.get("estacion_actual") or "—"),
                    ui.Dato("Transportista", envio.get("transportista_nombre") or "por asignar"),
                    ui.Dato("Orden de compra", envio.get("orden_compra") or "—"),
                    ui.Dato(
                        "Carga",
                        f"{bultos} bulto{'' if bultos == 1 else 's'}"
                        + (f" · {envio['peso_kg']} kg" if envio.get("peso_kg") else ""),
                    ),
                    ui.Dato("Entrega estimada", envio.get("fecha_estimada") or "sin fecha comprometida"),
                    ui.Dato("Descripción", envio.get("descripcion") or "—"),
                    ui.Dato("Registrado", f"{fecha_legible(envio.get('creado_en'))} por {envio.get('creado_por', '')}"),
                ],
                {"xs": 12, "sm": 6},
            ),
            titulo="Datos del envío",
        ),
    ]

    derecha: list[ft.Control] = []
    if datos_transiciones.get("exige_autorizacion_despachador"):
        derecha.append(
            ui.Aviso(
                "Reanudarlo requiere autorización del despachador. El conductor reporta el incidente; otro "
                "rol decide si continúa.",
                tono="alerta",
                titulo="Envío detenido por una incidencia",
            )
        )
    if envio["estado"] == "CREADO" and sesion.puede("envio:asignar"):
        derecha.append(PanelAsignacion(envio_id))
    if sesion.puede("evento:registrar") and envio["estado"] != "ENTREGADO":
        derecha.append(PanelEvidencia(envio_id, len(confirmadas)))
    if puede_registrar:
        derecha.append(PanelPuntoDeControl(envio_id, detalle_transiciones, confirmadas, key=envio["estado"]))
    else:
        entregado = envio["estado"] == "ENTREGADO"
        derecha.append(
            ui.Tarjeta(
                ui.Vacio(
                    "Envío entregado" if entregado else "Sin acciones disponibles",
                    "El estado ENTREGADO es final: el envío no admite más cambios."
                    if entregado
                    else "Su rol no puede registrar puntos de control en este envío.",
                )
            )
        )
    if puede_descargar:
        derecha.append(ListaEvidencias(evidencias))

    partes: list[ft.Control] = [encabezado]
    if recien_creado:
        partes.append(
            ui.Aviso(
                "Entregue este identificador al destinatario: es lo único que necesita para consultar el "
                "avance, y no puede deducirse.",
                tono="exito",
                titulo="Envío registrado",
            )
        )
    partes.append(ui.DoblePanel(izquierda, derecha))
    return ft.Column(partes, spacing=d.E4)


@ft.component
def LineaDeTiempo(eventos: list) -> ft.Control:
    p = ui.paleta()
    if not eventos:
        return ui.Vacio("Sin eventos", "El histórico se llena al registrar puntos de control.")
    pasos = []
    for evento in eventos:
        color = d.color_de_estado(p, evento["estado"])
        lineas: list[ft.Control] = [
            ft.Text(
                spans=[
                    ft.TextSpan(f"{evento.get('codigo_estado', '')} ", ft.TextStyle(color=p["texto-tenue"])),
                    ft.TextSpan(texto_estado(evento["estado"]), ft.TextStyle(color=color)),
                ],
                size=d.T_SM,
                weight=ft.FontWeight.W_700,
            ),
            ui.Texto(f"{fecha_legible(evento.get('ts'))} · {fecha_relativa(evento.get('ts'))}", tono="texto-suave", tamano=d.T_XS),
            ui.Texto(
                f"por {evento.get('actor_sub', '')}"
                + (f" ({', '.join(evento['actor_grupos'])})" if evento.get("actor_grupos") else ""),
                tono="texto-suave",
                tamano=d.T_XS,
            ),
        ]
        if evento.get("nota"):
            lineas.append(ft.Text(evento["nota"], size=d.T_SM, selectable=True))
        if evento.get("ubicacion"):
            u = evento["ubicacion"]
            lineas.append(ui.Texto(f"{u['lat']:.5f}, {u['lon']:.5f}", tono="texto-suave", tamano=d.T_XS, mono=True))
        if evento.get("evidencia_id"):
            lineas.append(ui.Texto("Con evidencia adjunta", tono="texto-suave", tamano=d.T_XS))
        pasos.append(
            ft.Container(
                content=ft.Column(lineas, spacing=2),
                padding=ft.Padding.only(left=d.E3, bottom=d.E3),
                border=ft.Border(left=ft.BorderSide(3, color)),
            )
        )
    return ft.Column(pasos, spacing=d.E2)


# --------------------------------------------------------------------------- #
# Asignación
# --------------------------------------------------------------------------- #


@ft.component
def PanelAsignacion(envio_id: str) -> ft.Control:
    """Los mensajeros salen del directorio de la organización. Antes había tres
    escritos en la pantalla con su identificador: el día que entrara uno nuevo,
    nadie iba a recompilar el sitio para que apareciera."""
    app = use_app()
    equipo = use_mensajeros()
    formulario = use_formulario({"sub": "", "nombre": ""})

    async def operacion():
        await app.api.asignar_conductor(envio_id, formulario.actual["sub"].strip(), formulario.actual["nombre"].strip())
        app.almacen.invalidar(*TRAS_ESCRIBIR)

    asignar = use_mutacion(operacion)

    async def enviar():
        if not formulario.actual["sub"].strip():
            return
        try:
            await asignar.ejecutar()
            app.avisar("Mensajero asignado.", "exito")
        except Exception:  # noqa: BLE001 - se muestra bajo el formulario
            pass

    mensajeros = (equipo.datos or {}).get("mensajeros", [])
    partes: list[ft.Control] = []
    if equipo.cargando:
        partes.append(ui.Cargando("Cargando mensajeros…"))
    if equipo.error:
        partes.append(ui.Aviso("No fue posible leer el equipo. Puede escribir el identificador del mensajero a mano.", tono="alerta"))
    if not equipo.cargando and not equipo.error and not mensajeros:
        partes.append(
            ui.Aviso(
                "Cree una cuenta con el rol conductor en Administración antes de asignar. Sin conductor, el "
                "envío no puede salir de CREADO.",
                tono="alerta",
                titulo="La empresa no tiene mensajeros activos",
            )
        )
    if mensajeros:
        partes.append(
            ft.Row(
                [
                    ui.Boton(
                        m["nombre"],
                        lambda m=m: formulario.reemplazar({"sub": m["sub"], "nombre": m["nombre"]}),
                        variante="primario" if formulario.valores["sub"] == m["sub"] else "secundario",
                    )
                    for m in mensajeros
                ],
                wrap=True,
                spacing=d.E2,
                run_spacing=d.E2,
            )
        )
    partes += [
        ui.Campo(
            "Identificador del mensajero",
            formulario.valores["sub"],
            formulario.poner("sub"),
            ayuda="Se rellena al elegir arriba. Debe coincidir con el sujeto del token del conductor.",
        ),
        ui.Campo("Nombre", formulario.valores["nombre"], formulario.poner("nombre")),
    ]
    if asignar.error:
        partes.append(ui.Aviso(mensaje_de_error(asignar.error), tono="error"))
    partes.append(ft.Row([ui.Boton("Asignar", enviar, cargando=asignar.pendiente, deshabilitado=not formulario.valores["sub"].strip())]))
    return ui.Tarjeta(partes, titulo="Asignar mensajero", ayuda="Transición CREADO → ASIGNADO. La valida la máquina de estados.")


# --------------------------------------------------------------------------- #
# Evidencia
# --------------------------------------------------------------------------- #


@ft.component
def PanelEvidencia(envio_id: str, confirmadas: int) -> ft.Control:
    app = use_app()
    archivo, poner_archivo = ft.use_state(None)
    fase, poner_fase = ft.use_state("inactiva")
    archivo_ref = ft.use_ref(None)

    async def operacion():
        resultado = await cargar(app.api, envio_id, archivo_ref.current, poner_fase)
        app.almacen.invalidar(*TRAS_ESCRIBIR)
        return resultado

    carga = use_mutacion(operacion)

    async def elegir():
        elegido = await elegir_foto()
        if elegido:
            archivo_ref.current = elegido
            poner_archivo(elegido)

    async def enviar():
        if not archivo_ref.current:
            return
        try:
            resultado = await carga.ejecutar()
            cifrado = (resultado.get("propiedades") or {}).get("cifrado") or "sin KMS en entorno local"
            app.avisar(f"Evidencia almacenada ({cifrado}). Ya puede registrar la entrega.", "exito")
            archivo_ref.current = None
            poner_archivo(None)
        except Exception:  # noqa: BLE001 - se muestra en la tarjeta
            poner_fase("inactiva")

    partes: list[ft.Control] = []
    if confirmadas:
        partes.append(
            ui.Aviso(
                f"{confirmadas} evidencia{'' if confirmadas == 1 else 's'} confirmada{'' if confirmadas == 1 else 's'}. "
                "Ya puede registrar la entrega.",
                tono="exito",
            )
        )
    partes += [
        ft.Row(
            [
                ui.Boton("Elegir foto" if not archivo else "Cambiar foto", elegir, variante="secundario", icono=ft.Icons.PHOTO_CAMERA),
                *([ui.Texto(archivo.name, tono="texto-suave", maximo_lineas=1)] if archivo else []),
            ],
            spacing=d.E2,
        ),
        VistaPrevia(archivo),
        ui.Texto("En el teléfono puede tomarla con la cámara o elegirla de la galería.", tono="texto-tenue", tamano=d.T_XS),
    ]
    if carga.pendiente:
        partes.append(PasosCarga(fase))
    if carga.error:
        partes.append(ui.Aviso(mensaje_de_error(carga.error), tono="error", titulo="La evidencia no se guardó"))
    partes.append(ft.Row([ui.Boton("Cargar evidencia", enviar, variante="secundario", deshabilitado=not archivo, cargando=carga.pendiente, bloque=True)]))
    return ui.Tarjeta(
        partes,
        titulo="Evidencia de entrega",
        ayuda="El archivo va directo al almacenamiento con un enlace de vigencia limitada: no atraviesa los servicios.",
    )


@ft.component
def ListaEvidencias(evidencias) -> ft.Control:
    p = ui.paleta()
    if evidencias.cargando:
        contenido: ft.Control | list = ui.Esqueleto(alto=64)
    elif (evidencias.datos or {}).get("evidencias"):
        filas = []
        for evidencia in evidencias.datos["evidencias"]:
            propiedades = evidencia.get("propiedades") or {}
            version = propiedades.get("version_id")
            filas.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(propiedades.get("cifrado") or "sin cifrado declarado", size=d.T_SM, weight=ft.FontWeight.W_600, expand=True),
                                    ft.TextButton("Abrir", url=evidencia.get("url_descarga")),
                                ]
                            ),
                            ui.Texto(propiedades.get("clave", ""), tono="texto-tenue", tamano=d.T_XS, mono=True),
                            ui.Texto(
                                f"{propiedades.get('tamano') or 0} bytes" + (f" · versión {version[:8]}" if version else ""),
                                tono="texto-tenue",
                                tamano=d.T_XS,
                            ),
                        ],
                        spacing=2,
                    ),
                    padding=ft.Padding.symmetric(vertical=d.E2),
                    border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
                )
            )
        contenido = filas
    else:
        contenido = ui.Vacio("Sin evidencias", "Se cargan al momento de la entrega.")
    return ui.Tarjeta(
        contenido,
        titulo="Evidencias de entrega",
        ayuda="Almacenadas cifradas. El conductor las carga; consultarlas corresponde a otros roles.",
    )


# --------------------------------------------------------------------------- #
# Punto de control
# --------------------------------------------------------------------------- #


@ft.component
def PanelPuntoDeControl(envio_id: str, transiciones: list, confirmadas: list) -> ft.Control:
    """Un solo formulario y ningún campo obligatorio más allá del estado: si
    registrar el avance cuesta más que enviar un mensaje de chat, el mensajero
    vuelve al chat. El estado se elige con botones, no con un desplegable: un
    toque en lugar de tres."""
    app = use_app()
    p = ui.paleta()
    formulario = use_formulario(
        {"estado": transiciones[0]["estado"] if transiciones else None, "nota": "", "ubicacion": True}
    )

    estado = formulario.valores["estado"]
    exige_evidencia = estado == "ENTREGADO"
    falta_evidencia = exige_evidencia and not confirmadas

    async def operacion(datos):
        resultado = await app.api.registrar_evento(envio_id, datos)
        app.almacen.invalidar(*TRAS_ESCRIBIR)
        return resultado

    registrar = use_mutacion(operacion)

    async def enviar():
        actual = formulario.actual
        if not actual["estado"]:
            return
        datos = {"estado": actual["estado"]}
        if actual["nota"].strip():
            datos["nota"] = actual["nota"].strip()
        if actual["estado"] == "ENTREGADO" and confirmadas:
            datos["evidencia_id"] = confirmadas[-1]
        if actual["ubicacion"]:
            # La geolocalización puede tardar o ser denegada, y no se deja que
            # bloquee el registro: un punto de control sin coordenadas sigue
            # siendo evidencia válida.
            lectura, _fallo = await app.gps.leer(espera=8)
            if lectura:
                datos["ubicacion"] = {"lat": lectura["lat"], "lon": lectura["lon"]}
            else:
                app.avisar("No se obtuvo la ubicación; el punto de control se registra sin ella.", "alerta")
        try:
            await registrar.ejecutar(datos)
            app.avisar(f"Punto de control registrado: {texto_estado(actual['estado'])}.", "exito")
            formulario.poner("nota")("")
        except Exception:  # noqa: BLE001 - se muestra bajo el formulario
            pass

    opciones = []
    for destino in transiciones:
        elegido = destino["estado"] == estado
        color = d.color_de_estado(p, destino["estado"])
        textos: list[ft.Control] = [
            ft.Text(
                spans=[
                    ft.TextSpan(f"{destino['codigo']} ", ft.TextStyle(color=p["texto-tenue"])),
                    ft.TextSpan(destino.get("etiqueta") or texto_estado(destino["estado"])),
                ],
                size=d.T_SM,
                weight=ft.FontWeight.W_600,
            )
        ]
        if destino.get("final"):
            textos.append(ft.Text("Cierra el envío: no admite más cambios", size=d.T_XS, color=p["texto-suave"]))
        opciones.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                        ft.Column(textos, spacing=0, expand=True),
                    ],
                    spacing=d.E2,
                ),
                padding=ft.Padding.symmetric(horizontal=d.E3, vertical=d.E2),
                border=ft.Border.all(2 if elegido else 1, color if elegido else p["borde"]),
                border_radius=d.R_MD,
                bgcolor=d.fondo_de_estado(p, destino["estado"]) if elegido else p["superficie"],
                on_click=lambda _e, e=destino["estado"]: formulario.poner("estado")(e),
                ink=True,
            )
        )

    partes: list[ft.Control] = [
        ft.Text("NUEVO ESTADO", size=d.T_XS, weight=ft.FontWeight.W_700, color=p["texto-suave"]),
        ui.Rejilla(opciones, {"xs": 12, "sm": 6}, espacio=d.E2),
        ui.Texto("Solo se ofrecen los estados alcanzables desde el actual. El servidor los vuelve a comprobar.", tono="texto-tenue", tamano=d.T_XS),
        ui.Campo("Nota", formulario.valores["nota"], formulario.poner("nota"), opcional=True, multilinea=True, filas=2, sugerencia="Recibido en portería"),
        ui.Casilla(
            "Adjuntar mi ubicación",
            formulario.valores["ubicacion"],
            formulario.poner("ubicacion"),
            "Se captura solo en este momento. El seguimiento continuo existe únicamente en el modo ruta, y lo "
            "inicia el conductor desde Entregas.",
        ),
    ]
    if falta_evidencia:
        partes.append(
            ui.Aviso(
                "Cargue y confirme la foto de la entrega antes de registrar el estado ENTREGADO.",
                tono="alerta",
                titulo="La entrega exige evidencia",
            )
        )
    if registrar.error:
        partes.append(ui.Aviso(mensaje_de_error(registrar.error), tono="error", titulo="No se registró el punto de control"))
    partes.append(
        ft.Row(
            [
                ui.Boton(
                    f"Registrar {texto_estado(estado) if estado else ''}",
                    enviar,
                    cargando=registrar.pendiente,
                    deshabilitado=not estado or falta_evidencia,
                    bloque=True,
                    grande=True,
                )
            ]
        )
    )
    return ui.Tarjeta(
        partes,
        titulo="Registrar punto de control",
        ayuda="Un solo formulario y ningún campo obligatorio más allá del estado. La marca de tiempo la pone el servidor.",
    )
