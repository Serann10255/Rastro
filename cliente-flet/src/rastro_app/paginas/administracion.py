"""Administración de la empresa: cuentas, roles y datos de la organización.

Crear usuarios es la operación más sensible del sistema: quien puede crear
cuentas puede concederse cualquier permiso. Por eso está restringida al
administrador y por eso cada alta, cambio de rol y desactivación queda en la
bitácora con quién lo hizo.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_formulario, use_mutacion
from comun.formato import fecha_relativa
from rastro_app.consultas import use_roles, use_usuarios
from rastro_app.contexto import mensaje_de_error, use_app, use_sesion


@ft.component
def Administracion() -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    es_admin = sesion.puede("usuario:crear")
    usuarios = use_usuarios(sesion.puede("usuario:listar"))
    # Los roles salen de la organización: incluyen los que ella haya creado.
    roles = use_roles(sesion.puede("rol:consultar"))
    lista_roles = (roles.datos or {}).get("roles", [])

    busqueda, poner_busqueda = ft.use_state("")
    creando, poner_creando = ft.use_state(False)
    editando, poner_editando = ft.use_state(None)
    por_desactivar, poner_por_desactivar = ft.use_state(None)
    cambiando_clave, poner_cambiando_clave = ft.use_state(False)

    async def actualizar_usuario(correo: str, cambios: dict):
        resultado = await app.api.actualizar_usuario(correo, cambios)
        app.almacen.invalidar("usuarios", "equipo", "tablero")
        return resultado

    actualizar = use_mutacion(actualizar_usuario)

    async def desactivar():
        try:
            await actualizar.ejecutar(por_desactivar["correo"], {"activo": False})
            app.avisar("Cuenta desactivada y sesiones cerradas.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")
        poner_por_desactivar(None)

    async def reactivar(correo: str):
        try:
            await actualizar.ejecutar(correo, {"activo": True})
            app.avisar("Cuenta reactivada.", "exito")
        except Exception as fallo:  # noqa: BLE001
            app.avisar(mensaje_de_error(fallo), "error")

    termino = busqueda.strip().lower()
    visibles = [
        u
        for u in (usuarios.datos or {}).get("usuarios", [])
        if not termino or termino in f"{u['nombre']} {u['correo']} {' '.join(u.get('grupos', []))}".lower()
    ]
    empresa = sesion.empresa or {}

    izquierda: list[ft.Control] = [
        ui.Tarjeta(
            ft.Row(
                [
                    ft.Container(ui.Campo("Buscar", busqueda, poner_busqueda, sugerencia="Nombre, correo o rol"), expand=True),
                    ui.Insignia(f"{(usuarios.datos or {}).get('total', 0)} cuentas"),
                ],
                spacing=d.E3,
            )
        )
    ]
    if usuarios.error:
        izquierda.append(ui.Aviso(mensaje_de_error(usuarios.error), tono="error"))
    if usuarios.cargando:
        izquierda.append(ui.Esqueleto(alto=256))
    elif not visibles:
        izquierda.append(ui.Tarjeta(ui.Vacio("Sin cuentas")))
    else:
        izquierda += [
            TarjetaUsuario(
                u,
                es_propio=u["correo"] == sesion.usuario.get("correo"),
                es_admin=es_admin,
                al_editar=lambda u=u: poner_editando(u),
                al_desactivar=lambda u=u: poner_por_desactivar(u),
                al_reactivar=lambda u=u: reactivar(u["correo"]),
                key=u["correo"],
            )
            for u in visibles
        ]

    derecha: list[ft.Control] = [
        ui.Tarjeta(
            [
                ui.Dato("Razón social", empresa.get("nombre") or "—"),
                ui.Dato("Identificador", empresa.get("org_id") or "—"),
                ui.Dato("NIT", empresa.get("nit") or "—"),
                ui.Dato("Dirección", empresa.get("direccion") or "—"),
                ui.Dato("Ciudad", f"{empresa['ciudad']}, {empresa.get('departamento', '')}" if empresa.get("ciudad") else "—"),
                ui.Dato("Teléfono", empresa.get("telefono") or "—"),
                ui.Dato("Contacto", empresa.get("correo_contacto") or "—"),
                ui.Texto(
                    "Los datos de la empresa se aprovisionan con el despliegue. El registro autónomo de "
                    "organizaciones está fuera del alcance del proyecto.",
                    tono="texto-tenue",
                    tamano=d.T_XS,
                ),
            ],
            titulo="Datos de la empresa",
        ),
        ui.Tarjeta(
            [
                ui.Dato("Nombre", sesion.usuario.get("nombre") or "—"),
                ui.Dato("Roles", ", ".join(sesion.grupos) or "—"),
                ft.Row([ui.Boton("Cambiar contraseña", lambda: poner_cambiando_clave(True), variante="secundario", icono=ft.Icons.KEY)]),
            ],
            titulo="Su cuenta",
            ayuda=sesion.usuario.get("correo"),
        ),
        ui.Tarjeta(
            [
                ft.Column([ui.Insignia(rol["nombre"]), ui.Texto(rol.get("descripcion", ""), tono="texto-suave", tamano=d.T_XS)], spacing=d.E1)
                for rol in lista_roles
            ]
            or ui.Texto("Sin roles que mostrar.", tono="texto-suave"),
            titulo="Qué puede hacer cada rol",
            ayuda="Los roles son de su organización: puede ajustarlos y crear otros.",
            pie=ft.Row([ui.Boton("Configurar roles", lambda: app.ir("/administracion/roles"), variante="secundario")]),
        ),
    ]

    FormularioUsuario(creando, lista_roles, lambda: poner_creando(False))
    FormularioEdicion(editando, lista_roles, lambda: poner_editando(None), actualizar)
    FormularioClave(cambiando_clave, lambda: poner_cambiando_clave(False))
    ui.use_confirmacion(
        por_desactivar is not None,
        "Desactivar cuenta",
        f"{(por_desactivar or {}).get('nombre', '')} no podrá entrar y sus sesiones abiertas se cerrarán de "
        "inmediato. La cuenta y su historial se conservan: desactivar no borra lo que esa persona hizo.",
        "Desactivar",
        desactivar,
        lambda: poner_por_desactivar(None),
        cargando=actualizar.pendiente,
        peligro=True,
    )

    return ft.Column(
        [
            ui.Encabezado(
                "Administración",
                f"Cuentas y roles de {empresa.get('nombre') or 'su empresa'}. Cada alta, cambio de rol y "
                "desactivación queda registrada en la bitácora con quién la hizo.",
                [ui.Boton("Crear usuario", lambda: poner_creando(True), icono=ft.Icons.PERSON_ADD)] if es_admin else None,
            ),
            ui.DoblePanel(izquierda, derecha),
        ],
        spacing=d.E4,
    )


@ft.component
def TarjetaUsuario(usuario: dict, es_propio: bool, es_admin: bool, al_editar, al_desactivar, al_reactivar) -> ft.Control:
    p = ui.paleta()
    activo = usuario.get("activo", True)
    cabecera: list[ft.Control] = [ft.Text(usuario["nombre"], size=d.T_MD, weight=ft.FontWeight.W_700, expand=True)]
    if es_propio:
        cabecera.append(ui.Insignia("usted"))
    cabecera.append(ui.Insignia("activo" if activo else "inactivo", "exito" if activo else "peligro"))
    acciones: list[ft.Control] = []
    if es_admin:
        acciones.append(ui.Boton("Editar", al_editar, variante="sutil", icono=ft.Icons.EDIT))
        if activo and not es_propio:
            acciones.append(ui.Boton("Desactivar", al_desactivar, variante="sutil", icono=ft.Icons.BLOCK))
        if not activo:
            acciones.append(ui.Boton("Reactivar", al_reactivar, variante="sutil", icono=ft.Icons.RESTART_ALT))
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(cabecera, spacing=d.E1, vertical_alignment=ft.CrossAxisAlignment.START),
                ui.Texto(usuario["correo"], tono="texto-tenue", tamano=d.T_XS),
                ft.Row([ui.Insignia(g, "info") for g in usuario.get("grupos", [])], wrap=True, spacing=d.E1, run_spacing=d.E1),
                ui.Texto(
                    " · ".join(
                        x
                        for x in (
                            usuario.get("telefono"),
                            f"último acceso {fecha_relativa(usuario['ultimo_acceso'])}" if usuario.get("ultimo_acceso") else "nunca entró",
                        )
                        if x
                    ),
                    tono="texto-suave",
                    tamano=d.T_XS,
                ),
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


@ft.component
def SelectorDeRoles(seleccionados: list, al_cambiar, disponibles: list) -> ft.Control:
    def alternar(grupo: str, marcado: bool):
        al_cambiar([g for g in seleccionados if g != grupo] + ([grupo] if marcado else []))

    return ft.Column(
        [
            ft.Text("ROLES", size=d.T_XS, weight=ft.FontWeight.W_700, opacity=0.7),
            *[
                ui.Casilla(rol["nombre"], rol["clave"] in seleccionados, lambda v, c=rol["clave"]: alternar(c, v), rol.get("descripcion"))
                for rol in disponibles
            ],
            ft.Text(
                "Una cuenta puede tener varios roles. El servidor concede el permiso si alguno de ellos lo autoriza.",
                size=d.T_XS,
                opacity=0.7,
            ),
        ],
        spacing=d.E1,
    )


def FormularioUsuario(abierto: bool, roles: list, al_cerrar) -> None:
    app = use_app()
    formulario = use_formulario({"nombre": "", "correo": "", "clave": "", "telefono": "", "grupos": ["conductor"]})
    v = formulario.valores
    clave_corta = 0 < len(v["clave"]) < 12

    async def crear_usuario(datos):
        resultado = await app.api.crear_usuario(datos)
        app.almacen.invalidar("usuarios", "equipo", "tablero")
        return resultado

    crear = use_mutacion(crear_usuario)

    async def enviar():
        actual = formulario.actual
        datos = {
            "correo": actual["correo"].strip(),
            "nombre": actual["nombre"].strip(),
            "clave": actual["clave"],
            "grupos": list(actual["grupos"]),
        }
        if actual["telefono"].strip():
            datos["telefono"] = actual["telefono"].strip()
        try:
            await crear.ejecutar(datos)
            app.avisar(f"Cuenta creada para {datos['correo']}.", "exito")
            formulario.reemplazar({"nombre": "", "correo": "", "clave": "", "telefono": "", "grupos": ["conductor"]})
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra dentro del formulario
            pass

    contenido: list[ft.Control] = [
        ui.Campo("Nombre completo", v["nombre"], formulario.poner("nombre")),
        ui.Campo("Correo", v["correo"], formulario.poner("correo"), teclado=ft.KeyboardType.EMAIL, ayuda="Será su nombre de usuario. No distingue mayúsculas."),
        ui.Campo(
            "Contraseña inicial",
            v["clave"],
            formulario.poner("clave"),
            contrasena=True,
            error="Al menos 12 caracteres." if clave_corta else None,
            ayuda="Mínimo 12 caracteres. Se almacena derivada, nunca en claro.",
            autocompletar=ft.AutofillHint.NEW_PASSWORD,
        ),
        ui.Campo("Teléfono", v["telefono"], formulario.poner("telefono"), opcional=True, teclado=ft.KeyboardType.PHONE),
        SelectorDeRoles(v["grupos"], formulario.poner("grupos"), roles),
    ]
    if crear.error:
        contenido.append(ui.Aviso(mensaje_de_error(crear.error), tono="error"))
    ui.use_modal(
        abierto,
        "Crear usuario",
        contenido,
        al_cerrar,
        ayuda="La persona entrará con este correo y esta contraseña, y podrá cambiarla después.",
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario"),
            ui.Boton("Crear cuenta", enviar, cargando=crear.pendiente, deshabilitado=not v["grupos"] or clave_corta or not v["clave"]),
        ],
        bloqueado=crear.pendiente,
    )


def FormularioEdicion(usuario: dict | None, roles: list, al_cerrar, actualizar) -> None:
    app = use_app()
    formulario = use_formulario({"nombre": "", "telefono": "", "grupos": []})
    ultimo, poner_ultimo = ft.use_state(None)
    if usuario is not ultimo:
        poner_ultimo(usuario)
        if usuario is not None:
            formulario.reemplazar(
                {"nombre": usuario["nombre"], "telefono": usuario.get("telefono") or "", "grupos": list(usuario.get("grupos", []))}
            )
    v = formulario.valores

    async def enviar():
        actual = formulario.actual
        try:
            await actualizar.ejecutar(
                usuario["correo"],
                {"nombre": actual["nombre"].strip(), "telefono": actual["telefono"].strip(), "grupos": list(actual["grupos"])},
            )
            app.avisar("Cuenta actualizada.", "exito")
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra dentro del formulario
            pass

    contenido: list[ft.Control] = [
        ui.Campo("Nombre completo", v["nombre"], formulario.poner("nombre")),
        ui.Campo("Teléfono", v["telefono"], formulario.poner("telefono"), opcional=True, teclado=ft.KeyboardType.PHONE),
        SelectorDeRoles(v["grupos"], formulario.poner("grupos"), roles),
        ui.Aviso(
            "El correo no se puede cambiar: es la clave con la que se identifica la cuenta y con la que están "
            "atribuidos sus registros en la bitácora.",
            tono="info",
        ),
    ]
    if actualizar.error:
        contenido.append(ui.Aviso(mensaje_de_error(actualizar.error), tono="error"))
    ui.use_modal(
        usuario is not None,
        "Editar usuario",
        contenido,
        al_cerrar,
        ayuda=(usuario or {}).get("correo"),
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario"),
            ui.Boton("Guardar", enviar, cargando=actualizar.pendiente, deshabilitado=not v["grupos"]),
        ],
        bloqueado=actualizar.pendiente,
    )


def FormularioClave(abierto: bool, al_cerrar) -> None:
    """Cambiar la contraseña cierra las demás sesiones: quien la cambia suele
    hacerlo porque sospecha que alguien más la tiene."""
    app = use_app()
    formulario = use_formulario({"actual": "", "nueva": "", "repetida": ""})
    v = formulario.valores
    no_coinciden = bool(v["repetida"]) and v["nueva"] != v["repetida"]
    corta = 0 < len(v["nueva"]) < 12
    cambiar = use_mutacion(app.api.cambiar_clave)

    async def enviar():
        actual = formulario.actual
        try:
            await cambiar.ejecutar(actual["actual"], actual["nueva"])
            app.avisar("Contraseña cambiada. Las demás sesiones se cerraron.", "exito")
            formulario.reemplazar({"actual": "", "nueva": "", "repetida": ""})
            al_cerrar()
        except Exception:  # noqa: BLE001 - se muestra dentro del formulario
            pass

    contenido: list[ft.Control] = [
        ui.Campo("Contraseña actual", v["actual"], formulario.poner("actual"), contrasena=True, autocompletar=ft.AutofillHint.PASSWORD),
        ui.Campo(
            "Contraseña nueva",
            v["nueva"],
            formulario.poner("nueva"),
            contrasena=True,
            error="Al menos 12 caracteres." if corta else None,
            autocompletar=ft.AutofillHint.NEW_PASSWORD,
        ),
        ui.Campo(
            "Repita la nueva",
            v["repetida"],
            formulario.poner("repetida"),
            contrasena=True,
            error="Las contraseñas no coinciden." if no_coinciden else None,
        ),
    ]
    if cambiar.error:
        contenido.append(ui.Aviso(mensaje_de_error(cambiar.error), tono="error"))
    ui.use_modal(
        abierto,
        "Cambiar contraseña",
        contenido,
        al_cerrar,
        ayuda="Al cambiarla se cerrarán sus demás sesiones. Si la cambia porque sospecha que alguien la conoce, "
        "dejar esas sesiones abiertas no serviría de nada.",
        acciones=[
            ui.Boton("Cancelar", al_cerrar, variante="secundario"),
            ui.Boton("Cambiar", enviar, cargando=cambiar.pendiente, deshabilitado=no_coinciden or corta or not v["nueva"]),
        ],
        bloqueado=cambiar.pendiente,
    )
