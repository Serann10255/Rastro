"""Bitácora de auditoría.

Solo el rol auditor la alcanza, y la pantalla no ofrece ninguna forma de
escribir: los eslabones los producen los demás servicios como efecto de sus
operaciones, y el servicio de bitácora no expone rutas de escritura. Aquí eso se
refleja en que no hay un solo formulario de edición.
"""

from __future__ import annotations

import json

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta, use_mutacion
from comun.formato import fecha_legible
from rastro_app.contexto import mensaje_de_error, use_app


@ft.component
def Bitacora() -> ft.Control:
    app = use_app()
    filtro, poner_filtro = ft.use_state("todos")
    busqueda, poner_busqueda = ft.use_state("")
    detalle, poner_detalle = ft.use_state(None)
    verificacion, poner_verificacion = ft.use_state(None)

    resultado = None if filtro == "todos" else filtro
    bitacora = use_consulta(app.almacen, ("bitacora", filtro), lambda: app.api.bitacora(resultado))
    verificar = use_mutacion(app.api.verificar_bitacora)

    async def ejecutar_verificacion():
        try:
            poner_verificacion(await verificar.ejecutar())
        except Exception:  # noqa: BLE001 - se muestra en la tarjeta
            pass

    termino = busqueda.strip().lower()
    lista = (bitacora.datos or {}).get("registros", [])
    filtrados = [
        r
        for r in lista
        if not termino
        or termino in " ".join(str(r.get(c) or "") for c in ("actor_sub", "accion", "recurso", "actor_email")).lower()
    ]
    registros = list(reversed(filtrados))
    rechazos = sum(1 for r in lista if r.get("resultado") == "DENY")

    def valor(v):
        return ui.Esqueleto(alto=32, ancho=48) if bitacora.cargando else v

    if verificacion:
        estado_cadena = "íntegra" if verificacion["cadena_valida"] else "rota"
        nota_cadena = f"verificada {fecha_legible(verificacion.get('verificado_en'))}"
        color_cadena = "exito" if verificacion["cadena_valida"] else "peligro"
    else:
        estado_cadena, nota_cadena, color_cadena = "sin verificar", "Pulse verificar", None

    cuerpo_verificacion: list[ft.Control] = []
    if verificar.error:
        cuerpo_verificacion.append(ui.Aviso(mensaje_de_error(verificar.error), tono="error"))
    if verificacion:
        ruptura = verificacion.get("punto_de_ruptura") or {}
        rupturas = verificacion.get("rupturas") or []
        cuerpo_verificacion += [
            ui.Aviso(
                f"{verificacion['registros_verificados']} registros recalculados, secuencias "
                f"{verificacion.get('primera_seq')} a {verificacion.get('ultima_seq')}."
                if verificacion["cadena_valida"]
                else f"{len(rupturas)} ruptura{'' if len(rupturas) == 1 else 's'}. La primera en la secuencia "
                f"{ruptura.get('seq', ruptura.get('seq_esperada'))}: {ruptura.get('descripcion', '')}",
                tono="exito" if verificacion["cadena_valida"] else "error",
                titulo="La cadena verifica" if verificacion["cadena_valida"] else "La cadena está rota",
            ),
            VistaCadena(verificacion),
            ui.Texto(f"Hash final: {verificacion.get('hash_final', '')}", tono="texto-tenue", tamano=d.T_XS, mono=True),
        ]
    else:
        cuerpo_verificacion.append(
            ui.Texto(
                "La verificación no se ejecuta sola: es un procedimiento de auditoría y debe quedar constancia "
                "de quién lo ejecutó. Al pulsar, la consulta también se registra.",
                tono="texto-suave",
            )
        )

    partes: list[ft.Control] = [
        ui.Encabezado(
            "Bitácora de auditoría",
            "Registro encadenado por funciones hash. Cada entrada conserva quién ejecutó la acción, cuál fue, "
            "sobre qué recurso y en qué momento. Modificar o eliminar un registro rompe la verificación de "
            "todos los posteriores.",
        ),
        ui.Rejilla(
            [
                ui.Metrica("Registros", valor((bitacora.datos or {}).get("total", 0)), "En la cadena de su organización", "acento"),
                ui.Metrica("Rechazos registrados", valor(rechazos), "Intentos denegados que dejaron rastro", "peligro" if rechazos else None),
                ui.Metrica("Estado de la cadena", estado_cadena, nota_cadena, color_cadena),
            ],
            {"xs": 12, "md": 4},
        ),
        ui.Tarjeta(
            cuerpo_verificacion,
            titulo="Verificación de integridad",
            ayuda="El criterio tiene dos sentidos: sobre una bitácora íntegra debe informar cadena válida, y "
            "tras una alteración debe señalar dónde se rompió.",
            acciones=[ui.Boton("Verificar cadena", ejecutar_verificacion, cargando=verificar.pendiente)],
        ),
        ui.Tarjeta(
            ui.Rejilla(
                [
                    ui.Campo("Buscar", busqueda, poner_busqueda, sugerencia="Actor, acción o recurso"),
                    ui.GrupoSegmentado(
                        filtro,
                        [("todos", "Todos"), ("ALLOW", "Permitidas"), ("DENY", "Rechazadas")],
                        poner_filtro,
                        etiqueta="Resultado",
                    ),
                    ft.Row([ui.Boton("Actualizar", bitacora.recargar, variante="secundario", cargando=bitacora.refrescando, icono=ft.Icons.REFRESH)]),
                ],
                {"xs": 12, "md": 6, "lg": 4},
            )
        ),
    ]
    if bitacora.error:
        partes.append(ui.Aviso(mensaje_de_error(bitacora.error), tono="error"))
    if bitacora.cargando:
        partes.append(ui.Esqueleto(alto=320))
    elif not registros:
        partes.append(ui.Tarjeta(ui.Vacio("Sin registros", "Ninguna entrada coincide con el filtro.")))
    else:
        filas = [
            [
                str(r["seq"]),
                fecha_legible(r.get("ts")),
                ft.Column(
                    [ft.Text(r.get("actor_sub", ""), size=d.T_SM), ui.Texto(", ".join(r.get("actor_grupos") or []), tono="texto-tenue", tamano=d.T_XS)],
                    spacing=0,
                    tight=True,
                ),
                ft.Column(
                    [ft.Text(r.get("accion", ""), size=d.T_SM), ui.Texto(r.get("recurso", ""), tono="texto-tenue", tamano=d.T_XS, mono=True)],
                    spacing=0,
                    tight=True,
                ),
                ui.EtiquetaResultado(r.get("resultado", "")),
                ft.Text(f"{r.get('hash', '')[:12]}…", size=d.T_XS, font_family=d.FUENTE_MONO),
                ui.Boton("Ver", lambda r=r: poner_detalle(r), variante="sutil"),
            ]
            for r in registros[:300]
        ]
        partes.append(
            ui.Tarjeta(
                [
                    ui.TablaDesplazable(["Seq", "Fecha", "Actor", "Acción y recurso", "Resultado", "Hash", ""], filas, ancho_minimo=900),
                    *(
                        [ui.Texto(f"Se muestran los 300 más recientes de {len(registros)}. Use la búsqueda para acotar.", tono="texto-tenue", tamano=d.T_XS)]
                        if len(registros) > 300
                        else []
                    ),
                ]
            )
        )

    DetalleRegistro(detalle, lambda: poner_detalle(None))
    return ft.Column(partes, spacing=d.E4)


@ft.component
def VistaCadena(verificacion: dict) -> ft.Control:
    """Cada eslabón es un bloque, y los rotos se destacan: en una tabla de
    cientos de filas es difícil ver de un vistazo dónde se rompió."""
    p = ui.paleta()
    primera = verificacion.get("primera_seq") or 1
    ultima = verificacion.get("ultima_seq") or 0
    total = max(0, ultima - primera + 1)
    if total == 0:
        return ft.Container()
    rotos = {r.get("seq", r.get("seq_esperada", -1)) for r in verificacion.get("rupturas") or []}
    limite = 160
    eslabones = [
        ft.Container(
            width=10,
            height=14,
            border_radius=3,
            bgcolor=p["peligro"] if seq in rotos else p["exito"],
            tooltip=f"Secuencia {seq}",
        )
        for seq in range(primera, primera + min(total, limite))
    ]
    texto = f"{total} eslabones" + (f" (se muestran los primeros {limite})" if total > limite else "") + "."
    if rotos:
        texto += " En rojo, los puntos donde la verificación falla."
    return ft.Column([ft.Row(eslabones, wrap=True, spacing=3, run_spacing=3), ui.Texto(texto, tono="texto-tenue", tamano=d.T_XS)], spacing=d.E2)


def DetalleRegistro(registro: dict | None, al_cerrar) -> None:
    """El registro completo en un diálogo. Es un hook (usa `use_modal`): se
    llama siempre, haya registro o no."""
    contenido: list[ft.Control] = []
    if registro:
        contenido = [
            ui.Dato("Actor", f"{registro.get('actor_sub', '')} ({registro.get('actor_email') or 'sin correo'})"),
            ui.Dato("Grupos", ", ".join(registro.get("actor_grupos") or []) or "ninguno"),
            ui.Dato("Acción", registro.get("accion", "")),
            ui.Dato("Recurso", registro.get("recurso", "")),
            ui.Dato("Resultado", registro.get("resultado", "")),
            ui.Dato("Organización", registro.get("org_id", "")),
            ft.Text("DETALLE", size=d.T_XS, weight=ft.FontWeight.W_700, opacity=0.6),
            ft.Container(
                ft.Text(json.dumps(registro.get("detalle") or {}, indent=2, ensure_ascii=False), size=d.T_XS, font_family=d.FUENTE_MONO, selectable=True),
                padding=d.E3,
                border_radius=d.R_MD,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ),
            ui.Dato("Hash previo", registro.get("hash_previo", "")),
            ui.Dato("Hash", registro.get("hash", "")),
            ft.Text(
                "El hash se calcula sobre el hash anterior concatenado con el contenido de este registro. "
                "Cambiar cualquier campo lo invalida, y reparar este eslabón rompe el siguiente.",
                size=d.T_XS,
                opacity=0.7,
            ),
        ]
    ui.use_modal(
        registro is not None,
        f"Registro {registro['seq']}" if registro else "",
        contenido,
        al_cerrar,
        acciones=[ui.Boton("Cerrar", al_cerrar, variante="secundario")],
        ayuda=fecha_legible(registro.get("ts")) if registro else None,
    )
