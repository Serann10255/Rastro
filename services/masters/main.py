"""Microservicio de datos maestros: tiendas, clientes y transportistas.

Son los catalogos sobre los que se apoya la operacion. Un envio no se registra
en el vacio: sale de una tienda, lo despacha un cliente y lo mueve un
transportista, y esos tres deben existir antes.

Lectura y escritura tienen permisos distintos y es deliberado: el despachador
necesita consultar las tiendas para registrar un envio, pero cambiar la
direccion de una tienda afecta a toda la operacion y corresponde al
administrador.
"""

from __future__ import annotations

from fastapi import Depends
from pydantic import BaseModel, Field

from rastro_core.audit import Resultado
from rastro_core.authz import Operacion
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.maestros import RepositorioMaestros, TipoTienda, TipoTransportista
from rastro_core.state_machine import catalogo_publico

app = crear_app(
    "rastro-maestros",
    "Tiendas, clientes y transportistas de la organizacion.",
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


# --------------------------------------------------------------------------- #
# Contratos
# --------------------------------------------------------------------------- #


class TiendaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    codigo: str = Field(default="", max_length=60)
    tipo: TipoTienda = TipoTienda.TIENDA
    direccion: str = Field(default="", max_length=200)
    ciudad: str = Field(min_length=2, max_length=80)
    departamento: str = Field(min_length=2, max_length=80)
    telefono: str = Field(default="", max_length=40)
    responsable: str = Field(default="", max_length=120)
    activa: bool = True


class ClienteEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    correo: str = Field(default="", max_length=160)
    telefono: str = Field(default="", max_length=40)
    documento: str = Field(default="", max_length=40)
    direccion: str = Field(default="", max_length=200)
    ciudad: str = Field(default="", max_length=80)
    departamento: str = Field(default="", max_length=80)
    activo: bool = True


class ModuloEntrada(BaseModel):
    """Solo lo que un administrador puede cambiar de un modulo.

    El nombre, la ruta y los grupos no se editan desde aqui: describen el
    sistema, no la decision de la empresa. Lo que la empresa decide es si el
    modulo esta encendido y, cuando no lo esta, por que.
    """

    disponible: bool
    motivo: str = Field(default="", max_length=400)


class TransportistaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    correo: str = Field(default="", max_length=160)
    telefono: str = Field(default="", max_length=40)
    tipo: TipoTransportista = TipoTransportista.TERCERO
    nit: str = Field(default="", max_length=40)
    ciudad: str = Field(default="", max_length=80)
    departamento: str = Field(default="", max_length=80)
    activo: bool = True


# --------------------------------------------------------------------------- #
# Catalogo de estados
# --------------------------------------------------------------------------- #


@app.get("/catalogos/estados", tags=["catalogos"], summary="Catalogo de estados con su codigo")
async def estados() -> dict:
    """El catalogo completo, con codigo numerico, fase y descripcion.

    Se sirve desde aqui para que la interfaz y los archivos de intercambio no lo
    dupliquen: un catalogo copiado en el cliente se desincroniza en cuanto se
    anade un estado, y el sintoma es que la pantalla muestra un estado en blanco
    sin decir por que.
    """
    return {"estados": catalogo_publico()}


# --------------------------------------------------------------------------- #
# Modulos de la organizacion
# --------------------------------------------------------------------------- #


@app.get("/catalogos/modulos", tags=["catalogos"], summary="Modulos de la organizacion")
async def modulos(ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Que modulos tiene esta organizacion y cuales no, con el motivo.

    La lista sale de la tabla y no del codigo de la interfaz. Que una empresa
    tenga contratada la auditoria y otra no es un dato de la empresa; escribirlo
    en la pantalla obligaria a recompilar el sitio para dar de alta un modulo, y
    haria imposible que dos organizaciones vieran cosas distintas.
    """
    ctx.exigir(Operacion.MAESTRO_CONSULTAR, recurso="modulo/lista")
    registros = maestros().listar_modulos(ctx.org_id)
    return {"modulos": registros, "total": len(registros)}


@app.post("/catalogos/modulos/{clave}", tags=["catalogos"], summary="Habilitar o apagar un modulo")
async def actualizar_modulo(
    clave: str, entrada: ModuloEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    """El administrador enciende o apaga un modulo de su organizacion.

    Apagar exige decir por que: un modulo ausente sin motivo parece un olvido y
    nadie sabe si falta por decision o por descuido.
    """
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"modulo/{clave}")
    actual = maestros().obtener_modulo(ctx.org_id, clave)

    datos = {**actual, "disponible": entrada.disponible, "motivo": entrada.motivo}
    modulo = maestros().guardar_modulo(ctx.org_id, datos)

    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"modulo/{clave}",
        resultado=Resultado.ALLOW,
        detalle={"disponible": modulo["disponible"], "motivo": modulo["motivo"]},
    )
    return {"modulo": modulo}


# --------------------------------------------------------------------------- #
# Tiendas
# --------------------------------------------------------------------------- #


@app.get("/tiendas", tags=["tiendas"], summary="Listar tiendas")
async def listar_tiendas(ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_CONSULTAR, recurso="tienda/lista")
    tiendas = maestros().listar_tiendas(ctx.org_id)
    return {"tiendas": tiendas, "total": len(tiendas)}


@app.post("/tiendas", status_code=201, tags=["tiendas"], summary="Crear una tienda")
async def crear_tienda(entrada: TiendaEntrada, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso="tienda/nueva")
    tienda = maestros().guardar_tienda(ctx.org_id, entrada.model_dump(mode="json"))
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"tienda/{tienda['tienda_id']}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "crear", "nombre": tienda["nombre"]},
    )
    return {"tienda": tienda}


@app.post("/tiendas/{tienda_id}", tags=["tiendas"], summary="Actualizar una tienda")
async def actualizar_tienda(
    tienda_id: str, entrada: TiendaEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"tienda/{tienda_id}")
    actual = maestros().obtener_tienda(ctx.org_id, tienda_id)
    tienda = maestros().guardar_tienda(
        ctx.org_id,
        {**actual, **entrada.model_dump(mode="json"), "tienda_id": tienda_id},
    )
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"tienda/{tienda_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "actualizar"},
    )
    return {"tienda": tienda}


@app.post("/tiendas/{tienda_id}/eliminar", tags=["tiendas"], summary="Eliminar una tienda")
async def eliminar_tienda(tienda_id: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"tienda/{tienda_id}")
    tienda = maestros().obtener_tienda(ctx.org_id, tienda_id)
    maestros().eliminar_tienda(ctx.org_id, tienda_id)
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"tienda/{tienda_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "eliminar", "nombre": tienda["nombre"]},
    )
    return {"eliminada": True}


# --------------------------------------------------------------------------- #
# Clientes
# --------------------------------------------------------------------------- #


@app.get("/clientes", tags=["clientes"], summary="Listar clientes")
async def listar_clientes(ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_CONSULTAR, recurso="cliente/lista")
    clientes = maestros().listar_clientes(ctx.org_id)
    return {"clientes": clientes, "total": len(clientes)}


@app.post("/clientes", status_code=201, tags=["clientes"], summary="Crear un cliente")
async def crear_cliente(entrada: ClienteEntrada, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso="cliente/nuevo")
    cliente = maestros().guardar_cliente(ctx.org_id, entrada.model_dump(mode="json"))
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"cliente/{cliente['cliente_id']}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "crear", "nombre": cliente["nombre"]},
    )
    return {"cliente": cliente}


@app.post("/clientes/{cliente_id}", tags=["clientes"], summary="Actualizar un cliente")
async def actualizar_cliente(
    cliente_id: str, entrada: ClienteEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"cliente/{cliente_id}")
    actual = maestros().obtener_cliente(ctx.org_id, cliente_id)
    cliente = maestros().guardar_cliente(
        ctx.org_id, {**actual, **entrada.model_dump(mode="json"), "cliente_id": cliente_id}
    )
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"cliente/{cliente_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "actualizar"},
    )
    return {"cliente": cliente}


@app.post("/clientes/{cliente_id}/eliminar", tags=["clientes"], summary="Eliminar un cliente")
async def eliminar_cliente(cliente_id: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"cliente/{cliente_id}")
    maestros().obtener_cliente(ctx.org_id, cliente_id)
    maestros().eliminar_cliente(ctx.org_id, cliente_id)
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"cliente/{cliente_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "eliminar"},
    )
    return {"eliminado": True}


# --------------------------------------------------------------------------- #
# Transportistas
# --------------------------------------------------------------------------- #


@app.get("/transportistas", tags=["transportistas"], summary="Listar transportistas")
async def listar_transportistas(ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.MAESTRO_CONSULTAR, recurso="transportista/lista")
    transportistas = maestros().listar_transportistas(ctx.org_id)
    return {"transportistas": transportistas, "total": len(transportistas)}


@app.post(
    "/transportistas", status_code=201, tags=["transportistas"], summary="Crear un transportista"
)
async def crear_transportista(
    entrada: TransportistaEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso="transportista/nuevo")
    transportista = maestros().guardar_transportista(ctx.org_id, entrada.model_dump(mode="json"))
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"transportista/{transportista['transportista_id']}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "crear", "nombre": transportista["nombre"]},
    )
    return {"transportista": transportista}


@app.post(
    "/transportistas/{transportista_id}",
    tags=["transportistas"],
    summary="Actualizar un transportista",
)
async def actualizar_transportista(
    transportista_id: str,
    entrada: TransportistaEntrada,
    ctx: Contexto = Depends(contexto_actual),
) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"transportista/{transportista_id}")
    actual = maestros().obtener_transportista(ctx.org_id, transportista_id)
    transportista = maestros().guardar_transportista(
        ctx.org_id,
        {**actual, **entrada.model_dump(mode="json"), "transportista_id": transportista_id},
    )
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"transportista/{transportista_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "actualizar"},
    )
    return {"transportista": transportista}


@app.post(
    "/transportistas/{transportista_id}/eliminar",
    tags=["transportistas"],
    summary="Eliminar un transportista",
)
async def eliminar_transportista(
    transportista_id: str, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.MAESTRO_EDITAR, recurso=f"transportista/{transportista_id}")
    maestros().obtener_transportista(ctx.org_id, transportista_id)
    maestros().eliminar_transportista(ctx.org_id, transportista_id)
    ctx.registrar(
        accion=Operacion.MAESTRO_EDITAR,
        recurso=f"transportista/{transportista_id}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "eliminar"},
    )
    return {"eliminado": True}
