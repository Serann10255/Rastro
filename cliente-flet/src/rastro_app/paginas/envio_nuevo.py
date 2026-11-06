"""Registro de envíos: uno a uno o en lote desde un archivo.

El registro masivo no es una comodidad: es la operación habitual de un cliente
corporativo, que despacha decenas de envíos de una vez. Sin él, el sistema
obliga a teclear cincuenta formularios y nadie lo usa.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_formulario, use_mutacion
from rastro_app.consultas import TRAS_ESCRIBIR, use_maestro
from rastro_app.contexto import mensaje_de_error, use_app
from rastro_app.lote_csv import COLUMNAS, PLANTILLA, analizar, decodificar


@ft.component
def EnvioNuevo() -> ft.Control:
    modo, poner_modo = ft.use_state("uno")
    return ft.Column(
        [
            ui.Encabezado(
                "Registrar envíos",
                "El sistema genera un identificador aleatorio por envío y crea el registro maestro en estado "
                "CREADO (código 10). A partir de ahí, cada cambio de estado queda atribuido a quien lo hizo.",
                [ui.GrupoSegmentado(modo, [("uno", "Un envío"), ("lote", "Lote")], poner_modo, etiqueta="Modo")],
            ),
            FormularioUnico() if modo == "uno" else CargaDeLote(),
        ],
        spacing=d.E5,
    )


VACIO = {
    "origen": "",
    "origen_referencia": "",
    "destino": "",
    "destino_referencia": "",
    "ciudad": "Bogotá",
    "destinatario": "",
    "telefono": "",
    "descripcion": "",
    "orden_compra": "",
    "tienda_id": "",
    "cliente_id": "",
    "transportista_id": "",
    "bultos": "1",
    "peso_kg": "",
    "valor_declarado": "",
    "fecha_estimada": "",
}


def _numero(texto: str) -> float:
    try:
        return float(str(texto).replace(",", "."))
    except ValueError:
        return 0.0


def a_datos_envio(datos: dict[str, Any]) -> dict[str, Any]:
    """Del formulario al contrato de `POST /envios`. Los opcionales vacíos no se
    envían: el servidor distingue «no lo dijo» de «lo dijo vacío»."""
    ciudad = datos["ciudad"].strip() or "Bogotá"

    def direccion(linea: str, referencia: str) -> dict[str, str]:
        resultado = {"linea": linea.strip(), "ciudad": ciudad}
        if referencia.strip():
            resultado["referencia"] = referencia.strip()
        return resultado

    envio: dict[str, Any] = {
        "origen": direccion(datos["origen"], datos["origen_referencia"]),
        "destino": direccion(datos["destino"], datos["destino_referencia"]),
        "destinatario": {"nombre": datos["destinatario"].strip()},
        "bultos": int(_numero(datos["bultos"])) or 1,
        "peso_kg": _numero(datos["peso_kg"]),
        "valor_declarado": _numero(datos["valor_declarado"]),
    }
    if datos["telefono"].strip():
        envio["destinatario"]["telefono"] = datos["telefono"].strip()
    for campo in ("descripcion", "orden_compra", "tienda_id", "cliente_id", "transportista_id", "fecha_estimada"):
        if str(datos[campo]).strip():
            envio[campo] = str(datos[campo]).strip()
    return envio


@ft.component
def FormularioUnico() -> ft.Control:
    app = use_app()
    tiendas = use_maestro("tiendas")
    clientes = use_maestro("clientes")
    transportistas = use_maestro("transportistas")
    formulario = use_formulario(VACIO)
    errores, poner_errores = ft.use_state({})
    v = formulario.valores

    async def operacion(datos):
        resultado = await app.api.crear_envio(datos)
        app.almacen.invalidar(*TRAS_ESCRIBIR)
        return resultado

    crear = use_mutacion(operacion)

    def cambiar(campo: str):
        poner = formulario.poner(campo)

        def cambio(valor):
            poner(valor)
            if errores.get(campo):
                poner_errores(lambda e: {**e, campo: None})

        return cambio

    def elegir_tienda(tienda_id: str):
        """Al elegir tienda se propone su dirección como origen: es lo que ocurre
        en la práctica y ahorra teclear la misma dirección cincuenta veces."""
        tienda = next((t for t in (tiendas.datos or {}).get("tiendas", []) if t["tienda_id"] == tienda_id), None)
        actual = dict(formulario.actual)
        actual["tienda_id"] = tienda_id
        if tienda:
            actual["origen"] = tienda.get("direccion") or actual["origen"]
            actual["origen_referencia"] = tienda.get("nombre") or actual["origen_referencia"]
        formulario.reemplazar(actual)

    async def enviar():
        """Se valida aquí para no gastar un viaje de red en un campo vacío, pero
        el servidor vuelve a validar: esto es comodidad, no control."""
        actual = formulario.actual
        nuevos = {}
        if len(actual["origen"].strip()) < 3:
            nuevos["origen"] = "Indique la dirección de recogida."
        if len(actual["destino"].strip()) < 3:
            nuevos["destino"] = "Indique la dirección de entrega."
        if len(actual["destinatario"].strip()) < 2:
            nuevos["destinatario"] = "Indique quién recibe el envío."
        poner_errores(nuevos)
        if nuevos:
            return
        try:
            resultado = await crear.ejecutar(a_datos_envio(actual))
            envio_id = resultado["envio"]["envio_id"]
            app.avisar(f"Envío registrado. Guía {envio_id}.", "exito")
            app.ir(f"/envios/{envio_id}", recien_creado=True)
        except Exception:  # noqa: BLE001 - se muestra bajo el formulario
            pass

    opciones_tiendas = [("", "Sin tienda asociada")] + [
        (t["tienda_id"], f"{t.get('codigo', '')} · {t['nombre']}") for t in (tiendas.datos or {}).get("tiendas", [])
    ]
    opciones_clientes = [("", "Sin cliente asociado")] + [
        (c["cliente_id"], c["nombre"]) for c in (clientes.datos or {}).get("clientes", [])
    ]
    opciones_transportistas = [("", "Por asignar")] + [
        (t["transportista_id"], f"{t['nombre']} ({t.get('tipo', '')})")
        for t in (transportistas.datos or {}).get("transportistas", [])
    ]

    izquierda = [
        ui.Tarjeta(
            [
                ui.Selector("Tienda de origen", v["tienda_id"], opciones_tiendas, elegir_tienda, ayuda="Al elegirla se propone su dirección como origen."),
                ui.Campo("Dirección de recogida", v["origen"], cambiar("origen"), sugerencia="Calle 100 #15-20", error=errores.get("origen")),
                ui.Campo("Referencia de recogida", v["origen_referencia"], cambiar("origen_referencia"), opcional=True, sugerencia="Oficina 402, portería norte"),
                ui.Campo("Dirección de entrega", v["destino"], cambiar("destino"), sugerencia="Carrera 7 #32-16", error=errores.get("destino")),
                ui.Campo("Referencia de entrega", v["destino_referencia"], cambiar("destino_referencia"), opcional=True, sugerencia="Piso 8"),
                ui.Campo("Ciudad", v["ciudad"], cambiar("ciudad")),
            ],
            titulo="Recogida y entrega",
        ),
        ui.Tarjeta(
            ui.Rejilla(
                [
                    ui.Campo("Bultos", v["bultos"], cambiar("bultos"), teclado=ft.KeyboardType.NUMBER),
                    ui.Campo("Peso (kg)", v["peso_kg"], cambiar("peso_kg"), opcional=True, teclado=ft.KeyboardType.NUMBER),
                    ui.Campo("Valor declarado", v["valor_declarado"], cambiar("valor_declarado"), opcional=True, teclado=ft.KeyboardType.NUMBER, ayuda="No se imprime en la guía."),
                ],
                {"xs": 12, "sm": 4},
            ),
            titulo="Carga",
        ),
    ]
    derecha: list[ft.Control] = [
        ui.Tarjeta(
            [
                ui.Campo(
                    "Nombre del destinatario",
                    v["destinatario"],
                    cambiar("destinatario"),
                    sugerencia="Nombre y apellido",
                    error=errores.get("destinatario"),
                    ayuda="En la consulta pública el nombre se muestra enmascarado.",
                ),
                ui.Campo("Teléfono", v["telefono"], cambiar("telefono"), opcional=True, teclado=ft.KeyboardType.PHONE),
                ui.Selector("Cliente", v["cliente_id"], opciones_clientes, cambiar("cliente_id")),
                ui.Selector("Transportista", v["transportista_id"], opciones_transportistas, cambiar("transportista_id")),
                ui.Campo(
                    "Orden de compra",
                    v["orden_compra"],
                    cambiar("orden_compra"),
                    opcional=True,
                    sugerencia="OC-2026-1042",
                    ayuda="La referencia del cliente. No la genera el sistema y puede repetirse.",
                ),
                ui.Campo(
                    "Fecha estimada de entrega",
                    v["fecha_estimada"],
                    cambiar("fecha_estimada"),
                    opcional=True,
                    sugerencia="AAAA-MM-DD",
                    teclado=ft.KeyboardType.DATETIME,
                    ayuda="Sirve para saber qué envíos van tarde.",
                ),
                ui.Campo(
                    "Descripción del contenido",
                    v["descripcion"],
                    cambiar("descripcion"),
                    opcional=True,
                    multilinea=True,
                    filas=2,
                    sugerencia="Sobre con documentos contractuales",
                ),
            ],
            titulo="Destinatario y referencias",
        ),
        ui.Aviso(
            "El sistema se puebla únicamente con datos sintéticos, de modo que el proyecto no genera obligaciones "
            "de tratamiento sobre titulares reales.",
            tono="info",
            titulo="Datos sintéticos",
        ),
    ]
    if crear.error:
        derecha.append(ui.Aviso(mensaje_de_error(crear.error), tono="error", titulo="No se pudo registrar el envío"))
    derecha.append(
        ft.Row(
            [
                ui.Boton("Registrar envío", enviar, cargando=crear.pendiente, grande=True),
                ui.Boton("Cancelar", lambda: app.volver("/envios"), variante="secundario"),
            ],
            wrap=True,
            spacing=d.E2,
        )
    )
    return ui.DoblePanel(izquierda, derecha)


# --------------------------------------------------------------------------- #
# Lote
# --------------------------------------------------------------------------- #


@ft.component
def CargaDeLote() -> ft.Control:
    app = use_app()
    tiendas = use_maestro("tiendas")
    clientes = use_maestro("clientes")
    formulario = use_formulario({"texto": "", "tienda_id": "", "cliente_id": ""})
    resultado, poner_resultado = ft.use_state(None)
    v = formulario.valores
    analisis = analizar(v["texto"])

    async def operacion(envios):
        respuesta = await app.api.crear_lote(envios)
        app.almacen.invalidar(*TRAS_ESCRIBIR)
        return respuesta

    crear_lote = use_mutacion(operacion)

    async def enviar():
        actual = formulario.actual
        filas = analizar(actual["texto"]).filas
        if not filas:
            return
        envios = []
        for fila in filas:
            envio = dict(fila)
            if actual["tienda_id"]:
                envio["tienda_id"] = actual["tienda_id"]
            if actual["cliente_id"]:
                envio["cliente_id"] = actual["cliente_id"]
            envios.append(envio)
        try:
            respuesta = await crear_lote.ejecutar(envios)
            poner_resultado(respuesta)
            resumen = respuesta["resumen"]
            app.avisar(
                f"{resumen['creados']} envíos registrados"
                + (f", {resumen['rechazados']} rechazados" if resumen["rechazados"] else "")
                + ".",
                "alerta" if resumen["rechazados"] else "exito",
            )
        except Exception:  # noqa: BLE001 - se muestra bajo el formulario
            pass

    async def descargar_plantilla():
        await ft.FilePicker().save_file(
            dialog_title="Guardar la plantilla",
            file_name="plantilla-envios.csv",
            src_bytes=PLANTILLA.encode("utf-8"),
        )

    async def leer_archivo():
        archivos = await ft.FilePicker().pick_files(
            dialog_title="Archivo de envíos",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv", "txt"],
            with_data=True,
        )
        if archivos and archivos[0].bytes is not None:
            formulario.poner("texto")(decodificar(archivos[0].bytes))

    opciones_tiendas = [("", "Sin tienda")] + [
        (t["tienda_id"], f"{t.get('codigo', '')} · {t['nombre']}") for t in (tiendas.datos or {}).get("tiendas", [])
    ]
    opciones_clientes = [("", "Sin cliente")] + [(c["cliente_id"], c["nombre"]) for c in (clientes.datos or {}).get("clientes", [])]

    izquierda = [
        ui.Tarjeta(
            [
                ft.Row([ui.Boton("Elegir archivo CSV", leer_archivo, variante="secundario", icono=ft.Icons.UPLOAD_FILE)]),
                ui.Campo(
                    "O pegue el contenido",
                    v["texto"],
                    formulario.poner("texto"),
                    multilinea=True,
                    filas=8,
                    sugerencia=PLANTILLA,
                    ayuda=f"Columnas reconocidas: {', '.join(COLUMNAS)}.",
                ),
                ui.Rejilla(
                    [
                        ui.Selector("Tienda para todo el lote", v["tienda_id"], opciones_tiendas, formulario.poner("tienda_id")),
                        ui.Selector("Cliente para todo el lote", v["cliente_id"], opciones_clientes, formulario.poner("cliente_id")),
                    ],
                    {"xs": 12, "md": 6},
                ),
            ],
            titulo="Archivo de envíos",
            ayuda="Un envío por fila, separado por comas. La primera fila son los nombres de columna.",
            acciones=[ui.Boton("Descargar plantilla", descargar_plantilla, variante="secundario", icono=ft.Icons.DOWNLOAD)],
        )
    ]

    vista: list[ft.Control] = []
    if analisis.error:
        vista.append(ui.Aviso(analisis.error, tono="error"))
    if not v["texto"].strip():
        vista.append(ui.Texto("Pegue el contenido o elija un archivo para ver aquí lo que se va a registrar.", tono="texto-suave"))
    if analisis.filas:
        resumen = f"{len(analisis.filas)} envíos listos."
        if analisis.ignoradas:
            resumen += f" {analisis.ignoradas} filas se omitieron por no tener destinatario o dirección."
        vista.append(ui.Texto(resumen))
        for fila in analisis.filas[:5]:
            vista.append(
                ft.Column(
                    [
                        ft.Text(fila["destinatario"]["nombre"], size=d.T_SM, weight=ft.FontWeight.W_600),
                        ui.Texto(f"{fila['destino']['linea']} · {fila['destino']['ciudad']}", tono="texto-suave", tamano=d.T_XS),
                        *([ui.Texto(f"OC {fila['orden_compra']}", tono="texto-tenue", tamano=d.T_XS, mono=True)] if fila.get("orden_compra") else []),
                    ],
                    spacing=2,
                )
            )
        if len(analisis.filas) > 5:
            vista.append(ui.Texto(f"y {len(analisis.filas) - 5} más.", tono="texto-tenue", tamano=d.T_XS))
    if crear_lote.error:
        vista.append(ui.Aviso(mensaje_de_error(crear_lote.error), tono="error"))
    vista.append(
        ft.Row(
            [
                ui.Boton(
                    f"Registrar {len(analisis.filas) or ''} envíos",
                    enviar,
                    cargando=crear_lote.pendiente,
                    deshabilitado=not analisis.filas,
                    grande=True,
                )
            ]
        )
    )
    derecha: list[ft.Control] = [ui.Tarjeta(vista, titulo="Vista previa")]

    if resultado:
        resumen = resultado["resumen"]
        partes: list[ft.Control] = [
            ui.Aviso(
                f"{resumen['creados']} de {resumen['solicitados']} envíos registrados.",
                tono="alerta" if resumen["rechazados"] else "exito",
            )
        ]
        if resultado.get("rechazados"):
            partes += [
                ui.Texto("Las filas rechazadas no impidieron el resto. Corrija estas y vuelva a enviarlas:", tono="texto-suave"),
                ui.TablaDesplazable(
                    ["Fila", "Destinatario", "Motivo"],
                    [[r["indice"] + 2, r.get("destinatario", ""), r.get("motivo", "")] for r in resultado["rechazados"]],
                    ancho_minimo=448,
                ),
            ]
        creados = [e["envio_id"] for e in resultado.get("creados", [])]
        derecha.append(
            ui.Tarjeta(
                partes,
                titulo="Resultado del lote",
                acciones=[ui.Boton("Generar guías", lambda: app.ir("/envios/guias", envios_guias=creados), icono=ft.Icons.QR_CODE_2)]
                if creados
                else None,
            )
        )
    return ui.DoblePanel(izquierda, derecha)
