"""Microservicio de bitacora de auditoria (REQ-07, REQ-08).

Expone la bitacora encadenada al rol auditor, que consulta sin poder modificar,
y el verificador de la cadena, que es el procedimiento con el que se demuestra
que el registro no fue alterado.

El servicio no ofrece ninguna operacion de escritura sobre la bitacora. Los
eslabones los escriben los demas servicios como efecto de sus propias
operaciones; ningun usuario, ni siquiera el administrador, puede anadir o
corregir un registro por esta via.
"""

from __future__ import annotations

from fastapi import Depends, Query

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.http import Contexto, contexto_actual, crear_app

app = crear_app(
    "rastro-bitacora",
    "Consulta de solo lectura y verificacion de integridad de la bitacora encadenada.",
)


@app.get("/bitacora", tags=["bitacora"], summary="Consultar la bitacora de la organizacion")
async def consultar_bitacora(
    limite: int = Query(default=200, ge=1, le=2000),
    resultado: str | None = Query(default=None, pattern="^(ALLOW|DENY|ERROR)$"),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Solo el grupo auditor la alcanza; cualquier otro obtiene 403 y queda registrado."""
    ctx.exigir(Operacion.BITACORA_CONSULTAR, recurso="bitacora")

    registros = ctx.repositorio.listar_bitacora(ctx.org_id, limite=limite)
    if resultado:
        registros = [r for r in registros if r.get("resultado") == resultado]

    # La consulta del auditor tambien deja rastro: quien reviso y cuando.
    ctx.registrar(
        accion=Operacion.BITACORA_CONSULTAR,
        recurso="bitacora",
        resultado=Resultado.ALLOW,
        detalle={"devueltos": len(registros), "filtro_resultado": resultado},
    )
    return {"org_id": ctx.org_id, "registros": registros, "total": len(registros)}


@app.get(
    "/bitacora/verificacion",
    tags=["bitacora"],
    summary="Verificar la integridad de la cadena",
)
async def verificar_bitacora(ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Recalcula la cadena completa y senala el punto exacto de ruptura.

    Cotejo consume esta operacion como prueba del control C-08. El criterio de
    aceptacion tiene dos sentidos: sobre una bitacora integra debe informar
    cadena valida, y tras una alteracion controlada debe senalar donde se rompio.
    Comprobar solo lo primero no demuestra que el verificador sirva.
    """
    ctx.exigir(Operacion.BITACORA_VERIFICAR, recurso="bitacora/verificacion")

    verificacion = ctx.repositorio.verificar_bitacora(ctx.org_id)

    ctx.registrar(
        accion=Operacion.BITACORA_VERIFICAR,
        recurso="bitacora/verificacion",
        resultado=Resultado.ALLOW,
        detalle={
            "cadena_valida": verificacion["cadena_valida"],
            "registros_verificados": verificacion["registros_verificados"],
        },
    )
    return {"org_id": ctx.org_id, **verificacion}
