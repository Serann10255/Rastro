"""Operaciones de dominio compartidas por los microservicios de envio.

El acceso a un envio pasa siempre por ``cargar_envio``. Esa funcion aplica en un
solo lugar los dos controles que el documento exige sobre cada lectura: el
filtro por organizacion (REQ-06) y la restriccion del conductor a los envios que
tiene asignados. Que exista un unico camino es lo que hace verificable el
aislamiento: no hay una segunda ruta que pueda olvidarlo.
"""

from __future__ import annotations

from typing import Any

from .audit import Resultado
from .authz import Operacion
from .errors import NoEncontradoError
from .http import Contexto
from .ids import marca_tiempo, nuevo_id_envio, nuevo_id_evento
from .models import CrearEnvioSolicitud, Envio, Evento
from .state_machine import Estado, codigo_de


def cargar_envio(ctx: Contexto, envio_id: str, operacion: Operacion) -> dict:
    """Recupera un envio de la organizacion del token, o falla como si no existiera.

    Un usuario de la organizacion A que pida un envio de la organizacion B
    recibe la misma respuesta que si el identificador no existiera, y el intento
    queda registrado con resultado DENY. Responder 403 confirmaria que el
    recurso existe, que es informacion que el solicitante no deberia obtener.
    """
    try:
        envio = ctx.repositorio.obtener_envio(ctx.org_id, envio_id)
    except NoEncontradoError:
        ctx.registrar(
            accion=operacion,
            recurso=f"envio/{envio_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "fuera_de_organizacion_o_inexistente"},
        )
        raise

    if ctx.exige_envio_propio(operacion) and envio.get("conductor_sub") != ctx.identidad.sub:
        ctx.registrar(
            accion=operacion,
            recurso=f"envio/{envio_id}",
            resultado=Resultado.DENY,
            detalle={"motivo": "envio_no_asignado_al_conductor"},
        )
        raise NoEncontradoError("El envio no existe.", {"envio_id": envio_id})

    return envio


def construir_envio(
    ctx: Contexto, solicitud: CrearEnvioSolicitud, *, referencias: dict | None = None
) -> dict:
    """REQ-01: crea el registro maestro en estado CREADO con identificador no predecible.

    ``referencias`` trae los nombres de tienda, cliente y transportista ya
    resueltos. Se guardan junto al identificador -y no solo el identificador-
    porque un envio es un documento historico: si manana se renombra la tienda,
    el envio debe seguir diciendo de donde salio en su momento.
    """
    ahora = marca_tiempo()
    referencias = referencias or {}
    envio = Envio(
        envio_id=nuevo_id_envio(),
        org_id=ctx.org_id,
        estado=Estado.CREADO,
        codigo_estado=codigo_de(Estado.CREADO),
        creado_en=ahora,
        actualizado_en=ahora,
        creado_por=ctx.identidad.sub,
        origen=solicitud.origen,
        destino=solicitud.destino,
        destinatario=solicitud.destinatario,
        descripcion=solicitud.descripcion,
        orden_compra=solicitud.orden_compra,
        tienda_id=solicitud.tienda_id,
        tienda_nombre=referencias.get("tienda_nombre", ""),
        cliente_id=solicitud.cliente_id,
        cliente_nombre=referencias.get("cliente_nombre", ""),
        transportista_id=solicitud.transportista_id,
        transportista_nombre=referencias.get("transportista_nombre", ""),
        estacion_actual=referencias.get("tienda_nombre", ""),
        peso_kg=solicitud.peso_kg,
        valor_declarado=solicitud.valor_declarado,
        bultos=solicitud.bultos,
        fecha_estimada=solicitud.fecha_estimada,
        observaciones=solicitud.observaciones,
    )
    return envio.model_dump(mode="json")


def construir_evento(
    ctx: Contexto,
    *,
    envio: dict,
    estado: Estado,
    estado_anterior: Estado | str | None,
    ubicacion: dict | None = None,
    nota: str = "",
    evidencia_id: str | None = None,
) -> dict:
    """REQ-02: el evento conserva estado, ubicacion, autor y marca de tiempo.

    La marca de tiempo es la del servidor. La del dispositivo del mensajero es
    manipulable y por lo tanto no sirve como evidencia.
    """
    evento = Evento(
        evento_id=nuevo_id_evento(),
        envio_id=envio["envio_id"],
        org_id=ctx.org_id,
        estado=Estado(estado),
        codigo_estado=codigo_de(estado),
        estado_anterior=Estado(estado_anterior) if estado_anterior else None,
        ts=marca_tiempo(),
        actor_sub=ctx.identidad.sub,
        actor_email=ctx.identidad.email,
        actor_grupos=tuple(ctx.identidad.grupos),
        ubicacion=ubicacion,
        nota=nota,
        evidencia_id=evidencia_id,
    )
    return evento.model_dump(mode="json")


def historico_autenticado(ctx: Contexto, envio_id: str) -> dict:
    """Registro maestro y eventos en orden cronologico, dentro de la organizacion."""
    envio = cargar_envio(ctx, envio_id, Operacion.ENVIO_CONSULTAR)
    eventos = ctx.repositorio.listar_eventos(ctx.org_id, envio_id)
    ctx.registrar(
        accion=Operacion.ENVIO_CONSULTAR,
        recurso=f"envio/{envio_id}",
        resultado=Resultado.ALLOW,
        detalle={"eventos": len(eventos)},
    )
    return {"envio": envio, "eventos": eventos}


def resumen_para_lista(envio: dict) -> dict[str, Any]:
    """Vista reducida para el listado del despachador y del conductor."""
    return {
        "envio_id": envio.get("envio_id"),
        "estado": envio.get("estado"),
        "codigo_estado": envio.get("codigo_estado", 10),
        "creado_en": envio.get("creado_en"),
        "actualizado_en": envio.get("actualizado_en"),
        "fecha_estimada": envio.get("fecha_estimada", ""),
        "conductor_sub": envio.get("conductor_sub"),
        "conductor_nombre": envio.get("conductor_nombre", ""),
        "destinatario": (envio.get("destinatario") or {}).get("nombre", ""),
        "destino": (envio.get("destino") or {}).get("linea", ""),
        "ciudad_destino": (envio.get("destino") or {}).get("ciudad", ""),
        "descripcion": envio.get("descripcion", ""),
        "orden_compra": envio.get("orden_compra", ""),
        "cliente_nombre": envio.get("cliente_nombre", ""),
        "tienda_nombre": envio.get("tienda_nombre", ""),
        "transportista_nombre": envio.get("transportista_nombre", ""),
        "estacion_actual": envio.get("estacion_actual", ""),
        "bultos": envio.get("bultos", 1),
    }


def datos_de_etiqueta(envio: dict, empresa: dict) -> dict[str, Any]:
    """Lo que se imprime en una guia.

    Va aparte del resumen porque son necesidades distintas: el listado busca
    reconocer un envio de un vistazo, la etiqueta tiene que permitir entregarlo
    sin abrir el sistema. En la etiqueta no aparece el valor declarado: pegarlo
    por fuera de la caja le dice a cualquiera cuanto vale lo que hay dentro.
    """
    destino = envio.get("destino") or {}
    destinatario = envio.get("destinatario") or {}
    return {
        "envio_id": envio["envio_id"],
        "orden_compra": envio.get("orden_compra", ""),
        "empresa": empresa.get("nombre", ""),
        "empresa_nit": empresa.get("nit", ""),
        "origen": (envio.get("origen") or {}).get("linea", ""),
        "tienda_nombre": envio.get("tienda_nombre", ""),
        "destinatario": destinatario.get("nombre", ""),
        "telefono": destinatario.get("telefono", ""),
        "direccion": destino.get("linea", ""),
        "referencia": destino.get("referencia", ""),
        "ciudad": destino.get("ciudad", ""),
        "bultos": envio.get("bultos", 1),
        "peso_kg": envio.get("peso_kg", 0),
        "descripcion": envio.get("descripcion", ""),
        "fecha_estimada": envio.get("fecha_estimada", ""),
        "creado_en": envio.get("creado_en", ""),
        "transportista": envio.get("transportista_nombre", ""),
    }
