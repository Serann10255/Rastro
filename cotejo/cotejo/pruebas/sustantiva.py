"""Pruebas sustantivas: comportamiento efectivo de la aplicacion (C-05 a C-07).

Es la cobertura que el apartado 4 del documento identifica como el vacio: los
servicios gestionados de evaluacion de configuracion no pueden saber si un
usuario del rol conductor logra crear un envio ni si un usuario de una
organizacion alcanza los datos de otra, porque esas reglas viven en el codigo.
Comprobarlas exige ejercitar el sistema con usuarios de prueba.

Cada prueba verifica dos cosas y no una: el codigo de respuesta que obtiene el
solicitante y el registro que queda en la bitacora. Un sistema que rechaza sin
registrar cumple la mitad del control.
"""

from __future__ import annotations

from ..contexto import Contexto, ErrorContexto
from ..modelos import Conclusion, Observacion, ResultadoPrueba

ENVIO_DE_PRUEBA = {
    "origen": {"linea": "Calle 100 #15-20", "ciudad": "Bogota"},
    "destino": {"linea": "Carrera 7 #32-16", "ciudad": "Bogota"},
    "destinatario": {"nombre": "Destinatario Sintetico"},
    "descripcion": "Envio creado por el programa de auditoria",
}


def _crear_envio(ctx: Contexto, etiqueta: str) -> tuple[str, Observacion]:
    respuesta = ctx.cliente.post(
        "/envios", headers=ctx.cabeceras(etiqueta), json=ENVIO_DE_PRUEBA
    )
    observacion = Observacion(
        f"POST /envios como {etiqueta}",
        {"codigo": respuesta.status_code, "cuerpo": _cuerpo(respuesta)},
    )
    if respuesta.status_code != 201:
        raise ErrorContexto(
            f"No se pudo preparar el envio de prueba: {respuesta.status_code} {respuesta.text[:200]}"
        )
    return respuesta.json()["envio"]["envio_id"], observacion


def _cuerpo(respuesta):
    try:
        return respuesta.json()
    except ValueError:
        return respuesta.text[:500]


def _buscar_en_bitacora(ctx: Contexto, etiqueta_auditor: str, **filtros) -> tuple[list, Observacion]:
    """Lee la bitacora con el rol auditor y devuelve los registros que casan.

    Se consulta con el auditor de la organizacion correspondiente: la bitacora
    de una organizacion no contiene registros de otra, y esa separacion es parte
    de lo que se esta comprobando.
    """
    respuesta = ctx.cliente.get(
        "/bitacora", headers=ctx.cabeceras(etiqueta_auditor), params={"limite": 2000}
    )
    observacion = Observacion(
        f"GET /bitacora como {etiqueta_auditor}",
        {"codigo": respuesta.status_code, "total": _cuerpo(respuesta).get("total")
         if isinstance(_cuerpo(respuesta), dict) else None},
    )
    if respuesta.status_code != 200:
        return [], observacion

    registros = respuesta.json()["registros"]
    coincidencias = [
        r for r in registros if all(str(r.get(c)) == str(v) for c, v in filtros.items())
    ]
    observacion.salida = {
        "codigo": respuesta.status_code,
        "registros_totales": len(registros),
        "filtros": filtros,
        "coincidencias": coincidencias[-3:],
    }
    return coincidencias, observacion


# --------------------------------------------------------------------------- #
# C-05
# --------------------------------------------------------------------------- #


def autorizacion_por_rol(ctx: Contexto) -> ResultadoPrueba:
    """Un conductor invoca la creacion de envios: debe recibir 403 y quedar registrado."""
    procedimiento = (
        "Autenticarse como conductor de la organizacion A, invocar POST /envios "
        "(operacion reservada a despachador y administrador) y buscar el intento "
        "en la bitacora con el rol auditor."
    )
    observaciones: list[Observacion] = []
    fallos: list[str] = []

    try:
        respuesta = ctx.cliente.post(
            "/envios", headers=ctx.cabeceras("conductor_a"), json=ENVIO_DE_PRUEBA
        )
        observaciones.append(
            Observacion(
                "POST /envios como conductor_a",
                {"codigo": respuesta.status_code, "cuerpo": _cuerpo(respuesta)},
            )
        )
        if respuesta.status_code != 403:
            fallos.append(
                f"la respuesta fue {respuesta.status_code} y el criterio exige 403"
            )

        registros, observacion = _buscar_en_bitacora(
            ctx,
            "auditor_a",
            accion="envio:crear",
            resultado="DENY",
            actor_sub=_sub_de(ctx, "conductor_a"),
        )
        observaciones.append(observacion)
        if not registros:
            fallos.append("el intento rechazado no quedo registrado en la bitacora")
        else:
            ultimo = registros[-1]
            faltantes = [
                campo
                for campo in ("actor_sub", "actor_grupos", "accion", "recurso", "resultado")
                if not ultimo.get(campo)
            ]
            if faltantes:
                fallos.append(f"el registro no conserva: {', '.join(faltantes)}")

    except ErrorContexto as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)
    except Exception as exc:  # noqa: BLE001
        return ResultadoPrueba.no_ejecutada(f"{type(exc).__name__}: {exc}", procedimiento)

    return ResultadoPrueba(
        conclusion=Conclusion.DESVIADO if fallos else Conclusion.CONFORME,
        observaciones=observaciones,
        resumen=(
            "; ".join(fallos)
            if fallos
            else "La operacion no autorizada se rechaza con 403 y el intento queda registrado."
        ),
        detalle={"fallos": fallos},
    )


def _sub_de(ctx: Contexto, etiqueta: str) -> str:
    """Obtiene el identificador de sujeto del usuario de prueba desde su sesion."""
    respuesta = ctx.cliente.get("/auth/yo", headers=ctx.cabeceras(etiqueta))
    if respuesta.status_code == 200:
        return respuesta.json()["sub"]
    return ""


# --------------------------------------------------------------------------- #
# C-06
# --------------------------------------------------------------------------- #

#: Rutas de lectura que un usuario de otra organizacion podria intentar. Se
#: prueban todas: basta una sin filtrar para que el aislamiento falle.
RUTAS_DE_LECTURA = [
    ("GET", "/envios/{envio_id}"),
    ("GET", "/envios/{envio_id}/transiciones"),
    ("GET", "/envios/{envio_id}/evidencias"),
]


def aislamiento_entre_organizaciones(ctx: Contexto) -> ResultadoPrueba:
    """Un usuario de la organizacion B pide un envio de la A por cada ruta de lectura."""
    procedimiento = (
        "Crear un envio como despachador de la organizacion A. Autenticarse como "
        "despachador de la organizacion B y solicitar ese envio por su identificador "
        "en cada ruta de lectura. Comprobar despues el registro del intento."
    )
    observaciones: list[Observacion] = []
    fallos: list[str] = []

    try:
        envio_id, observacion = _crear_envio(ctx, "despachador_a")
        observaciones.append(observacion)

        for metodo, plantilla in RUTAS_DE_LECTURA:
            ruta = plantilla.format(envio_id=envio_id)
            respuesta = ctx.cliente.request(
                metodo, ruta, headers=ctx.cabeceras("despachador_b")
            )
            observaciones.append(
                Observacion(
                    f"{metodo} {ruta} como despachador_b (organizacion distinta)",
                    {"codigo": respuesta.status_code, "cuerpo": _cuerpo(respuesta)},
                )
            )
            if respuesta.status_code == 200:
                fallos.append(f"FUGA: {ruta} devolvio datos de otra organizacion")
            elif respuesta.status_code == 403:
                # Un 403 confirma que el recurso existe. El criterio exige 404.
                fallos.append(
                    f"{ruta} respondio 403 y confirma la existencia del recurso; el criterio exige 404"
                )
            elif respuesta.status_code != 404:
                fallos.append(f"{ruta} respondio {respuesta.status_code}, no contemplado")

        registros, observacion = _buscar_en_bitacora(
            ctx, "auditor_b", resultado="DENY"
        )
        observaciones.append(observacion)
        cruzados = [
            r
            for r in registros
            if r.get("detalle", {}).get("motivo") == "fuera_de_organizacion_o_inexistente"
        ]
        if not cruzados:
            fallos.append("el intento entre organizaciones no quedo registrado en la bitacora")

        # La bitacora de la organizacion titular no debe contener el intento
        # ajeno: si lo contuviera, una organizacion sabria de la otra.
        propios, observacion = _buscar_en_bitacora(ctx, "auditor_a", resultado="DENY")
        observaciones.append(observacion)
        if any(r.get("actor_sub") == _sub_de(ctx, "despachador_b") for r in propios):
            fallos.append("la bitacora de la organizacion A contiene actividad de la B")

    except ErrorContexto as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)
    except Exception as exc:  # noqa: BLE001
        return ResultadoPrueba.no_ejecutada(f"{type(exc).__name__}: {exc}", procedimiento)

    return ResultadoPrueba(
        conclusion=Conclusion.DESVIADO if fallos else Conclusion.CONFORME,
        observaciones=observaciones,
        resumen=(
            "; ".join(fallos)
            if fallos
            else "Ninguna ruta de lectura cruza la frontera de organizacion; el intento queda registrado."
        ),
        detalle={"fallos": fallos, "rutas_probadas": len(RUTAS_DE_LECTURA)},
    )


# --------------------------------------------------------------------------- #
# C-07
# --------------------------------------------------------------------------- #

#: Transiciones que el modelo no contempla. Se prueban varias y no una sola:
#: un sistema podria rechazar el salto obvio y admitir el retroceso.
TRANSICIONES_INVALIDAS = ["ENTREGADO", "EN_TRANSITO", "EN_REPARTO"]


def transiciones_invalidas(ctx: Contexto) -> ResultadoPrueba:
    """Sobre un envio en estado CREADO se solicitan transiciones no contempladas."""
    procedimiento = (
        "Crear un envio (queda en CREADO) y solicitar desde ese estado cada "
        "transicion que la maquina de estados no contempla."
    )
    observaciones: list[Observacion] = []
    fallos: list[str] = []

    try:
        envio_id, observacion = _crear_envio(ctx, "despachador_a")
        observaciones.append(observacion)

        for destino in TRANSICIONES_INVALIDAS:
            respuesta = ctx.cliente.post(
                f"/envios/{envio_id}/eventos",
                headers=ctx.cabeceras("despachador_a"),
                json={"estado": destino},
            )
            observaciones.append(
                Observacion(
                    f"POST /envios/{{id}}/eventos con estado {destino} desde CREADO",
                    {"codigo": respuesta.status_code, "cuerpo": _cuerpo(respuesta)},
                )
            )
            if respuesta.status_code != 400:
                fallos.append(
                    f"la transicion CREADO -> {destino} respondio {respuesta.status_code}; "
                    "el criterio exige 400"
                )

        registros, observacion = _buscar_en_bitacora(
            ctx, "auditor_a", resultado="DENY", recurso=f"envio/{envio_id}"
        )
        observaciones.append(observacion)
        con_motivo = [
            r for r in registros if r.get("detalle", {}).get("motivo") == "transicion_invalida"
        ]
        if len(con_motivo) < len(TRANSICIONES_INVALIDAS):
            fallos.append(
                f"se registraron {len(con_motivo)} intentos de transicion invalida "
                f"de {len(TRANSICIONES_INVALIDAS)} realizados"
            )

    except ErrorContexto as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)
    except Exception as exc:  # noqa: BLE001
        return ResultadoPrueba.no_ejecutada(f"{type(exc).__name__}: {exc}", procedimiento)

    return ResultadoPrueba(
        conclusion=Conclusion.DESVIADO if fallos else Conclusion.CONFORME,
        observaciones=observaciones,
        resumen=(
            "; ".join(fallos)
            if fallos
            else f"Las {len(TRANSICIONES_INVALIDAS)} transiciones invalidas se rechazan con 400 y quedan registradas."
        ),
        detalle={"fallos": fallos, "transiciones_probadas": TRANSICIONES_INVALIDAS},
    )
