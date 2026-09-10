"""Microservicio de tablero: indicadores de la organizacion.

Agrega sobre los envios de la organizacion del token. Ningun indicador cruza la
frontera de organizacion: el tablero de una empresa no puede mostrar ni siquiera
un total que incluya envios de otra, porque un total tambien es informacion.

Los calculos se hacen en el servicio y no en la interfaz. La razon es que un
tablero calculado en el cliente obliga a enviarle todos los envios, y eso es a
la vez lento y una entrega de datos que la pantalla no necesita mostrar.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from fastapi import Depends, Query

from rastro_core.audit import Resultado
from rastro_core.authz import Grupo, Operacion, normalizar_grupos
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.ids import ahora_utc, marca_tiempo
from rastro_core.maestros import RepositorioMaestros
from rastro_core.state_machine import CATALOGO, Estado, POR_ESTADO

app = crear_app(
    "rastro-tablero",
    "Indicadores de operacion de la organizacion.",
)

_maestros: RepositorioMaestros | None = None


def maestros() -> RepositorioMaestros:
    global _maestros
    if _maestros is None:
        _maestros = RepositorioMaestros()
    return _maestros


def fijar_maestros(repositorio: RepositorioMaestros) -> None:
    global _maestros
    _maestros = repositorio


def _fecha(iso: str | None) -> dt.date | None:
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).date()
    except ValueError:
        return None


@app.get("/tablero", tags=["tablero"], summary="Indicadores de la organizacion")
async def tablero(
    dias: int = Query(default=30, ge=1, le=365),
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Resumen de operacion de los ultimos ``dias`` dias.

    El conductor ve el mismo tablero acotado a sus propios envios: no es un
    tablero distinto, es el mismo con el filtro que ya aplica el resto del
    sistema.
    """
    ctx.exigir(Operacion.TABLERO_CONSULTAR, recurso="tablero")

    envios = ctx.repositorio.listar_envios(ctx.org_id, limite=2000)

    grupos = normalizar_grupos(ctx.identidad.grupos)
    solo_propios = Grupo.CONDUCTOR in grupos and not (
        grupos & {Grupo.ADMINISTRADOR, Grupo.DESPACHADOR, Grupo.AUDITOR}
    )
    if solo_propios:
        envios = [e for e in envios if e.get("conductor_sub") == ctx.identidad.sub]

    hoy = ahora_utc().date()
    desde = hoy - dt.timedelta(days=dias - 1)
    en_ventana = [e for e in envios if (_fecha(e.get("creado_en")) or hoy) >= desde]

    por_estado = Counter(e.get("estado", "") for e in envios)
    finales = {str(d.estado) for d in CATALOGO if d.final}
    abiertos = [e for e in envios if e.get("estado") not in finales]

    entregados = por_estado.get(str(Estado.ENTREGADO), 0)
    devueltos = por_estado.get(str(Estado.DEVUELTO), 0)
    cancelados = por_estado.get(str(Estado.CANCELADO), 0)
    cerrados = entregados + devueltos + cancelados

    empresa = maestros().obtener_empresa(ctx.org_id)
    usuarios = maestros().listar_usuarios(ctx.org_id)

    resultado = {
        "empresa": {
            "org_id": empresa["org_id"],
            "nombre": empresa["nombre"],
            "nit": empresa.get("nit", ""),
            "ciudad": empresa.get("ciudad", ""),
            "departamento": empresa.get("departamento", ""),
        },
        "ventana": {"dias": dias, "desde": desde.isoformat(), "hasta": hoy.isoformat()},
        "alcance": "propios" if solo_propios else "organizacion",
        "totales": {
            "envios": len(envios),
            "abiertos": len(abiertos),
            "cerrados": cerrados,
            "entregados": entregados,
            "devueltos": devueltos,
            "cancelados": cancelados,
            "creados_en_ventana": len(en_ventana),
        },
        # La tasa de entrega se calcula sobre los cerrados y no sobre el total:
        # incluir los que siguen en curso la hunde artificialmente al principio
        # del dia y no dice nada util.
        "tasa_entrega": round(entregados / cerrados * 100, 1) if cerrados else None,
        "por_estado": _desglose_por_estado(por_estado),
        "por_fase": _desglose_por_fase(por_estado),
        "atencion": _requieren_atencion(envios, hoy),
        "serie_diaria": _serie_diaria(envios, desde, hoy),
        "equipo": _resumen_equipo(usuarios) if not solo_propios else None,
        "generado_en": marca_tiempo(),
    }

    ctx.registrar(
        accion=Operacion.TABLERO_CONSULTAR,
        recurso="tablero",
        resultado=Resultado.ALLOW,
        detalle={"dias": dias, "alcance": resultado["alcance"], "envios": len(envios)},
    )
    return resultado


def _desglose_por_estado(por_estado: Counter) -> list[dict]:
    """Todos los estados del catalogo, incluidos los que estan en cero.

    Mostrar solo los que tienen envios haria que el tablero cambiara de forma
    entre una carga y otra, y que un estado en cero -que es informacion- pasara
    inadvertido.
    """
    return [
        {
            "codigo": definicion.codigo,
            "estado": str(definicion.estado),
            "etiqueta": definicion.etiqueta,
            "fase": str(definicion.fase),
            "final": definicion.final,
            "cantidad": por_estado.get(str(definicion.estado), 0),
        }
        for definicion in CATALOGO
    ]


def _desglose_por_fase(por_estado: Counter) -> list[dict]:
    fases: dict[str, int] = {}
    for estado, cantidad in por_estado.items():
        definicion = POR_ESTADO.get(Estado(estado)) if estado in POR_ESTADO else None
        if definicion is None:
            try:
                definicion = POR_ESTADO[Estado(estado)]
            except (ValueError, KeyError):
                continue
        fases[str(definicion.fase)] = fases.get(str(definicion.fase), 0) + cantidad
    return [{"fase": fase, "cantidad": cantidad} for fase, cantidad in sorted(fases.items())]


def _requieren_atencion(envios: list[dict], hoy: dt.date) -> dict:
    """Lo que un despachador necesita ver al abrir el sistema.

    No es un resumen: son las tres listas sobre las que hay que hacer algo hoy.
    """
    finales = {str(d.estado) for d in CATALOGO if d.final}

    sin_asignar = [e for e in envios if e.get("estado") == str(Estado.CREADO)]
    con_incidencia = [e for e in envios if e.get("estado") == str(Estado.INCIDENCIA)]

    # Un envio abierto cuya ultima actualizacion es de hace mas de dos dias esta
    # detenido aunque su estado no lo diga. Es el caso que se pierde de vista.
    estancados = [
        e
        for e in envios
        if e.get("estado") not in finales
        and (_fecha(e.get("actualizado_en")) or hoy) <= hoy - dt.timedelta(days=2)
    ]

    return {
        "sin_asignar": len(sin_asignar),
        "con_incidencia": len(con_incidencia),
        "estancados": len(estancados),
        "detalle_estancados": [
            {
                "envio_id": e["envio_id"],
                "estado": e.get("estado"),
                "actualizado_en": e.get("actualizado_en"),
                "destinatario": (e.get("destinatario") or {}).get("nombre", ""),
            }
            for e in sorted(estancados, key=lambda x: x.get("actualizado_en", ""))[:10]
        ],
    }


def _serie_diaria(envios: list[dict], desde: dt.date, hasta: dt.date) -> list[dict]:
    """Creados y entregados por dia, con los dias vacios incluidos.

    Omitir los dias sin movimiento comprime el eje y hace parecer continua una
    operacion que tuvo un fin de semana en medio.
    """
    creados: Counter = Counter()
    entregados: Counter = Counter()

    for envio in envios:
        creado = _fecha(envio.get("creado_en"))
        if creado and desde <= creado <= hasta:
            creados[creado] += 1
        if envio.get("estado") == str(Estado.ENTREGADO):
            cerrado = _fecha(envio.get("actualizado_en"))
            if cerrado and desde <= cerrado <= hasta:
                entregados[cerrado] += 1

    serie = []
    dia = desde
    while dia <= hasta:
        serie.append(
            {
                "fecha": dia.isoformat(),
                "creados": creados.get(dia, 0),
                "entregados": entregados.get(dia, 0),
            }
        )
        dia += dt.timedelta(days=1)
    return serie


def _resumen_equipo(usuarios: list[dict]) -> dict:
    activos = [u for u in usuarios if u.get("activo", True)]
    por_grupo: Counter = Counter()
    for usuario in activos:
        for grupo in usuario.get("grupos", []):
            por_grupo[grupo] += 1
    return {
        "usuarios": len(usuarios),
        "activos": len(activos),
        "por_grupo": [
            {"grupo": str(grupo), "cantidad": por_grupo.get(str(grupo), 0)} for grupo in Grupo
        ],
    }
