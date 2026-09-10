"""Prueba de integridad de la bitacora encadenada (C-08).

Se ejecuta en dos sentidos, y esa es la parte importante. Comprobar que el
verificador informa "cadena valida" sobre una bitacora integra no demuestra que
sirva: un verificador que siempre respondiera que si tambien pasaria esa prueba.
Lo que la demuestra es que senale el punto de ruptura cuando la alteracion
existe.

La alteracion se introduce sobre una copia de trabajo descargada, nunca sobre la
bitacora del sistema auditado. Un programa de auditoria no modifica lo que
audita: si lo hiciera, el registro dejaria de ser evidencia.
"""

from __future__ import annotations

import copy

from rastro_core.audit import calcular_hash, verificar_cadena

from ..contexto import Contexto
from ..modelos import Conclusion, Observacion, ResultadoPrueba


def cadena_de_bitacora(ctx: Contexto) -> ResultadoPrueba:
    procedimiento = (
        "Descargar la bitacora con el rol auditor, recalcular la cadena de "
        "funciones hash sobre la copia obtenida, y despues repetir el calculo "
        "sobre tres copias alteradas a proposito: contenido modificado, hash "
        "recalculado por el atacante y registro intermedio eliminado."
    )
    observaciones: list[Observacion] = []
    fallos: list[str] = []

    try:
        respuesta = ctx.cliente.get(
            "/bitacora", headers=ctx.cabeceras("auditor_a"), params={"limite": 2000}
        )
        if respuesta.status_code != 200:
            return ResultadoPrueba.no_ejecutada(
                f"No fue posible descargar la bitacora: {respuesta.status_code}", procedimiento
            )

        registros = respuesta.json()["registros"]
        observaciones.append(
            Observacion(
                "GET /bitacora como auditor_a",
                {"codigo": respuesta.status_code, "registros_descargados": len(registros)},
            )
        )

        if len(registros) < 3:
            return ResultadoPrueba.no_ejecutada(
                "La bitacora tiene menos de tres registros; no hay cadena que verificar.",
                procedimiento,
            )

        # -- sentido 1: la cadena integra debe verificar ------------------- #
        integra = verificar_cadena(copy.deepcopy(registros))
        observaciones.append(
            Observacion(
                "Recalculo de la cadena sobre la copia descargada",
                {
                    "cadena_valida": integra["cadena_valida"],
                    "registros_verificados": integra["registros_verificados"],
                    "rupturas": integra["rupturas"],
                },
            )
        )
        if not integra["cadena_valida"]:
            fallos.append(
                "la cadena de la bitacora del sistema auditado no verifica: "
                f"{integra['punto_de_ruptura']}"
            )

        # -- sentido 2: cada alteracion debe detectarse -------------------- #
        objetivo = len(registros) // 2 or 1
        for nombre, alterados, esperado in _copias_alteradas(registros, objetivo):
            # Comprobar que la copia difiere del original antes de evaluarla.
            # Sin esta guarda, una alteracion que por casualidad no cambiara
            # nada haria concluir que el verificador no detecta la manipulacion,
            # cuando en realidad no se le presento ninguna.
            if alterados == registros:
                fallos.append(
                    f"la alteracion '{nombre}' no modifico la copia; la prueba no es concluyente"
                )
                continue

            resultado = verificar_cadena(alterados)
            detectada = not resultado["cadena_valida"]
            tipos = {r["tipo"] for r in resultado["rupturas"]}
            observaciones.append(
                Observacion(
                    f"Recalculo sobre la copia alterada: {nombre}",
                    {
                        "cadena_valida": resultado["cadena_valida"],
                        "punto_de_ruptura": resultado["punto_de_ruptura"],
                        "tipos_detectados": sorted(tipos),
                    },
                )
            )
            if not detectada:
                fallos.append(f"el verificador NO detecto la alteracion: {nombre}")
            elif esperado not in tipos:
                fallos.append(
                    f"la alteracion '{nombre}' se detecto como {sorted(tipos)} "
                    f"y se esperaba {esperado}"
                )

        # -- la verificacion del sistema auditado coincide con la propia --- #
        propia = ctx.cliente.get("/bitacora/verificacion", headers=ctx.cabeceras("auditor_a"))
        observaciones.append(
            Observacion(
                "GET /bitacora/verificacion como auditor_a",
                {"codigo": propia.status_code, "cuerpo": _resumen_verificacion(propia)},
            )
        )
        if propia.status_code == 200 and propia.json()["cadena_valida"] != integra["cadena_valida"]:
            fallos.append(
                "el verificador del sistema auditado y el recalculo independiente "
                "no coinciden en la conclusion"
            )

    except Exception as exc:  # noqa: BLE001
        return ResultadoPrueba.no_ejecutada(f"{type(exc).__name__}: {exc}", procedimiento)

    return ResultadoPrueba(
        conclusion=Conclusion.DESVIADO if fallos else Conclusion.CONFORME,
        observaciones=observaciones,
        resumen=(
            "; ".join(fallos)
            if fallos
            else "La cadena verifica sobre la bitacora integra y las tres alteraciones se detectan."
        ),
        detalle={"fallos": fallos, "registros_verificados": len(registros)},
    )


#: Valores que ningun registro real puede tener. Usarlos garantiza que la
#: alteracion cambia el contenido: si se reutilizara un valor plausible -poner
#: ALLOW donde ya decia ALLOW- la copia quedaria identica al original y la
#: prueba concluiria que el verificador no detecta nada, cuando en realidad no
#: se le presento nada que detectar.
_ACCION_FALSA = "auditoria:alteracion-controlada"
_RECURSO_FALSO = "envio/alterado-por-cotejo"


def _alterar(registro: dict) -> dict:
    """Cambia el contenido de un registro de forma inequivoca."""
    registro["accion"] = _ACCION_FALSA
    registro["recurso"] = _RECURSO_FALSO
    registro["resultado"] = "DENY" if registro.get("resultado") != "DENY" else "ALLOW"
    return registro


def _copias_alteradas(registros: list[dict], objetivo: int):
    """Produce las tres formas de manipulacion que el control debe detectar."""
    # 1. Contenido modificado sin tocar el hash almacenado.
    contenido = copy.deepcopy(registros)
    _alterar(contenido[objetivo])
    yield "contenido modificado", contenido, "CONTENIDO_ALTERADO"

    # 2. Contenido modificado y hash recalculado: el atacante repara su propio
    #    eslabon, pero no los posteriores, y ahi se rompe el encadenamiento.
    #    Es el escenario que da valor al encadenamiento y el mas exigente.
    reparado = copy.deepcopy(registros)
    _alterar(reparado[objetivo])
    reparado[objetivo]["hash"] = calcular_hash(
        reparado[objetivo]["hash_previo"], reparado[objetivo]
    )
    yield "contenido modificado con hash recalculado", reparado, "ENCADENAMIENTO_ROTO"

    # 3. Registro intermedio eliminado.
    eliminado = [r for i, r in enumerate(copy.deepcopy(registros)) if i != objetivo]
    yield "registro intermedio eliminado", eliminado, "SECUENCIA_INCOMPLETA"


def _resumen_verificacion(respuesta):
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return respuesta.text[:300]
    return {
        clave: cuerpo.get(clave)
        for clave in ("cadena_valida", "registros_verificados", "punto_de_ruptura")
    }
