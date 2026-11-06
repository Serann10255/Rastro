"""¿Sale lo mismo si lo repite otra persona?

Debería. Si el resultado dependiera de quién ejecuta el programa, no sería una
medida: sería una opinión. Se comparan las conclusiones y no las huellas: cada
ejecución tiene su propia marca de tiempo y, por lo tanto, su propia huella. Lo
que debe reproducirse es el juicio sobre cada control, no el byte.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_mutacion
from comun.formato import fecha_legible
from cotejo_app.contexto import mensaje_de_error, use_app, use_consola
from cotejo_app.piezas import RESPUESTAS, ConTecnicismo


def _palabra(conclusion: str) -> str:
    return RESPUESTAS.get(conclusion, {}).get("palabra", conclusion)


@ft.component
def VistaComparacion() -> ft.Control:
    app = use_app()
    consola = use_consola()
    ejecuciones = ((consola.ejecuciones.datos if consola.ejecuciones else None) or {}).get("ejecuciones", [])

    a, poner_a = ft.use_state("")
    b, poner_b = ft.use_state("")
    resultado, poner_resultado = ft.use_state(None)
    comparar = use_mutacion(app.api.comparar)

    # Por omisión, las dos más recientes: la penúltima contra la última.
    def proponer():
        if not a and len(ejecuciones) > 1:
            poner_a(ejecuciones[1]["ejecucion_id"])
        if not b and ejecuciones:
            poner_b(ejecuciones[0]["ejecucion_id"])

    ft.use_effect(proponer, [len(ejecuciones)])

    async def ejecutar_comparacion():
        poner_resultado(None)
        try:
            poner_resultado(await comparar.ejecutar(a, b))
        except Exception:  # noqa: BLE001 - se muestra bajo el botón
            pass

    identidad = {e["ejecucion_id"]: e.get("identidad_ejecucion") for e in ejecuciones}
    opciones = [("", "Elige una revisión")] + [
        (e["ejecucion_id"], f"{fecha_legible(e.get('cerrado_en'))} · la ejecutó {e.get('identidad_ejecucion', '')}")
        for e in ejecuciones
    ]

    encabezado = ft.Column(
        [
            ui.Titulo("¿Sale lo mismo si lo repite otra persona?"),
            ConTecnicismo(
                "Debería. Si el resultado dependiera de quién ejecuta el programa, no sería una medida: sería una "
                "opinión. Aquí se comparan dos revisiones y se mira si cada cosa dio la misma respuesta. No se "
                "comparan los sellos, porque cada revisión se hace a una hora distinta y por eso su sello es "
                "distinto; lo que tiene que repetirse es el juicio, no el archivo.",
                "en auditoría: reproducibilidad",
            ),
        ],
        spacing=d.E1,
    )

    if len(ejecuciones) < 2:
        return ft.Column(
            [
                encabezado,
                ui.Tarjeta(
                    ui.Vacio(
                        "Hacen falta dos revisiones para comparar",
                        "Vuelve a «Revisión» y pulsa «Revisar ahora» una segunda vez. Vale mucho más si la segunda "
                        "la ejecuta otra persona del equipo.",
                        ui.Boton("Ir a Revisión", lambda: app.ir("/revision"), variante="secundario"),
                    )
                ),
            ],
            spacing=d.E4,
        )

    cuerpo: list[ft.Control] = [
        ui.Rejilla(
            [
                ft.Row([ui.Selector("Primera revisión", a, opciones, poner_a)]),
                ft.Row([ui.Selector("Segunda revisión", b, opciones, poner_b)]),
            ],
            {"xs": 12, "md": 6},
        )
    ]
    if a and b and identidad.get(a) and identidad.get(a) == identidad.get(b):
        cuerpo.append(
            ui.Aviso(
                "Las dos las ejecutó la misma persona. Comparar sirve igual, pero prueba mucho menos: lo que se "
                "quiere demostrar es que el resultado no depende de quién lo ejecute.",
                tono="alerta",
            )
        )
    cuerpo.append(
        ft.Row(
            [
                ui.Boton(
                    "Comparar las dos",
                    ejecutar_comparacion,
                    cargando=comparar.pendiente,
                    deshabilitado=not a or not b or a == b,
                    icono=ft.Icons.COMPARE_ARROWS,
                )
            ]
        )
    )
    if comparar.error:
        cuerpo.append(ui.Aviso(mensaje_de_error(comparar.error), tono="error"))
    if resultado:
        texto: list[ft.Control] = [
            ui.Texto(f"{resultado['coincidencias']} de {resultado['controles_comparados']} cosas dieron la misma respuesta.")
        ]
        if resultado.get("diferencias"):
            texto.append(
                ui.Texto(
                    "Una diferencia no significa que el programa esté mal: puede que Rastro haya cambiado entre una "
                    "revisión y otra. Hay que abrir las dos pruebas antes de concluir."
                )
            )
            texto += [
                ui.Texto(
                    f"• {x['control_id']}: {_palabra(x['ejecucion_a'])} la primera vez, "
                    f"{_palabra(x['ejecucion_b'])} la segunda"
                )
                for x in resultado["diferencias"]
            ]
        cuerpo.append(
            ui.Aviso(
                texto,
                tono="exito" if resultado.get("reproducible") else "error",
                titulo="Sale lo mismo las dos veces" if resultado.get("reproducible") else "No sale lo mismo",
            )
        )

    return ft.Column([encabezado, ui.Tarjeta(cuerpo)], spacing=d.E4)
