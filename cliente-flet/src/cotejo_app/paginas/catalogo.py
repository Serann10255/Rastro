"""Qué se revisa: el catálogo de controles, antes de ejecutar nada.

El criterio se muestra tal como está declarado en el catálogo, **antes** de
ejecutar: es lo que impide acomodarlo al resultado.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from comun import diseno as d
from comun import ui
from cotejo_app.contexto import mensaje_de_error, use_consola
from cotejo_app.piezas import SEVERIDADES, CampoHallazgo, ConTecnicismo, DetalleTecnico, EtiquetaSeveridad, colores_de_ficha

GRUPOS = [
    (
        "cumplimiento",
        "Se mira cómo está puesto",
        "Comprobar la configuración sin tocar nada. Como revisar que la puerta tenga cerradura.",
        "pruebas de cumplimiento",
    ),
    (
        "sustantiva",
        "Se usa el sistema de verdad",
        "Empujar la puerta para ver si de verdad está cerrada. Esto no lo hace ninguna herramienta automática "
        "de la nube: estas reglas viven en el código, no en la configuración.",
        "pruebas sustantivas",
    ),
    (
        "integridad",
        "Se comprueba que el historial no se pueda retocar",
        "Recalcular la cadena de sellos del cuaderno de Rastro.",
        "prueba de integridad",
    ),
]


@ft.component
def Ficha(severidad: str, contenido: list[ft.Control]) -> ft.Control:
    """Un control o un hallazgo, con el borde del color de su severidad."""
    p = ui.paleta()
    color, _, _ = colores_de_ficha(p, SEVERIDADES.get(severidad, ("", "texto-suave"))[1])
    return ft.Container(
        content=ft.Column(contenido, spacing=d.E2),
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


def _cabecera(identificador: str, severidad: str) -> ft.Control:
    return ft.Row(
        [
            ft.Text(identificador, size=d.T_SM, weight=ft.FontWeight.W_700, font_family=d.FUENTE_MONO),
            EtiquetaSeveridad(severidad, solo_dos=True),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        wrap=True,
        run_spacing=d.E1,
    )


@ft.component
def FichaControl(control: dict[str, Any]) -> ft.Control:
    p = ui.paleta()
    severidad = control.get("severidad_si_desviado", "media")
    return Ficha(
        severidad,
        [
            _cabecera(control["id"], severidad),
            ft.Text(control.get("pregunta", ""), size=d.T_MD, weight=ft.FontWeight.W_600, selectable=True),
            ui.Texto(control.get("en_simple", ""), tono="texto-suave"),
            ft.Text(
                spans=[ft.TextSpan("Si fallara: ", ft.TextStyle(weight=ft.FontWeight.W_700)), ft.TextSpan(control.get("si_falla", ""))],
                size=d.T_SM,
                color=p["texto"],
                selectable=True,
            ),
            DetalleTecnico(
                [
                    CampoHallazgo("Control", control.get("control")),
                    CampoHallazgo("Marco de referencia", control.get("marco")),
                    CampoHallazgo("Criterio de aceptación", control.get("criterio")),
                    CampoHallazgo("Procedimiento", control.get("procedimiento")),
                    CampoHallazgo("Evidencia esperada", control.get("evidencia_esperada")),
                ]
            ),
        ],
    )


@ft.component
def FichaHallazgoPermanente(hallazgo: dict[str, Any]) -> ft.Control:
    severidad = hallazgo.get("severidad", "media")
    return Ficha(
        severidad,
        [
            _cabecera(hallazgo["id"], severidad),
            ft.Text(hallazgo.get("en_simple", ""), size=d.T_MD, selectable=True),
            CampoHallazgo("Qué habría que hacer", hallazgo.get("recomendacion")),
            DetalleTecnico(
                [
                    CampoHallazgo("Condición", hallazgo.get("condicion")),
                    CampoHallazgo("Criterio", hallazgo.get("criterio")),
                    CampoHallazgo("Causa", hallazgo.get("causa")),
                    CampoHallazgo("Efecto", hallazgo.get("efecto")),
                    CampoHallazgo("Nota de alcance", hallazgo.get("nota_de_alcance")),
                ]
            ),
        ],
    )


@ft.component
def VistaCatalogo() -> ft.Control:
    consola = use_consola()
    consulta = consola.catalogo
    if consulta is None or (consulta.cargando and not consulta.datos):
        return ui.Esqueleto(alto=320)
    if consulta.error and not consulta.datos:
        return ui.Aviso(mensaje_de_error(consulta.error), tono="error")
    catalogo = consulta.datos or {}

    partes: list[ft.Control] = [
        ft.Column(
            [
                ui.Titulo("Qué se revisa"),
                ConTecnicismo(
                    "Esta lista se escribe antes de revisar nada, y las reglas salen de listas de buenas prácticas "
                    "que ya existen y usa medio mundo, no de lo que a este equipo le parezca. Así, si algo no está "
                    "en la lista, es porque se decidió dejarlo fuera y no porque se olvidara.",
                    f"en auditoría: matriz de controles, versión {catalogo.get('version', '')}",
                ),
            ],
            spacing=d.E1,
        )
    ]

    for tipo, titulo, ayuda, tecnico in GRUPOS:
        controles = [c for c in catalogo.get("controles", []) if c.get("tipo") == tipo]
        if not controles:
            continue
        partes.append(
            ui.Tarjeta(
                [FichaControl(c, key=c["id"]) for c in controles],
                titulo=titulo,
                ayuda=f"{ayuda} · en auditoría: {tecnico}",
                acciones=[ui.Insignia(str(len(controles)))],
            )
        )

    partes.append(
        ui.Tarjeta(
            [FichaHallazgoPermanente(h, key=h["id"]) for h in catalogo.get("hallazgos_permanentes", [])],
            titulo="Cosas que ya sabemos que están mal",
            ayuda="Y que aquí no se pueden arreglar, porque el laboratorio de clase no lo permite. No se prueban "
            "—una prueba que siempre da el mismo resultado no aporta nada— pero se escriben en todos los "
            "informes: quitarlas haría creer que se revisó más de lo que se revisó. · en auditoría: hallazgos "
            "permanentes",
        )
    )
    return ft.Column(partes, spacing=d.E4)
