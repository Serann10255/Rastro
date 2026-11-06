"""Revisión: ejecutar el catálogo y leer el resultado.

Es la traducción de `VistaEjecucion` y sus piezas en `cotejo/web/src/App.tsx`.
El papel de trabajo y el informe se abren en un diálogo, como los modales de la
web; el informe, además, se puede guardar como archivo, que en una aplicación
instalada es la forma de llevárselo.
"""

from __future__ import annotations

import json
from typing import Any

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_mutacion
from comun.formato import fecha_legible
from cotejo_app.claves import CLAVE_AYUDA
from cotejo_app.contexto import mensaje_de_error, use_ancho, use_app, use_consola
from cotejo_app.piezas import (
    RESPUESTAS,
    SEVERIDADES,
    Bloque,
    CampoHallazgo,
    ConTecnicismo,
    DetalleTecnico,
    EtiquetaSeveridad,
    Preformateado,
    Respuesta,
    TextoMono,
    colores_de_ficha,
)

def HUECO() -> ft.Control:
    """El sitio de una pieza que ahora no se muestra. Invisible y no solo vacío:
    así tampoco cuenta para el espacio entre piezas de la columna."""
    return ft.Container(visible=False)


# --------------------------------------------------------------------------- #
# Cómo funciona
# --------------------------------------------------------------------------- #

PASOS = [
    (
        "Primero se escribe qué se va a comprobar",
        "Antes de tocar nada. Si la regla se escribiera después de ver el resultado, siempre se podría "
        "acomodar para que quede bonito.",
        "en auditoría: criterio declarado",
    ),
    (
        "Después se usa el sistema de verdad",
        "Cotejo entra como un conductor, como una empresa que no debería mirar, e intenta hacer lo que no "
        "le toca, para ver qué contesta Rastro.",
        "en auditoría: prueba sustantiva",
    ),
    (
        "Y se guarda lo que pasó, con un sello",
        "Se guarda la respuesta tal cual, sin resumir, y se le calcula un sello. Si alguien cambiara una "
        "letra de ese archivo, el sello dejaría de cuadrar y se notaría.",
        "en auditoría: papel de trabajo y huella",
    ),
]


@ft.component
def NumeroPaso(numero: str) -> ft.Control:
    p = ui.paleta()
    return ft.Container(
        content=ft.Text(numero, size=d.T_SM, weight=ft.FontWeight.W_700, color=p["acento-fuerte"]),
        width=28,
        height=28,
        bgcolor=p["acento-suave"],
        border_radius=14,
        alignment=ft.Alignment.CENTER,
    )


@ft.component
def PanelComoFunciona(que_es_esto: str | None) -> ft.Control:
    """Los tres pasos del trabajo, para quien abre esto por primera vez. Se puede
    ocultar, y se recuerda oculto: una explicación que no se puede cerrar acaba
    siendo ruido para quien ya la leyó."""
    app = use_app()
    oculto, poner_oculto = ft.use_state(lambda: bool(app.banderas.get(CLAVE_AYUDA)))

    async def cambiar(valor: bool):
        poner_oculto(valor)
        await app.poner_bandera(CLAVE_AYUDA, valor)

    async def mostrar():
        await cambiar(False)

    async def ocultar():
        await cambiar(True)

    if oculto:
        return ft.Row(
            [
                ui.Texto("¿Primera vez por aquí?", tono="texto-tenue", tamano=d.T_XS, seleccionable=False),
                ui.Boton("Explicar cómo funciona", mostrar, variante="sutil"),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True,
        )

    return ui.Tarjeta(
        [
            ft.Row(
                [
                    NumeroPaso(str(numero)),
                    ft.Column(
                        [
                            ft.Text(titulo, size=d.T_SM, weight=ft.FontWeight.W_700),
                            ConTecnicismo(texto, tecnicismo),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=d.E3,
            )
            for numero, (titulo, texto, tecnicismo) in enumerate(PASOS, start=1)
        ],
        titulo="Cómo funciona esto",
        ayuda=que_es_esto,
        acciones=[ui.Boton("Ocultar", ocultar, variante="sutil")],
    )


# --------------------------------------------------------------------------- #
# Pantalla
# --------------------------------------------------------------------------- #


@ft.component
def VistaEjecucion() -> ft.Control:
    app = use_app()
    consola = use_consola()
    ancho = use_ancho()
    ejecucion_id = consola.ejecucion_id
    catalogo = (consola.catalogo.datos if consola.catalogo else None) or {}
    ejecuciones = ((consola.ejecuciones.datos if consola.ejecuciones else None) or {}).get("ejecuciones", [])

    detalle = use_consulta(
        app.almacen,
        ("ejecucion", ejecucion_id or ""),
        lambda: app.api.ejecucion(ejecucion_id),
        habilitada=bool(ejecucion_id),
    )
    control_abierto, poner_control = ft.use_state(None)
    ver_informe, poner_ver_informe = ft.use_state(False)
    verificacion, poner_verificacion = ft.use_state(None)
    verificar = use_mutacion(lambda: app.api.verificar_almacen(ejecucion_id))

    # Cambiar de revisión olvida la verificación de la anterior: el aviso diría
    # «nadie las ha tocado» de unas pruebas que no son las que se ven.
    ft.use_effect(lambda: poner_verificacion(None), [ejecucion_id])

    async def verificar_almacen():
        try:
            poner_verificacion(await verificar.ejecutar())
        except Exception:  # noqa: BLE001 - se muestra junto al resultado
            pass

    # Los diálogos: papel de trabajo e informe.
    ancho_dialogo = min(ancho - 48, 832)
    estrecho = ancho < d.PUNTOS_DE_CORTE["sm"]
    margen_dialogo = ft.Padding.symmetric(horizontal=8 if estrecho else 40, vertical=16 if estrecho else 24)
    dialogo = None
    if control_abierto and ejecucion_id:
        dialogo = ft.AlertDialog(
            content=ft.Container(ContenidoPapel(ejecucion_id, control_abierto), width=ancho_dialogo),
            actions=[ft.TextButton("Cerrar", on_click=lambda: poner_control(None))],
            scrollable=True,
            inset_padding=margen_dialogo,
            on_dismiss=lambda _e: poner_control(None),
        )
    elif ver_informe and ejecucion_id:
        dialogo = ft.AlertDialog(
            content=ft.Container(ContenidoInforme(ejecucion_id), width=min(ancho - 48, 960)),
            actions=[ft.TextButton("Cerrar", on_click=lambda: poner_ver_informe(False))],
            scrollable=True,
            inset_padding=margen_dialogo,
            on_dismiss=lambda _e: poner_ver_informe(False),
        )
    ft.use_dialog(dialogo)

    total_catalogo = len(catalogo.get("controles", [])) or 8
    partes: list[ft.Control] = [
        ui.Encabezado(
            "Revisión",
            f"Al pulsar el botón, Cotejo comprueba de una sola vez las {total_catalogo} cosas de la lista, "
            "sin que nadie tenga que ir una por una. Tarda alrededor de un minuto.",
            [
                ui.Boton(
                    "Revisando…" if consola.ejecutando else "Revisar ahora",
                    consola.ejecutar,
                    cargando=consola.ejecutando,
                    grande=True,
                    icono=ft.Icons.PLAY_ARROW,
                )
            ],
        ),
        PanelComoFunciona(catalogo.get("que_es_esto")),
    ]

    # Cada pieza tiene su sitio fijo, ocupado por un hueco cuando no se muestra:
    # si el resultado cambiara de posición al aparecer un aviso, Flet lo volvería
    # a montar y se cerraría lo que el auditor tenía abierto.
    partes.append(
        ui.Aviso(mensaje_de_error(consola.error_ejecucion), tono="error", titulo="No se pudo revisar")
        if consola.error_ejecucion
        else HUECO()
    )

    if len(ejecuciones) <= 1:
        partes.append(HUECO())
    else:
        # En una fila: el desplegable se estira a lo ancho, y en una columna que
        # se desplaza se estiraría a lo alto sin límite.
        partes.append(
            ft.Row(
                [
                    ui.Selector(
                        "Revisión que se está viendo",
                        ejecucion_id or "",
                        [
                            (
                                e["ejecucion_id"],
                                f"{fecha_legible(e.get('cerrado_en'))} — {e.get('conformes', 0)} bien, "
                                f"{e.get('desviados', 0)} mal, {e.get('no_ejecutados', 0)} sin revisar",
                            )
                            for e in ejecuciones
                        ],
                        lambda valor: consola.elegir(valor) if valor else None,
                    )
                ]
            )
        )

    if consola.ejecutando:
        partes.append(EnCurso(catalogo.get("controles", [])))
    elif not ejecucion_id:
        partes.append(
            ui.Tarjeta(
                ui.Vacio(
                    "Todavía no se ha revisado nada",
                    "Pulsa «Revisar ahora» y en unos segundos aparece aquí qué salió bien y qué no.",
                )
            )
        )
    elif detalle.error and not detalle.datos:
        partes.append(ui.Aviso(mensaje_de_error(detalle.error), tono="error"))
    elif detalle.cargando or not detalle.datos:
        partes.append(ui.Esqueleto(alto=256))
    else:
        partes.append(
            ResultadoEjecucion(
                detalle.datos,
                ejecucion_id,
                poner_control,
                verificar_almacen,
                verificacion,
                verificar.pendiente,
                verificar.error,
                lambda: poner_ver_informe(True),
            )
        )

    return ft.Column(partes, spacing=d.E4)


@ft.component
def EnCurso(controles: list[dict[str, Any]]) -> ft.Control:
    """Qué está pasando mientras se ejecuta. Se enseña la lista de lo que se va
    a comprobar, sin marcar ninguna como hecha: el programa responde de una vez y
    no informa de su avance, así que fingir un progreso sería inventar."""
    return ui.Tarjeta(
        [
            ft.Row(
                [NumeroPaso(control["id"].replace("C-", "")), ft.Column([ui.Texto(control.get("pregunta", ""))], expand=True)],
                spacing=d.E3,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
            for control in controles
        ]
        or ui.Cargando("Revisando…"),
        titulo="Revisando ahora mismo…",
        ayuda="Cotejo está usando Rastro de verdad: entra, intenta cosas que no debería poder hacer y anota "
        "lo que le contesta. Suele tardar unos segundos.",
        acciones=[ft.ProgressRing(width=20, height=20, stroke_width=2)],
    )


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #


@ft.component
def BarraResultado(conformes: int, desviados: int, no_ejecutados: int) -> ft.Control:
    p = ui.paleta()
    partes = [
        ft.Container(bgcolor=color, expand=cantidad, height=12)
        for cantidad, color in ((conformes, p["exito"]), (desviados, p["peligro"]), (no_ejecutados, p["texto-tenue"]))
        if cantidad > 0
    ]
    return ft.Container(
        content=ft.Row(partes or [ft.Container(height=12, expand=True)], spacing=2),
        height=12,
        bgcolor=p["fondo-sutil"],
        border_radius=999,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


@ft.component
def Veredicto(cobertura: dict[str, Any], metadatos: dict[str, Any], acciones: list[ft.Control]) -> ft.Control:
    p = ui.paleta()
    total = cobertura.get("controles_del_catalogo", 0)
    bien, mal, pendientes = cobertura.get("conformes", 0), cobertura.get("desviados", 0), cobertura.get("no_ejecutados", 0)
    negrita = ft.TextStyle(weight=ft.FontWeight.W_700)
    frase = ft.Text(
        spans=[
            ft.TextSpan("Revisamos "),
            ft.TextSpan(str(total), negrita),
            ft.TextSpan(" cosas que Rastro dice cumplir. "),
            ft.TextSpan(f"{bien} salieron bien", ft.TextStyle(weight=ft.FontWeight.W_700, color=p["exito"])),
            ft.TextSpan(", "),
            ft.TextSpan(f"{mal} salieron mal", ft.TextStyle(weight=ft.FontWeight.W_700, color=p["peligro"] if mal else None)),
            ft.TextSpan(" y "),
            ft.TextSpan(
                f"{pendientes} quedaron sin revisar",
                ft.TextStyle(weight=ft.FontWeight.W_700, color=p["alerta"] if pendientes else None),
            ),
            ft.TextSpan("."),
        ],
        size=d.T_LG,
        selectable=True,
    )
    nota = ft.Text(
        spans=[
            ft.TextSpan(f"Revisado el {fecha_legible(str(metadatos.get('iniciado_en') or ''))} sobre el entorno "),
            ft.TextSpan(str(metadatos.get("entorno") or ""), negrita),
            ft.TextSpan(", por "),
            ft.TextSpan(str(metadatos.get("identidad_ejecucion") or ""), negrita),
            ft.TextSpan("."),
        ],
        size=d.T_SM,
        color=p["texto-suave"],
        selectable=True,
    )
    return ft.Container(
        content=ft.Column(
            [frase, BarraResultado(bien, mal, pendientes), nota, ft.Row(acciones, wrap=True, spacing=d.E2, run_spacing=d.E2)],
            spacing=d.E4,
        ),
        padding=d.E5,
        bgcolor=p["superficie"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_LG,
    )


@ft.component
def ResultadoEjecucion(
    ejecucion: dict[str, Any],
    ejecucion_id: str,
    al_abrir_control,
    al_verificar,
    verificacion: dict[str, Any] | None,
    verificando: bool,
    error_verificacion: BaseException | None,
    al_ver_informe,
) -> ft.Control:
    cobertura = ejecucion.get("cobertura") or {}
    controles = ejecucion.get("controles") or []
    hallazgos = ejecucion.get("hallazgos") or []
    metadatos = ejecucion.get("metadatos") or {}
    propios = [h for h in hallazgos if not h.get("permanente")]
    permanentes = [h for h in hallazgos if h.get("permanente")]
    total = cobertura.get("controles_del_catalogo", 0)

    partes: list[ft.Control] = [
        Veredicto(
            cobertura,
            metadatos,
            [
                ui.Boton("Ver el informe completo", al_ver_informe, variante="secundario", icono=ft.Icons.ARTICLE_OUTLINED),
                ui.Boton(
                    "Comprobando…" if verificando else "¿Alguien tocó estas pruebas?",
                    al_verificar,
                    variante="secundario",
                    cargando=verificando,
                    icono=ft.Icons.FINGERPRINT,
                ),
            ],
        )
    ]

    partes.append(ui.Aviso(mensaje_de_error(error_verificacion), tono="error") if error_verificacion else HUECO())
    if not verificacion:
        partes.append(HUECO())
    else:
        if verificacion.get("almacen_integro"):
            texto = ConTecnicismo(
                f"Se volvió a calcular el sello de {verificacion.get('papeles_verificados')} pruebas guardadas y "
                "sale el mismo que se anotó el día que se ejecutaron.",
                "en auditoría: almacén íntegro",
                tono="texto",
            )
        else:
            afectados = ", ".join(x.get("control_id", "") for x in verificacion.get("discrepancias", []))
            texto = ui.Texto(
                f"El sello ya no cuadra en: {afectados}. El almacén no impide que se edite un archivo; lo que "
                "hace es que se note."
            )
        partes.append(
            ui.Aviso(
                texto,
                tono="exito" if verificacion.get("almacen_integro") else "error",
                titulo="Nadie las ha tocado"
                if verificacion.get("almacen_integro")
                else "Ojo: alguna prueba fue modificada después de guardarse",
            )
        )

    if not cobertura.get("no_ejecutados"):
        partes.append(HUECO())
    else:
        partes.append(
            ui.Aviso(
                f"{cobertura['no_ejecutados']} de las {total} no se pudieron comprobar aquí: son las que miran "
                "piezas de la nube que en este computador no existen. Quedan pendientes de ejecutarse contra la "
                "cuenta desplegada. Contarlas como buenas sería lo peor que podría hacer un programa de "
                "auditoría, así que tienen su propia casilla.",
                tono="alerta",
                titulo="Lo que quedó sin revisar no está aprobado",
            )
        )

    partes.append(
        ui.Rejilla(
            [
                ui.Metrica("Bien", cobertura.get("conformes", 0), "Se probó y cumplió", "exito"),
                ui.Metrica(
                    "Mal", cobertura.get("desviados", 0), "Se probó y no cumplió", "peligro" if cobertura.get("desviados") else None
                ),
                ui.Metrica(
                    "Sin revisar",
                    cobertura.get("no_ejecutados", 0),
                    "No se pudo probar aquí",
                    "alerta" if cobertura.get("no_ejecutados") else None,
                ),
                ui.Metrica("Se llegó a probar", cobertura.get("cobertura", ""), "En auditoría: cobertura", "acento"),
            ],
            {"xs": 12, "sm": 6, "lg": 3},
        )
    )

    partes.append(
        ui.Tarjeta(
            [FilaControl(papel, al_abrir_control, key=papel["control_id"]) for papel in controles],
            titulo="Una por una",
            ayuda="Toca cualquiera para ver exactamente qué se hizo y qué contestó Rastro, palabra por palabra.",
        )
    )

    cuerpo_hallazgos: list[ft.Control] = []
    if not propios:
        cuerpo_hallazgos.append(ui.Aviso("De lo que se pudo probar, nada salió mal.", tono="exito"))
    if permanentes:
        cuerpo_hallazgos.append(
            ui.Texto(
                f"Las {len(permanentes)} de abajo marcadas como «se sabe y no se puede arreglar aquí» salen en "
                "todos los informes: el laboratorio de clase no permite corregirlas. Se dicen igual, porque "
                "callarlas haría creer que se revisó más de lo que se revisó.",
                tono="texto-suave",
            )
        )
    cuerpo_hallazgos += [TarjetaHallazgo(h, ejecucion_id, key=h["id"]) for h in [*propios, *permanentes]]
    partes.append(
        ui.Tarjeta(
            cuerpo_hallazgos,
            titulo="Lo que hay que arreglar",
            ayuda="Cada cosa se cuenta en cinco partes: qué pasa, con qué regla choca, por qué pasa, qué daño "
            "puede causar y qué habría que hacer. Y siempre dice de qué prueba salió: sin eso, sería solo una "
            "afirmación. · en auditoría: hallazgo",
            acciones=[ui.Insignia(str(len(hallazgos)))],
        )
    )
    return ft.Column(partes, spacing=d.E4)


@ft.component
def FilaControl(papel: dict[str, Any], al_abrir) -> ft.Control:
    p = ui.paleta()
    ficha = RESPUESTAS.get(papel.get("conclusion"), RESPUESTAS["NO_EJECUTADA"])["ficha"]
    color, _, _ = colores_de_ficha(p, ficha)
    huella = str(papel.get("huella_evidencia") or "")
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(papel["control_id"], size=d.T_SM, weight=ft.FontWeight.W_700, font_family=d.FUENTE_MONO),
                        Respuesta(papel.get("conclusion", "NO_EJECUTADA"), papel.get("conclusion_llana")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    run_spacing=d.E1,
                ),
                ft.Text(papel.get("pregunta") or papel.get("control", ""), size=d.T_MD, weight=ft.FontWeight.W_600),
                ui.Texto(papel.get("resumen", ""), tono="texto-suave", seleccionable=False),
                ft.Row(
                    [
                        ft.Text("Ver qué se hizo y qué contestó", size=d.T_XS, color=p["acento"], weight=ft.FontWeight.W_600),
                        ft.Text(f"sello {huella[:12]}…", size=d.T_XS, font_family=d.FUENTE_MONO, color=p["texto-tenue"]),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
            ],
            spacing=d.E2,
        ),
        padding=d.E3,
        bgcolor=p["superficie"],
        border=ft.Border(
            left=ft.BorderSide(4, color),
            top=ft.BorderSide(1, p["borde"]),
            right=ft.BorderSide(1, p["borde"]),
            bottom=ft.BorderSide(1, p["borde"]),
        ),
        border_radius=d.R_MD,
        on_click=lambda _e: al_abrir(papel["control_id"]),
        ink=True,
    )


@ft.component
def TarjetaHallazgo(hallazgo: dict[str, Any], ejecucion_id: str) -> ft.Control:
    p = ui.paleta()
    color, _, _ = colores_de_ficha(p, SEVERIDADES.get(hallazgo.get("severidad"), ("", "texto-suave"))[1])
    cabecera: list[ft.Control] = [ft.Text(hallazgo["id"], size=d.T_SM, weight=ft.FontWeight.W_700, font_family=d.FUENTE_MONO)]
    if hallazgo.get("permanente"):
        cabecera.append(ft.Text("· se sabe y no se puede arreglar aquí", size=d.T_XS, color=p["texto-tenue"]))
    huella = str(hallazgo.get("huella_evidencia") or "")
    papel = f"{ejecucion_id}/{hallazgo.get('papel_de_trabajo', '')}" + (f" · huella {huella[:24]}…" if huella else "")
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [ft.Row(cabecera, spacing=d.E1, wrap=True, tight=True), EtiquetaSeveridad(hallazgo.get("severidad", "baja"))],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    run_spacing=d.E1,
                ),
                *([ft.Text(hallazgo["en_simple"], size=d.T_MD, selectable=True)] if hallazgo.get("en_simple") else []),
                CampoHallazgo("Qué habría que hacer", hallazgo.get("recomendacion")),
                DetalleTecnico(
                    [
                        CampoHallazgo("Control", hallazgo.get("control_id")),
                        CampoHallazgo("Condición", hallazgo.get("condicion")),
                        CampoHallazgo("Criterio", hallazgo.get("criterio")),
                        CampoHallazgo("Causa", hallazgo.get("causa")),
                        CampoHallazgo("Efecto", hallazgo.get("efecto")),
                        CampoHallazgo("Papel de trabajo", TextoMono(papel)),
                    ]
                ),
            ],
            spacing=d.E3,
        ),
        padding=d.E4,
        bgcolor=p["superficie"],
        border=ft.Border(
            left=ft.BorderSide(4, color),
            top=ft.BorderSide(1, p["borde"]),
            right=ft.BorderSide(1, p["borde"]),
            bottom=ft.BorderSide(1, p["borde"]),
        ),
        border_radius=d.R_MD,
    )


# --------------------------------------------------------------------------- #
# Papel de trabajo
# --------------------------------------------------------------------------- #

# Lo que significa cada código de respuesta, dicho como se lo contarías a
# alguien. No se inventa nada: se describe el número que está en la evidencia.
CODIGOS = {
    200: "contestó que sí y entregó lo que se le pidió",
    201: "creó lo que se le pidió",
    204: "hizo lo que se le pidió y no tenía nada que devolver",
    400: "rechazó la petición porque no es válida",
    401: "pidió identificarse primero",
    403: "dijo que ese usuario no tiene permiso",
    404: "dijo que eso no existe",
    409: "dijo que choca con algo que ya existe",
    422: "dijo que los datos enviados no sirven",
    500: "se rompió por dentro",
}


def explicar_salida(salida: Any) -> str | None:
    if not isinstance(salida, dict):
        return None
    partes: list[str] = []
    codigo = salida.get("codigo")
    if isinstance(codigo, int) and not isinstance(codigo, bool):
        texto = CODIGOS.get(codigo)
        partes.append(f"Rastro {texto} (código {codigo})." if texto else f"Rastro respondió con el código {codigo}.")
    if isinstance(salida.get("registros_totales"), int):
        partes.append(f"Se leyeron {salida['registros_totales']} anotaciones del cuaderno.")
    if isinstance(salida.get("coincidencias"), list):
        cuantas = len(salida["coincidencias"])
        partes.append(
            "Ninguna anotación cuadra con lo que se buscaba."
            if cuantas == 0
            else f"{cuantas} {'anotación cuadra' if cuantas == 1 else 'anotaciones cuadran'} con lo que se buscaba."
        )
    return " ".join(partes) or None


@ft.component
def NumeroObservacion(numero: int) -> ft.Control:
    p = ui.paleta()
    return ft.Container(
        content=ft.Text(str(numero), size=d.T_XS, weight=ft.FontWeight.W_700, color=p["texto-suave"]),
        width=24,
        height=24,
        bgcolor=p["fondo-sutil"],
        border_radius=12,
        alignment=ft.Alignment.CENTER,
    )


@ft.component
def Observacion(indice: int, observacion: dict[str, Any]) -> ft.Control:
    p = ui.paleta()
    explicacion = explicar_salida(observacion.get("salida"))
    partes: list[ft.Control] = [
        ft.Row(
            [NumeroObservacion(indice + 1), ft.Column([TextoMono(observacion.get("procedimiento", ""))], expand=True)],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=d.E2,
        )
    ]
    if explicacion:
        partes.append(ft.Text(explicacion, size=d.T_SM, selectable=True))
    if observacion.get("error"):
        partes.append(ft.Text(f"No se pudo completar: {observacion['error']}", size=d.T_SM, color=p["peligro"], selectable=True))
    if observacion.get("salida") is not None:
        partes.append(
            DetalleTecnico(
                [Preformateado(json.dumps(observacion["salida"], ensure_ascii=False, indent=2))],
                resumen="Ver la respuesta tal como llegó",
            )
        )
    return ft.Container(
        content=ft.Column(partes, spacing=d.E2),
        padding=d.E3,
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_MD,
    )


@ft.component
def ContenidoPapel(ejecucion_id: str, control_id: str) -> ft.Control:
    """La evidencia literal, con la huella recalculada al leerla: abrir el papel
    sirve además como comprobación de que nadie lo editó."""
    app = use_app()
    papel = use_consulta(
        app.almacen, ("papel", ejecucion_id, control_id), lambda: app.api.papel(ejecucion_id, control_id)
    )

    if papel.error and not papel.datos:
        return ui.Aviso(mensaje_de_error(papel.error), tono="error")
    contenido = (papel.datos or {}).get("contenido") if papel.datos else None
    cabecera = ft.Column(
        [
            ft.Text((contenido or {}).get("pregunta") or f"Prueba {control_id}", size=d.T_LG, weight=ft.FontWeight.W_700),
            ConTecnicismo(f"{control_id} · esto es lo que quedó guardado de la prueba", "en auditoría: papel de trabajo"),
        ],
        spacing=d.E1,
        tight=True,
    )
    if not contenido:
        return ft.Column([cabecera, ui.Esqueleto(alto=192)], spacing=d.E3, tight=True)

    datos = papel.datos
    coincide = datos.get("coincide")
    conclusion = contenido.get("conclusion", "NO_EJECUTADA")
    explicada = contenido.get("conclusion_explicada") or RESPUESTAS.get(conclusion, RESPUESTAS["NO_EJECUTADA"])["explicacion"]

    partes: list[ft.Control] = [
        cabecera,
        ui.Aviso(
            [
                ui.Texto(
                    "El sello que sale al recalcularlo ahora es el mismo que se anotó al ejecutar la prueba. Si "
                    "alguien hubiera cambiado una sola letra, no cuadraría."
                    if coincide
                    else "El sello que sale ahora no es el que se anotó. Alguien editó el archivo."
                ),
                TextoMono(f"ahora: {datos.get('huella_recalculada', '')}"),
                TextoMono(f"se anotó: {datos.get('huella_registrada') or '—'}"),
            ],
            tono="exito" if coincide else "error",
            titulo="Este archivo no se ha tocado desde que se guardó"
            if coincide
            else "Este archivo fue modificado después de guardarse",
        ),
        Bloque("Qué se hizo", [ui.Texto(contenido.get("en_simple") or contenido.get("procedimiento", ""), tamano=d.T_BASE)]),
        Bloque(
            "Qué contestó Rastro",
            [
                ui.Texto(contenido.get("resumen", ""), tamano=d.T_BASE),
                ft.Row([Respuesta(conclusion, contenido.get("conclusion_llana"), grande=True)], wrap=True),
                ui.Texto(explicada, tono="texto-suave"),
            ],
        ),
    ]
    if contenido.get("si_falla") and conclusion != "CONFORME":
        partes.append(Bloque("Por qué importa", [ui.Texto(contenido["si_falla"], tamano=d.T_BASE)]))

    partes.append(
        Bloque(
            "Paso a paso, con lo que respondió tal cual",
            [
                ConTecnicismo(
                    "Sin resumir ni retocar: es lo que permite que otra persona revise si la conclusión es justa.",
                    "en auditoría: evidencia",
                ),
                *[Observacion(i, o, key=str(i)) for i, o in enumerate(contenido.get("observaciones") or [])],
            ],
        )
    )
    partes.append(
        DetalleTecnico(
            [
                CampoHallazgo("Control", contenido.get("control")),
                CampoHallazgo("Marco de referencia", contenido.get("marco")),
                CampoHallazgo("Tipo de prueba", contenido.get("tipo")),
                CampoHallazgo("Procedimiento", contenido.get("procedimiento")),
                CampoHallazgo("Criterio", contenido.get("criterio")),
                CampoHallazgo("Evidencia esperada", contenido.get("evidencia_esperada")),
                CampoHallazgo("Conclusión", contenido.get("conclusion")),
                CampoHallazgo(
                    "Ejecutada", f"{fecha_legible(contenido.get('iniciado_en'))} bajo {contenido.get('identidad_ejecucion', '')}"
                ),
            ],
            resumen="Ver la ficha de auditoría de esta prueba",
        )
    )
    return ft.Column(partes, spacing=d.E3, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


@ft.component
def ContenidoInforme(ejecucion_id: str) -> ft.Control:
    app = use_app()
    informe = use_consulta(app.almacen, ("informe", ejecucion_id), lambda: app.api.informe_texto(ejecucion_id))
    guardando, poner_guardando = ft.use_state(False)
    texto = (informe.datos or {}).get("texto", "")

    async def guardar():
        poner_guardando(True)
        try:
            ruta = await ft.FilePicker().save_file(
                dialog_title="Guardar el informe",
                file_name=f"informe-{ejecucion_id}.txt",
                src_bytes=texto.encode("utf-8"),
            )
            if ruta or app.pagina.web:
                app.avisar("Informe guardado.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")
        finally:
            poner_guardando(False)

    cuerpo: ft.Control
    if informe.error and not informe.datos:
        cuerpo = ui.Aviso(mensaje_de_error(informe.error), tono="error")
    elif not informe.datos:
        cuerpo = ui.Esqueleto(alto=320)
    else:
        cuerpo = Preformateado(texto, alto_maximo=520)

    return ft.Column(
        [
            ft.Text("El informe completo", size=d.T_LG, weight=ft.FontWeight.W_700),
            ui.Texto(
                "Empieza en palabras normales y sigue con el registro técnico. Es el mismo archivo que se guarda "
                "junto a las pruebas.",
                tono="texto-suave",
            ),
            ft.Row(
                [ui.Boton("Guardar el informe", guardar, cargando=guardando, deshabilitado=not texto, icono=ft.Icons.DOWNLOAD)],
                wrap=True,
            ),
            cuerpo,
        ],
        spacing=d.E3,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
