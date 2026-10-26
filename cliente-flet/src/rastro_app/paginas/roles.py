"""Roles y permisos de la organización.

Es la pantalla más delicada del sistema: aquí se decide quién puede hacer qué.
Tres cosas la hacen manejable sin volverla peligrosa:

- **El catálogo de operaciones lo pone el servidor**, agrupado y con una
  descripción por operación. Marcar casillas llamadas `evento:reanudar` sin
  saber qué significan es firmar sin leer.
- **Lo que esta pantalla impide no es el control.** El servidor rechaza igual un
  permiso inventado, uno que quien edita no tiene, y cualquier rol que mezcle
  auditar con operar. Aquí solo se avisa antes, para no hacer perder el viaje.
- **El administrador no se edita**: es el seguro contra que una organización se
  quede sin nadie que pueda entrar a deshacer un cambio.
"""

from __future__ import annotations

import re

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_formulario, use_mutacion
from rastro_app.consultas import use_catalogo_de_operaciones, use_roles
from rastro_app.contexto import mensaje_de_error, use_app, use_sesion

# El área cuya lectura, combinada con cualquier escritura, rompe la separación
# de funciones. El servidor lo rechaza; esto lo anticipa.
ESCRITURA_Y_AUDITORIA = "auditoria"


@ft.component
def Roles() -> ft.Control:
    sesion = use_sesion()
    roles = use_roles()
    catalogo = use_catalogo_de_operaciones()
    editando, poner_editando = ft.use_state(None)
    creando, poner_creando = ft.use_state(False)
    puede_editar = sesion.puede("rol:administrar")
    areas = (catalogo.datos or {}).get("areas", [])

    def cerrar():
        poner_creando(False)
        poner_editando(None)

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Roles y permisos",
            "Qué puede hacer cada rol de su organización. Los de fábrica se pueden ajustar y no se pueden "
            "eliminar; puede crear los suyos para repartir el trabajo como lo reparte de verdad.",
            [ui.Boton("Crear rol", lambda: poner_creando(True), icono=ft.Icons.ADD)] if puede_editar else None,
        ),
        ui.Aviso(
            "Un rol solo puede contener operaciones que el sistema ya sabe hacer, y nadie puede conceder un "
            "permiso que no tiene. Además, ningún rol —ni ninguna cuenta— puede a la vez operar y leer la "
            "bitácora: quien revisa el registro no puede ser quien lo produce.",
            tono="info",
            titulo="Dos reglas que ninguna pantalla puede desactivar",
        ),
    ]
    if roles.error:
        partes.append(ui.Aviso(mensaje_de_error(roles.error), tono="error"))
    if roles.cargando:
        partes.append(ui.Esqueleto(alto=288))
    else:
        partes.append(
            ui.Rejilla(
                [
                    TarjetaRol(rol, areas, puede_editar, lambda rol=rol: poner_editando(rol), key=rol["clave"])
                    for rol in (roles.datos or {}).get("roles", [])
                ],
                {"xs": 12, "md": 6},
            )
        )

    FormularioRol(creando or editando is not None, editando, areas, cerrar)
    return ft.Column(partes, spacing=d.E4)


@ft.component
def TarjetaRol(rol: dict, areas: list, puede_editar: bool, al_editar) -> ft.Control:
    app = use_app()

    async def eliminar_rol():
        await app.api.eliminar_rol(rol["clave"])
        app.almacen.invalidar("roles")

    eliminar = use_mutacion(eliminar_rol)

    async def confirmar_eliminacion():
        try:
            await eliminar.ejecutar()
            app.avisar(f"Rol «{rol['nombre']}» eliminado.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")

    concedidas = set(rol.get("operaciones") or [])
    por_area = [
        (area["nombre"], sum(1 for o in area["operaciones"] if o["operacion"] in concedidas), len(area["operaciones"]))
        for area in areas
    ]
    insignias = [ui.Insignia(rol["clave"], "info")]
    if rol.get("integrado"):
        insignias.append(ui.Insignia("de fábrica"))
    if not rol.get("editable", True):
        insignias.append(ui.Insignia("no editable", "peligro"))

    cuentas = rol.get("cuentas") or 0
    acciones: list[ft.Control] = []
    if puede_editar and rol.get("editable", True):
        acciones.append(ui.Boton("Editar permisos", al_editar, variante="secundario"))
    if puede_editar and not rol.get("integrado"):
        acciones.append(ui.Boton("Eliminar", confirmar_eliminacion, variante="peligro", cargando=eliminar.pendiente))

    contenido: list[ft.Control] = [
        ft.Row(insignias, wrap=True, spacing=d.E1, run_spacing=d.E1),
        *[
            ft.Row([ui.Texto(nombre, tono="texto-suave"), ui.Texto(f"{cuantas}/{total}", tamano=d.T_XS, mono=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            for nombre, cuantas, total in por_area
            if cuantas
        ],
    ]
    if not rol.get("editable", True):
        contenido.append(
            ui.Texto(
                "El administrador tiene todas las operaciones salvo la bitácora, y no se puede recortar: es lo "
                "que garantiza que la organización nunca se quede sin nadie que pueda entrar.",
                tono="texto-tenue",
                tamano=d.T_XS,
            )
        )
    return ui.Tarjeta(
        contenido,
        titulo=rol["nombre"],
        ayuda=rol.get("descripcion"),
        pie=ft.Column(
            [
                ui.Texto("Sin cuentas asignadas" if cuentas == 0 else f"{cuentas} cuenta{'' if cuentas == 1 else 's'}", tono="texto-tenue", tamano=d.T_XS),
                *([ft.Row(acciones, wrap=True, spacing=d.E2)] if acciones else []),
            ],
            spacing=d.E2,
        ),
    )


def FormularioRol(abierto: bool, rol: dict | None, areas: list, al_cerrar) -> None:
    app = use_app()
    formulario = use_formulario({"clave": "", "nombre": "", "descripcion": "", "operaciones": frozenset()})
    ultimo, poner_ultimo = ft.use_state(("cerrado", None))
    marca = ("abierto" if abierto else "cerrado", rol)
    if marca[0] != ultimo[0] or marca[1] is not ultimo[1]:
        poner_ultimo(marca)
        if abierto:
            formulario.reemplazar(
                {
                    "clave": (rol or {}).get("clave", ""),
                    "nombre": (rol or {}).get("nombre", ""),
                    "descripcion": (rol or {}).get("descripcion", ""),
                    "operaciones": frozenset((rol or {}).get("operaciones") or []),
                }
            )
    v = formulario.valores
    operaciones = v["operaciones"]

    def alternar(operacion: str, marcada: bool):
        actuales = formulario.actual["operaciones"]
        formulario.poner("operaciones")(actuales | {operacion} if marcada else actuales - {operacion})

    # Se avisa antes de enviar por cortesía; el servidor lo rechaza igual.
    auditoria = next((a for a in areas if a["area"] == ESCRITURA_Y_AUDITORIA), {"operaciones": []})
    lee_bitacora = any(o["operacion"] in operaciones for o in auditoria["operaciones"])
    escribe = any(o.get("escritura") and o["operacion"] in operaciones for a in areas for o in a["operaciones"])
    separacion_rota = lee_bitacora and escribe

    async def guardar_rol():
        actual = formulario.actual
        datos = {
            "nombre": actual["nombre"].strip(),
            "descripcion": actual["descripcion"].strip(),
            "operaciones": sorted(actual["operaciones"]),
        }
        if rol is None:
            clave = re.sub(r"\s+", "-", actual["clave"].strip().lower())
            resultado = await app.api.crear_rol({"clave": clave, **datos})
        else:
            resultado = await app.api.actualizar_rol(rol["clave"], datos)
        # Cambiar permisos cambia lo que las cuentas pueden ver.
        app.almacen.invalidar("roles", "usuarios")
        return resultado

    guardar = use_mutacion(guardar_rol)

    async def enviar():
        try:
            await guardar.ejecutar()
            app.avisar("Permisos actualizados." if rol else "Rol creado.", "exito")
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra bajo el formulario
            pass

    contenido: list[ft.Control] = []
    if rol is None:
        contenido.append(
            ui.Campo(
                "Clave",
                v["clave"],
                formulario.poner("clave"),
                sugerencia="supervisor-turno",
                ayuda="Es lo que guardan las cuentas y no se puede cambiar después. Minúsculas y guiones.",
            )
        )
    contenido += [
        ui.Campo("Nombre", v["nombre"], formulario.poner("nombre"), sugerencia="Supervisor de turno"),
        ui.Campo("Descripción", v["descripcion"], formulario.poner("descripcion"), ayuda="Para qué existe este rol. Lo lee quien asigna cuentas."),
    ]
    if separacion_rota:
        contenido.append(
            ui.Aviso(
                "Un rol no puede leer la bitácora y además operar sobre el sistema: quien revisa el registro no "
                "puede ser quien lo produce. Separe las dos cosas en roles distintos.",
                tono="alerta",
                titulo="Esto no se va a poder guardar",
            )
        )
    for area in areas:
        contenido.append(ft.Text(area["nombre"].upper(), size=d.T_XS, weight=ft.FontWeight.W_700, opacity=0.7))
        for operacion in area["operaciones"]:
            contenido.append(
                ui.Casilla(
                    operacion["descripcion"] + ("  ·  escribe" if operacion.get("escritura") else ""),
                    operacion["operacion"] in operaciones,
                    lambda marcada, o=operacion["operacion"]: alternar(o, marcada),
                    operacion["operacion"],
                )
            )
    if not operaciones:
        contenido.append(ui.Vacio("Sin permisos seleccionados", "Un rol sin operaciones no deja hacer nada: desactive las cuentas en su lugar."))
    if guardar.error:
        contenido.append(ui.Aviso(mensaje_de_error(guardar.error), tono="error"))

    ui.use_modal(
        abierto,
        f"Permisos de {rol['nombre']}" if rol else "Crear rol",
        contenido,
        al_cerrar,
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario"),
            ui.Boton(
                "Guardar permisos" if rol else "Crear rol",
                enviar,
                cargando=guardar.pendiente,
                deshabilitado=not operaciones or not v["nombre"].strip() or (rol is None and not v["clave"].strip()),
            ),
        ],
        ancho=640,
        bloqueado=guardar.pendiente,
    )
