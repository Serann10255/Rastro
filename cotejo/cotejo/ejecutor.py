"""Ejecutor del catalogo de controles.

Recorre el catalogo completo en una sola invocacion y sin intervencion manual
(REQ-01 de Cotejo). Por cada control produce un papel de trabajo con el
procedimiento, la salida literal, la marca de tiempo, la identidad de sesion y
la huella criptografica del archivo de evidencia.

Un fallo del ejecutor sobre un control no detiene el resto: el control queda
marcado como NO_EJECUTADA con su motivo. Es la mitigacion del riesgo R-05 del
documento: una ejecucion interrumpida a la mitad produciria papeles incompletos
que podrian confundirse con pruebas fallidas.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

import yaml

from .contexto import Contexto
from .modelos import Conclusion, Control, PapelDeTrabajo, ResultadoPrueba, marca_tiempo
from .papeles import AlmacenPapeles
from .pruebas import cumplimiento, integridad, sustantiva

RAIZ_COTEJO = Path(__file__).resolve().parents[1]
CATALOGO_POR_OMISION = RAIZ_COTEJO / "catalogo" / "controles.yaml"

#: Nombre declarado en el catalogo -> funcion que lo implementa. El catalogo no
#: importa codigo: nombra una prueba y este mapa la resuelve. Asi un catalogo
#: mal formado no puede ejecutar nada arbitrario.
PRUEBAS: dict[str, Callable[[Contexto], ResultadoPrueba]] = {
    "cumplimiento.registro_de_actividad": cumplimiento.registro_de_actividad,
    "cumplimiento.cifrado_de_evidencias": cumplimiento.cifrado_de_evidencias,
    "cumplimiento.acceso_publico_bloqueado": cumplimiento.acceso_publico_bloqueado,
    "cumplimiento.versionado_activo": cumplimiento.versionado_activo,
    "sustantiva.autorizacion_por_rol": sustantiva.autorizacion_por_rol,
    "sustantiva.aislamiento_entre_organizaciones": sustantiva.aislamiento_entre_organizaciones,
    "sustantiva.transiciones_invalidas": sustantiva.transiciones_invalidas,
    "integridad.cadena_de_bitacora": integridad.cadena_de_bitacora,
}


class ErrorCatalogo(Exception):
    """El catalogo no es utilizable. Sin criterio declarado no hay auditoria."""


def cargar_catalogo(ruta: Path | None = None) -> dict:
    """Carga y valida la matriz de controles.

    Se valida antes de ejecutar nada: un control cuyo criterio no este declarado
    de antemano permitiria acomodar el criterio al resultado, que es justamente
    lo que el programa existe para evitar.
    """
    ruta = Path(ruta or CATALOGO_POR_OMISION)
    if not ruta.is_file():
        raise ErrorCatalogo(f"No existe el catalogo de controles en {ruta}")

    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict) or "controles" not in datos:
        raise ErrorCatalogo("El catalogo debe declarar una lista 'controles'.")

    controles = []
    identificadores = set()
    for entrada in datos["controles"]:
        control = Control.desde_dict(entrada)
        if control.id in identificadores:
            raise ErrorCatalogo(f"El control {control.id} esta declarado dos veces.")
        if control.prueba not in PRUEBAS:
            raise ErrorCatalogo(
                f"El control {control.id} nombra la prueba '{control.prueba}', "
                "que no esta implementada."
            )
        # Un control que solo sabe decirse en vocabulario tecnico no se puede
        # discutir con quien decide, y un hallazgo que nadie entiende no se
        # corrige. La version llana se exige igual que el criterio, y por la
        # misma razon: escribirla despues permitiria acomodarla al resultado.
        for campo in ("pregunta", "en_simple", "si_falla"):
            if not getattr(control, campo):
                raise ErrorCatalogo(
                    f"El control {control.id} no declara '{campo}'. Todo control "
                    "debe poder explicarse sin vocabulario tecnico."
                )
        identificadores.add(control.id)
        controles.append(control)

    if not controles:
        raise ErrorCatalogo("El catalogo no declara ningun control.")

    datos["controles"] = controles
    return datos


def nuevo_id_ejecucion() -> str:
    return f"{marca_tiempo().replace(':', '').replace('.', '').replace('-', '')}-{uuid.uuid4().hex[:6]}"


def ejecutar(
    ctx: Contexto,
    catalogo: dict,
    *,
    ejecucion_id: str | None = None,
    base_papeles: Path | None = None,
    solo: list[str] | None = None,
) -> tuple[AlmacenPapeles, dict]:
    """Recorre el catalogo y devuelve el almacen de papeles y los metadatos."""
    ejecucion_id = ejecucion_id or nuevo_id_ejecucion()
    almacen = AlmacenPapeles(ejecucion_id, base=base_papeles)
    identidad = ctx.identidad_de_sesion()
    iniciado = marca_tiempo()

    controles = [c for c in catalogo["controles"] if not solo or c.id in solo]

    for control in controles:
        inicio = marca_tiempo()
        prueba = PRUEBAS[control.prueba]
        try:
            resultado = prueba(ctx)
        except Exception as exc:  # noqa: BLE001 - un control no tumba la ejecucion
            resultado = ResultadoPrueba.no_ejecutada(
                f"La prueba lanzo {type(exc).__name__}: {exc}", control.procedimiento
            )

        almacen.guardar(
            PapelDeTrabajo(
                ejecucion_id=ejecucion_id,
                control_id=control.id,
                control=control.control,
                pregunta=control.pregunta,
                en_simple=control.en_simple,
                si_falla=control.si_falla,
                marco=control.marco,
                tipo=control.tipo,
                procedimiento=control.procedimiento,
                criterio=control.criterio,
                evidencia_esperada=control.evidencia_esperada,
                conclusion=resultado.conclusion,
                resumen=resultado.resumen,
                observaciones=[o.como_dict() for o in resultado.observaciones],
                detalle=resultado.detalle,
                identidad_ejecucion=identidad,
                iniciado_en=inicio,
                terminado_en=marca_tiempo(),
            )
        )

    metadatos = {
        "sistema_auditado": catalogo.get("sistema_auditado", "Rastro"),
        "version_catalogo": catalogo.get("version", "sin version"),
        # Viaja con la ejecucion para que el informe se explique solo, sin el
        # catalogo de su epoca al lado.
        "que_es_esto": " ".join(str(catalogo.get("que_es_esto", "")).split()),
        "entorno": ctx.entorno,
        "url_api": ctx.url_api,
        "region": ctx.region,
        "identidad_ejecucion": identidad,
        "iniciado_en": iniciado,
        "controles_ejecutados": len(controles),
        "controles_del_catalogo": len(catalogo["controles"]),
    }
    almacen.cerrar(metadatos)
    return almacen, metadatos


def cobertura(almacen: AlmacenPapeles, catalogo: dict) -> dict:
    """Cuanto del catalogo se ejecuto realmente.

    Un informe que no distinga entre "conforme" y "no ejecutada" transmitiria
    una cobertura mayor que la real, que es el riesgo R-04 del documento.
    """
    total = len(catalogo["controles"])
    por_conclusion = almacen.resumen()
    ejecutados = total - por_conclusion.get(str(Conclusion.NO_EJECUTADA), 0)
    return {
        "controles_del_catalogo": total,
        "controles_con_resultado": ejecutados,
        "conformes": por_conclusion.get(str(Conclusion.CONFORME), 0),
        "desviados": por_conclusion.get(str(Conclusion.DESVIADO), 0),
        "no_ejecutados": por_conclusion.get(str(Conclusion.NO_EJECUTADA), 0),
        "cobertura": f"{ejecutados}/{total}",
    }
