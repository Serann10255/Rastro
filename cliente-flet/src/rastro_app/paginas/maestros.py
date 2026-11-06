"""Datos maestros: tiendas, clientes y transportistas.

Los tres recursos comparten estructura porque comparten necesidad: listar,
buscar, crear, editar y dar de baja. Aquí son una sola pantalla con la
descripción de cada recurso; escribirla tres veces produciría tres
comportamientos ligeramente distintos.

Lectura y escritura tienen permisos distintos: el despachador consulta las
tiendas para registrar un envío, pero cambiar la dirección de una tienda afecta
a toda la operación y corresponde al administrador. **Eliminar es desactivar**:
los envíos históricos apuntan a estos registros.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_formulario, use_mutacion
from rastro_app.consultas import use_maestro
from rastro_app.contexto import mensaje_de_error, use_app, use_sesion


@dataclass(frozen=True)
class CampoMaestro:
    clave: str
    etiqueta: str
    obligatorio: bool = False
    opciones: tuple[tuple[str, str], ...] = ()
    ayuda: str | None = None
    teclado: ft.KeyboardType | None = None


@dataclass(frozen=True)
class Recurso:
    clave: str
    titulo: str
    singular: str
    femenino: bool
    descripcion: str
    texto_crear: str
    identificador: str
    activo: str
    campos: tuple[CampoMaestro, ...]
    al_eliminar: str
    vacio: str


RECURSOS = {
    "tiendas": Recurso(
        clave="tiendas",
        titulo="Tiendas",
        singular="tienda",
        femenino=True,
        descripcion="Tiendas, almacenes y estaciones desde donde sale y por donde pasa la carga.",
        texto_crear="Agregar tienda",
        identificador="tienda_id",
        activo="activa",
        campos=(
            CampoMaestro("nombre", "Nombre", obligatorio=True),
            CampoMaestro("codigo", "Código", ayuda="Se guarda en mayúsculas. Si se deja vacío, se usa el nombre."),
            CampoMaestro("tipo", "Tipo", opciones=(("tienda", "Tienda"), ("almacen", "Almacén"), ("estacion", "Estación"))),
            CampoMaestro("direccion", "Dirección"),
            CampoMaestro("ciudad", "Ciudad", obligatorio=True),
            CampoMaestro("departamento", "Departamento", obligatorio=True),
            CampoMaestro("telefono", "Teléfono", teclado=ft.KeyboardType.PHONE),
            CampoMaestro("responsable", "Responsable"),
        ),
        al_eliminar="Los envíos ya registrados conservan el nombre de la tienda tal como estaba: no pierden su origen.",
        vacio="Agregue la primera para poder asociarla a los envíos.",
    ),
    "clientes": Recurso(
        clave="clientes",
        titulo="Clientes",
        singular="cliente",
        femenino=False,
        descripcion="Empresas y personas que despachan envíos a través de su operación.",
        texto_crear="Agregar cliente",
        identificador="cliente_id",
        activo="activo",
        campos=(
            CampoMaestro("nombre", "Nombre o razón social", obligatorio=True),
            CampoMaestro("documento", "Documento o NIT"),
            CampoMaestro("telefono", "Teléfono", teclado=ft.KeyboardType.PHONE),
            CampoMaestro("correo", "Correo", teclado=ft.KeyboardType.EMAIL),
            CampoMaestro("direccion", "Dirección"),
            CampoMaestro("ciudad", "Ciudad"),
            CampoMaestro("departamento", "Departamento"),
        ),
        al_eliminar="Los envíos ya registrados conservan su nombre: no pierden a quién pertenecían.",
        vacio="Agregue el primero para asociarlo a los envíos.",
    ),
    "transportistas": Recurso(
        clave="transportistas",
        titulo="Transportistas",
        singular="transportista",
        femenino=False,
        descripcion="Flota propia y terceros que mueven la carga. Distinguirlos importa: la responsabilidad "
        "ante el cliente no se subcontrata.",
        texto_crear="Agregar transportista",
        identificador="transportista_id",
        activo="activo",
        campos=(
            CampoMaestro("nombre", "Nombre", obligatorio=True),
            CampoMaestro("tipo", "Tipo", opciones=(("propio", "Flota propia"), ("tercero", "Tercero"))),
            CampoMaestro("nit", "NIT"),
            CampoMaestro("correo", "Correo", teclado=ft.KeyboardType.EMAIL),
            CampoMaestro("telefono", "Teléfono", teclado=ft.KeyboardType.PHONE),
            CampoMaestro("ciudad", "Ciudad"),
            CampoMaestro("departamento", "Departamento"),
        ),
        al_eliminar="Los envíos ya registrados conservan su nombre.",
        vacio="Agregue el primero para asociarlo a los envíos.",
    ),
}


def _vacio(recurso: Recurso) -> dict:
    datos = {campo.clave: (campo.opciones[0][0] if campo.opciones else "") for campo in recurso.campos}
    if recurso.clave == "transportistas":
        datos["tipo"] = "tercero"
    return datos


@ft.component
def Maestros() -> ft.Control:
    clave = ft.use_route_params().get("recurso", "tiendas")
    recurso = RECURSOS.get(clave, RECURSOS["tiendas"])
    return PantallaMaestro(recurso, key=recurso.clave)


@ft.component
def PantallaMaestro(recurso: Recurso) -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    consulta = use_maestro(recurso.clave)
    busqueda, poner_busqueda = ft.use_state("")
    editando, poner_editando = ft.use_state(None)
    por_eliminar, poner_por_eliminar = ft.use_state(None)
    puede_editar = sesion.puede("maestro:editar")

    async def eliminar_registro():
        await app.api.eliminar_maestro(recurso.clave, por_eliminar[recurso.identificador])
        app.almacen.invalidar(recurso.clave)

    eliminar = use_mutacion(eliminar_registro)

    async def confirmar_eliminacion():
        try:
            await eliminar.ejecutar()
            app.avisar(f"{recurso.singular.capitalize()} eliminad{'a' if recurso.femenino else 'o'}.", "exito")
            poner_por_eliminar(None)
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")

    termino = busqueda.strip().lower()
    registros = [
        r
        for r in (consulta.datos or {}).get(recurso.clave, [])
        if not termino or termino in " ".join(str(v) for v in r.values() if isinstance(v, str)).lower()
    ]

    partes: list[ft.Control] = [
        ui.Encabezado(
            recurso.titulo,
            recurso.descripcion,
            [ui.Boton(recurso.texto_crear, lambda: poner_editando(_vacio(recurso)), icono=ft.Icons.ADD)] if puede_editar else None,
        ),
        ui.Tarjeta(
            ft.Row(
                [
                    ft.Container(ui.Campo("Buscar", busqueda, poner_busqueda, sugerencia="Nombre, ciudad o código"), expand=True),
                    ui.Insignia(f"{(consulta.datos or {}).get('total', 0)} registros"),
                ],
                spacing=d.E3,
            )
        ),
    ]
    if consulta.error:
        partes.append(ui.Aviso(mensaje_de_error(consulta.error), tono="error"))
    if consulta.cargando:
        partes.append(ui.Esqueleto(alto=256))
    elif not registros:
        partes.append(
            ui.Tarjeta(
                ui.Vacio(
                    f"Ningun{'a' if recurso.femenino else ''} {recurso.singular} coincide" if busqueda else f"Sin {recurso.clave}",
                    "Pruebe con otro término." if busqueda else recurso.vacio,
                )
            )
        )
    else:
        partes.append(
            ui.Rejilla(
                [
                    TarjetaRegistro(
                        recurso,
                        r,
                        (lambda r=r: poner_editando(dict(r))) if puede_editar else None,
                        (lambda r=r: poner_por_eliminar(r)) if puede_editar else None,
                        key=r[recurso.identificador],
                    )
                    for r in registros
                ],
                {"xs": 12, "md": 6, "xl": 4},
            )
        )

    FormularioMaestro(recurso, editando, lambda: poner_editando(None))
    ui.use_confirmacion(
        por_eliminar is not None,
        f"Eliminar {recurso.singular}",
        f"Se eliminará {por_eliminar['nombre'] if por_eliminar else ''}. {recurso.al_eliminar}",
        "Eliminar",
        confirmar_eliminacion,
        lambda: poner_por_eliminar(None),
        cargando=eliminar.pendiente,
        peligro=True,
    )
    return ft.Column(partes, spacing=d.E4)


@ft.component
def TarjetaRegistro(recurso: Recurso, registro: dict, al_editar, al_eliminar) -> ft.Control:
    p = ui.paleta()
    activo = bool(registro.get(recurso.activo, True))
    detalles = [
        f"{campo.etiqueta}: {dict(campo.opciones).get(registro.get(campo.clave), registro.get(campo.clave))}"
        for campo in recurso.campos[1:]
        if registro.get(campo.clave)
    ]
    acciones: list[ft.Control] = []
    if al_editar:
        acciones.append(ui.Boton("Editar", al_editar, variante="sutil", icono=ft.Icons.EDIT))
    if al_eliminar and activo:
        acciones.append(ui.Boton("Eliminar", al_eliminar, variante="sutil", icono=ft.Icons.DELETE_OUTLINE))
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(registro.get("nombre", ""), size=d.T_MD, weight=ft.FontWeight.W_700, expand=True),
                        ui.Insignia("activo" if activo else "inactivo", "exito" if activo else "peligro"),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                *[ft.Text(linea, size=d.T_SM, color=p["texto-suave"], selectable=True) for linea in detalles],
                *([ft.Row(acciones, wrap=True, spacing=d.E1)] if acciones else []),
            ],
            spacing=d.E1,
        ),
        padding=d.E4,
        bgcolor=p["superficie"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_LG,
        opacity=1 if activo else 0.7,
    )


def FormularioMaestro(recurso: Recurso, inicial: dict | None, al_cerrar) -> None:
    """El formulario de alta o edición, en un diálogo. Es un hook: se llama en
    cada render, abierto o no."""
    app = use_app()
    formulario = use_formulario(inicial or _vacio(recurso))
    errores, poner_errores = ft.use_state({})
    ultima, poner_ultima = ft.use_state(None)

    # Al abrir el diálogo con otro registro, el formulario toma sus datos.
    if inicial is not ultima:
        poner_ultima(inicial)
        if inicial is not None:
            formulario.reemplazar({**_vacio(recurso), **{k: v for k, v in inicial.items() if v is not None}})
            poner_errores({})

    async def guardar_registro(datos, identificador):
        resultado = await app.api.guardar_maestro(recurso.clave, identificador, datos)
        app.almacen.invalidar(recurso.clave)
        return resultado

    guardar = use_mutacion(guardar_registro)

    async def enviar():
        actual = formulario.actual
        nuevos = {
            campo.clave: "Obligatorio, al menos 2 caracteres."
            for campo in recurso.campos
            if campo.obligatorio and len(str(actual.get(campo.clave, "")).strip()) < 2
        }
        poner_errores(nuevos)
        if nuevos:
            return
        identificador = (inicial or {}).get(recurso.identificador)
        datos = {campo.clave: str(actual.get(campo.clave, "")).strip() for campo in recurso.campos}
        try:
            await guardar.ejecutar(datos, identificador)
            accion = "actualizad" if identificador else "cread"
            app.avisar(f"{recurso.singular.capitalize()} {accion}{'a' if recurso.femenino else 'o'}.", "exito")
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra dentro del formulario
            pass

    controles: list[ft.Control] = []
    for campo in recurso.campos:
        if campo.opciones:
            controles.append(ui.Selector(campo.etiqueta, formulario.valores.get(campo.clave, ""), campo.opciones, formulario.poner(campo.clave)))
        else:
            controles.append(
                ui.Campo(
                    campo.etiqueta,
                    str(formulario.valores.get(campo.clave, "") or ""),
                    formulario.poner(campo.clave),
                    ayuda=campo.ayuda,
                    error=errores.get(campo.clave),
                    opcional=not campo.obligatorio,
                    teclado=campo.teclado,
                )
            )
    if guardar.error:
        controles.append(ui.Aviso(mensaje_de_error(guardar.error), tono="error"))
    editar = bool((inicial or {}).get(recurso.identificador))
    ui.use_modal(
        inicial is not None,
        f"{'Editar' if editar else 'Nuev' + ('a' if recurso.femenino else 'o')} {recurso.singular}",
        controles,
        al_cerrar,
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario"),
            ui.Boton("Guardar", enviar, cargando=guardar.pendiente),
        ],
        bloqueado=guardar.pendiente,
    )
