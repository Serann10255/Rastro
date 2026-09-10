"""Microservicio de evidencias de entrega (REQ-05).

Las evidencias no atraviesan el servicio. El conductor pide un enlace
prefirmado de vigencia limitada, carga el archivo directamente contra el
almacenamiento y despues confirma la carga. La confirmacion no cree al cliente:
consulta las propiedades del objeto almacenado y solo entonces asocia la
evidencia al envio.

Esa comprobacion es la diferencia entre registrar que alguien dijo haber
cargado una foto y acreditar que la foto esta guardada y cifrada.
"""

from __future__ import annotations

from fastapi import Depends

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.dominio import cargar_envio
from rastro_core.errors import NoEncontradoError, ValidacionError
from rastro_core.http import Contexto, contexto_actual, crear_app, obtener_almacen
from rastro_core.ids import marca_tiempo
from rastro_core.models import SolicitarEvidenciaSolicitud
from rastro_core.storage import construir_clave

app = crear_app(
    "rastro-evidencias",
    "Emision de enlaces prefirmados y confirmacion de evidencias cifradas.",
)


@app.post(
    "/envios/{envio_id}/evidencias",
    status_code=201,
    tags=["evidencias"],
    summary="Solicitar enlace prefirmado de carga",
)
async def solicitar_enlace(
    envio_id: str,
    solicitud: SolicitarEvidenciaSolicitud,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Devuelve un enlace de escritura acotado al prefijo de la organizacion."""
    ctx.exigir(Operacion.EVIDENCIA_CARGAR, recurso=f"envio/{envio_id}")
    cargar_envio(ctx, envio_id, Operacion.EVIDENCIA_CARGAR)

    enlace = obtener_almacen().enlace_de_carga(
        org_id=ctx.org_id, envio_id=envio_id, tipo_contenido=solicitud.tipo_contenido
    )

    ctx.registrar(
        accion=Operacion.EVIDENCIA_CARGAR,
        recurso=f"envio/{envio_id}/evidencia/{enlace['evidencia_id']}",
        resultado=Resultado.ALLOW,
        detalle={
            "fase": "enlace_emitido",
            "tipo_contenido": solicitud.tipo_contenido,
            "vigencia_segundos": enlace["vigencia_segundos"],
            "nombre_original": solicitud.nombre_archivo,
        },
    )
    return enlace


@app.post(
    "/envios/{envio_id}/evidencias/{evidencia_id}/confirmacion",
    tags=["evidencias"],
    summary="Confirmar que la evidencia quedo almacenada",
)
async def confirmar_carga(
    envio_id: str,
    evidencia_id: str,
    tipo_contenido: str = "image/jpeg",
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """Comprueba el objeto en el almacenamiento antes de asociarlo al envio."""
    ctx.exigir(Operacion.EVIDENCIA_CARGAR, recurso=f"envio/{envio_id}")
    envio = cargar_envio(ctx, envio_id, Operacion.EVIDENCIA_CARGAR)

    clave = construir_clave(ctx.org_id, envio_id, evidencia_id, tipo_contenido)
    almacen = obtener_almacen()
    if not almacen.existe(org_id=ctx.org_id, clave=clave):
        ctx.registrar(
            accion=Operacion.EVIDENCIA_CARGAR,
            recurso=f"envio/{envio_id}/evidencia/{evidencia_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "objeto_no_encontrado_en_almacenamiento", "clave": clave},
        )
        raise ValidacionError("La evidencia no esta en el almacenamiento; la carga no se completo.")

    propiedades = almacen.describir_objeto(org_id=ctx.org_id, clave=clave)

    evidencias = list(envio.get("evidencias") or ())
    if evidencia_id not in evidencias:
        evidencias.append(evidencia_id)
    envio["evidencias"] = evidencias
    envio["actualizado_en"] = marca_tiempo()
    ctx.repositorio.actualizar_envio(envio)

    ctx.registrar(
        accion=Operacion.EVIDENCIA_CARGAR,
        recurso=f"envio/{envio_id}/evidencia/{evidencia_id}",
        resultado=Resultado.ALLOW,
        detalle={
            "fase": "carga_confirmada",
            "clave": clave,
            "cifrado": propiedades.get("cifrado"),
            "tamano": propiedades.get("tamano"),
        },
    )
    return {"evidencia_id": evidencia_id, "propiedades": propiedades, "envio": envio}


@app.get(
    "/envios/{envio_id}/evidencias",
    tags=["evidencias"],
    summary="Listar evidencias con enlace de descarga",
)
async def listar_evidencias(
    envio_id: str,
    tipo_contenido: str = "image/jpeg",
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    """La descarga no la puede pedir el conductor: carga evidencia, no la consulta."""
    ctx.exigir(Operacion.EVIDENCIA_DESCARGAR, recurso=f"envio/{envio_id}")
    envio = cargar_envio(ctx, envio_id, Operacion.EVIDENCIA_DESCARGAR)

    almacen = obtener_almacen()
    evidencias = []
    for evidencia_id in envio.get("evidencias") or ():
        clave = construir_clave(ctx.org_id, envio_id, evidencia_id, tipo_contenido)
        try:
            propiedades = almacen.describir_objeto(org_id=ctx.org_id, clave=clave)
        except NoEncontradoError:
            continue
        except Exception:  # noqa: BLE001 - el objeto pudo eliminarse fuera del sistema
            propiedades = {"clave": clave, "estado": "no_recuperable"}
        evidencias.append(
            {
                "evidencia_id": evidencia_id,
                "propiedades": propiedades,
                "url_descarga": almacen.enlace_de_descarga(org_id=ctx.org_id, clave=clave),
            }
        )

    ctx.registrar(
        accion=Operacion.EVIDENCIA_DESCARGAR,
        recurso=f"envio/{envio_id}",
        resultado=Resultado.ALLOW,
        detalle={"evidencias": len(evidencias)},
    )
    return {"envio_id": envio_id, "evidencias": evidencias}
