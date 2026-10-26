"""Acceso del auditor.

Sin cuenta prefijada: escribir un correo válido en el formulario es publicar una
cuenta que existe. Las credenciales están en la documentación de despliegue.

Como en Rastro, el panel «Conexión» es lo que la web no necesita: una aplicación
instalada no tiene un `configuracion.json` junto al sitio, y aquí se le dicen
las dos direcciones —la de Cotejo y la de Rastro— sin reconstruirla (REQ-09).
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_formulario
from comun.http import ErrorApi, enviar
from comun.marca import LogotipoCotejo
from cotejo_app.claves import CLAVE_URL_COTEJO, CLAVE_URL_RASTRO
from cotejo_app.contexto import mensaje_de_error, use_ancho, use_app, use_sesion
from cotejo_app.estructura import SelectorTema


async def _comprobar(url: str, ruta: str, nombre: str) -> None:
    if not url.startswith(("http://", "https://")):
        raise ErrorApi(0, "SOLICITUD_INVALIDA", f"La dirección de {nombre} debe empezar por https:// (o http:// en la red local).")
    respuesta = await enviar("GET", f"{url}{ruta}")
    if not respuesta.is_success:
        raise ErrorApi(respuesta.status_code, "ERROR", f"{nombre} respondió con código {respuesta.status_code}.")


@ft.component
def PanelConexion() -> ft.Control:
    app = use_app()
    abierto, poner_abierto = ft.use_state(False)
    formulario = use_formulario(
        {"cotejo": app.configuracion.get("url_cotejo", ""), "rastro": app.configuracion.get("url_rastro", "")}
    )
    resultado, poner_resultado = ft.use_state(None)
    probando, poner_probando = ft.use_state(False)

    async def probar_y_guardar():
        cotejo = formulario.actual["cotejo"].strip().rstrip("/")
        rastro = formulario.actual["rastro"].strip().rstrip("/")
        poner_probando(True)
        try:
            await _comprobar(cotejo, "/salud", "Cotejo")
            await _comprobar(rastro, "/catalogos/estados", "Rastro")
            await app.preferencias.set(CLAVE_URL_COTEJO, cotejo)
            await app.preferencias.set(CLAVE_URL_RASTRO, rastro)
            app.api.configuracion = {**app.configuracion, "url_cotejo": cotejo, "url_rastro": rastro}
            app.origen_configuracion = "direcciones fijadas en este dispositivo"
            app.almacen.invalidar("salud")
            poner_resultado(("exito", "Conectado. Las direcciones quedan guardadas en este dispositivo."))
        except ErrorApi as error:
            poner_resultado(("error", f"No respondió como se esperaba: {error.mensaje}"))
        finally:
            poner_probando(False)

    async def olvidar():
        await app.preferencias.remove(CLAVE_URL_COTEJO)
        await app.preferencias.remove(CLAVE_URL_RASTRO)
        poner_resultado(("info", "La próxima vez que abra la aplicación se usarán las direcciones de su configuración."))

    if not abierto:
        return ft.TextButton(
            f"Conexión: {app.configuracion.get('url_cotejo') or 'mismo origen'}",
            icon=ft.Icons.SETTINGS_ETHERNET,
            on_click=lambda: poner_abierto(True),
        )

    return ui.Tarjeta(
        [
            ui.Campo(
                "Dirección de Cotejo",
                formulario.valores["cotejo"],
                formulario.poner("cotejo"),
                ayuda="La de `url_cotejo` del despliegue.",
                teclado=ft.KeyboardType.URL,
            ),
            ui.Campo(
                "Dirección de Rastro",
                formulario.valores["rastro"],
                formulario.poner("rastro"),
                ayuda="La de `url_rastro`: ahí se entra, porque el auditor es un usuario de Rastro.",
                teclado=ft.KeyboardType.URL,
            ),
            *([ui.Aviso(resultado[1], tono=resultado[0])] if resultado else []),
            ft.Row(
                [
                    ui.Boton("Probar y guardar", probar_y_guardar, cargando=probando),
                    ui.Boton("Usar las empaquetadas", olvidar, variante="sutil"),
                    ui.Boton("Cerrar", lambda: poner_abierto(False), variante="sutil"),
                ],
                wrap=True,
            ),
        ],
        titulo="Conexión",
        ayuda=f"Ahora: {app.origen_configuracion}. Trasladar el sistema a otra cuenta no exige reinstalar la aplicación.",
    )


@ft.component
def Acceso() -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    ancho = use_ancho()
    p = ui.paleta()
    formulario = use_formulario({"correo": "", "clave": ""})
    error, poner_error = ft.use_state(None)
    enviando, poner_enviando = ft.use_state(False)
    salud = use_consulta(app.almacen, ("salud",), app.api.salud)

    def ya_dentro():
        if sesion.autenticado:
            app.ir("/revision", reemplazar=True)

    ft.use_effect(ya_dentro, [sesion.autenticado])

    async def entrar():
        correo, clave = formulario.actual["correo"], formulario.actual["clave"]
        if not correo.strip() or not clave:
            poner_error("Escriba el correo y la clave.")
            return
        poner_error(None)
        poner_enviando(True)
        try:
            await sesion.entrar(correo, clave)
        except PermissionError as fallo:
            poner_error(str(fallo))
        except Exception as fallo:  # noqa: BLE001 - se muestra bajo el formulario
            poner_error(mensaje_de_error(fallo) or "No fue posible entrar.")
        finally:
            poner_enviando(False)

    datos_salud = salud.datos or {}
    if salud.datos:
        pie = ft.Text(
            spans=[
                ft.TextSpan("Ahora mismo revisa el sistema que está en "),
                ft.TextSpan(str(datos_salud.get("url_auditada", "")), ft.TextStyle(weight=ft.FontWeight.W_700)),
                ft.TextSpan(f" ({datos_salud.get('entorno', '')}), y tiene "),
                ft.TextSpan(str(datos_salud.get("controles_en_catalogo", "")), ft.TextStyle(weight=ft.FontWeight.W_700)),
                ft.TextSpan(" cosas por comprobar."),
            ],
            size=d.T_XS,
            color=p["texto-tenue"],
        )
    elif salud.error:
        pie = ui.Texto("El programa no responde. Comprueba que el servicio esté encendido.", tono="texto-tenue", tamano=d.T_XS)
    else:
        pie = ui.Texto("Mirando si el programa está encendido…", tono="texto-tenue", tamano=d.T_XS)

    contenido = ft.Column(
        [
            ft.Row(
                [
                    LogotipoCotejo(40),
                    ft.Column(
                        [
                            ft.Text("Cotejo", size=d.T_2XL, weight=ft.FontWeight.W_800),
                            ft.Text("Comprueba si Rastro cumple lo que promete", size=d.T_SM, color=p["texto-suave"]),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    SelectorTema(),
                ],
                spacing=d.E3,
            ),
            *([ui.Tarjeta(ui.Texto(datos_salud["que_es_esto"], tamano=d.T_SM))] if datos_salud.get("que_es_esto") else []),
            ui.Tarjeta(
                [
                    *([ui.Aviso(sesion.motivo_de_salida, tono="alerta")] if sesion.motivo_de_salida and not error else []),
                    ui.Campo(
                        "Correo",
                        formulario.valores["correo"],
                        formulario.poner("correo"),
                        teclado=ft.KeyboardType.EMAIL,
                        sugerencia="usuario@empresa.test",
                        autofoco=True,
                        autocompletar=ft.AutofillHint.USERNAME,
                    ),
                    ui.Campo(
                        "Clave",
                        formulario.valores["clave"],
                        formulario.poner("clave"),
                        contrasena=True,
                        al_enviar=entrar,
                        autocompletar=ft.AutofillHint.PASSWORD,
                    ),
                    *([ui.Aviso(error, tono="error")] if error else []),
                    ft.Row([ui.Boton("Entrando…" if enviando else "Entrar", entrar, cargando=enviando, bloque=True, grande=True)]),
                ],
                titulo="Entrar",
                ayuda="Se entra con la misma cuenta del sistema auditado, la que tenga el rol de auditor. "
                "Cotejo no tiene usuarios propios.",
                pie=pie,
            ),
            PanelConexion(),
        ],
        spacing=d.E4,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    return ft.SafeArea(
        ft.Column(
            [
                ft.Row(
                    [ft.Container(contenido, width=min(440, ancho - 2 * d.E4), padding=ft.Padding.symmetric(vertical=d.E6))],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        expand=True,
    )
