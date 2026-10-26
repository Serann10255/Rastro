"""Pantalla de acceso.

No lista cuentas ni las rellena: las credenciales las administra el
administrador de cada empresa desde el propio sistema. Mostrar usuarios y
contraseñas en la pantalla de entrada convertiría el control de acceso en una
formalidad.

Lo que añade frente a la web es el panel «Conexión»: una aplicación instalada
no tiene un `configuracion.json` junto al sitio, y es aquí donde se le dice a
qué despliegue hablar sin reconstruirla (REQ-09).
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_formulario
from comun.http import ErrorApi, enviar
from comun.marca import LogotipoRastro
from rastro_app.aplicacion_claves import CLAVE_URL_API
from rastro_app.contexto import mensaje_de_error, use_ancho, use_app, use_sesion
from rastro_app.estructura import SelectorTema


@ft.component
def PanelConexion() -> ft.Control:
    app = use_app()
    abierto, poner_abierto = ft.use_state(False)
    formulario = use_formulario({"direccion": app.configuracion.get("url_publica_api", "")})
    resultado, poner_resultado = ft.use_state(None)
    probando, poner_probando = ft.use_state(False)

    async def probar_y_guardar():
        url = formulario.actual["direccion"].strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            poner_resultado(("error", "La dirección debe empezar por https:// (o http:// en la red local)."))
            return
        poner_probando(True)
        try:
            respuesta = await enviar("GET", f"{url}/catalogos/estados")
            if not respuesta.is_success:
                raise ErrorApi(respuesta.status_code, "ERROR", f"El servicio respondió con código {respuesta.status_code}.")
            await app.preferencias.set(CLAVE_URL_API, url)
            app.api.configuracion = {**app.configuracion, "url_publica_api": url}
            app.origen_configuracion = "dirección fijada en este dispositivo"
            poner_resultado(("exito", "Conectado. La dirección queda guardada en este dispositivo."))
        except ErrorApi as error:
            poner_resultado(("error", f"No respondió como Rastro: {error.mensaje}"))
        finally:
            poner_probando(False)

    async def olvidar():
        await app.preferencias.remove(CLAVE_URL_API)
        poner_resultado(("info", "Se usará la dirección empaquetada la próxima vez que abra la aplicación."))

    if not abierto:
        return ft.TextButton(
            f"Conexión: {app.configuracion.get('url_publica_api') or 'mismo origen'}",
            icon=ft.Icons.SETTINGS_ETHERNET,
            on_click=lambda: poner_abierto(True),
        )

    return ui.Tarjeta(
        [
            ui.Campo(
                "Dirección de la API",
                formulario.valores["direccion"],
                formulario.poner("direccion"),
                ayuda="La de `url_publica_api` del despliegue. Se comprueba antes de guardarla.",
                teclado=ft.KeyboardType.URL,
            ),
            *([ui.Aviso(resultado[1], tono=resultado[0])] if resultado else []),
            ft.Row(
                [
                    ui.Boton("Probar y guardar", probar_y_guardar, cargando=probando),
                    ui.Boton("Usar la empaquetada", olvidar, variante="sutil"),
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

    def ya_dentro():
        if sesion.autenticado:
            app.ir(app.tomar("desde", "/panel"), reemplazar=True)

    ft.use_effect(ya_dentro, [sesion.autenticado])

    async def entrar():
        correo, clave = formulario.actual["correo"], formulario.actual["clave"]
        if not correo.strip() or not clave:
            poner_error("Escriba el correo y la contraseña.")
            return
        poner_error(None)
        poner_enviando(True)
        try:
            await sesion.entrar(correo, clave)
        except Exception as fallo:  # noqa: BLE001 - se muestra bajo el formulario
            poner_error(mensaje_de_error(fallo))
        finally:
            poner_enviando(False)

    configuracion = app.configuracion
    contenido = ft.Column(
        [
            ft.Row(
                [
                    LogotipoRastro(40),
                    ft.Column(
                        [
                            ft.Text("Rastro", size=d.T_2XL, weight=ft.FontWeight.W_800),
                            ft.Text("Trazabilidad verificable de envíos", size=d.T_SM, color=p["texto-suave"]),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    SelectorTema(),
                ],
                spacing=d.E3,
            ),
            ui.Tarjeta(
                [
                    # El aviso de la salida anterior desaparece en cuanto hay un
                    # error del intento actual: dos mensajes sobre el mismo
                    # formulario se leen como contradictorios.
                    *([ui.Aviso(sesion.motivo_de_salida, tono="alerta")] if sesion.motivo_de_salida and not error else []),
                    ui.Campo(
                        "Correo",
                        formulario.valores["correo"],
                        formulario.poner("correo"),
                        teclado=ft.KeyboardType.EMAIL,
                        sugerencia="nombre@empresa.com",
                        autofoco=True,
                        autocompletar=ft.AutofillHint.USERNAME,
                    ),
                    ui.Campo(
                        "Contraseña",
                        formulario.valores["clave"],
                        formulario.poner("clave"),
                        contrasena=True,
                        al_enviar=entrar,
                        autocompletar=ft.AutofillHint.PASSWORD,
                    ),
                    *([ui.Aviso(error, tono="error", titulo="No fue posible entrar")] if error else []),
                    ft.Row([ui.Boton("Entrar", entrar, cargando=enviando, bloque=True, grande=True)]),
                    ui.Texto(
                        "¿No tiene cuenta? El administrador de su empresa la crea desde el sistema.",
                        tono="texto-suave",
                    ),
                ]
            ),
            ui.Tarjeta(
                ft.Row(
                    [
                        ui.Texto("¿Espera un envío?", tono="texto-suave"),
                        ft.TextButton("Consulte su avance con el identificador", on_click=lambda: app.ir("/rastreo")),
                    ],
                    wrap=True,
                    spacing=d.E1,
                )
            ),
            PanelConexion(),
            ft.Text(
                f"Entorno {configuracion.get('entorno', 'local')} · región {configuracion.get('region', '')}",
                size=d.T_XS,
                color=p["texto-tenue"],
                text_align=ft.TextAlign.CENTER,
            ),
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
