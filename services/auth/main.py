"""Servicio de identidad: usuarios, sesiones y administracion de cuentas.

Sustituye al emisor de demostracion. Ahora las credenciales son reales: las
contrasenas se almacenan derivadas con PBKDF2-HMAC-SHA256 y nunca en claro, la
sesion se compone de un token de acceso corto y uno de refresco revocable, y las
cuentas se administran desde el propio sistema.

Sobre Cognito. En AWS este servicio puede sustituirse por un grupo de usuarios
de Amazon Cognito, que emite tokens con el mismo contrato. La diferencia es que
Cognito no permite administrar los usuarios desde la aplicacion sin permisos que
el laboratorio no concede, de modo que aqui el directorio es propio. La eleccion
se documenta: un despliegue productivo puede quedarse con este servicio o
delegar en Cognito sin tocar el resto del sistema, porque lo unico que los demas
servicios conocen es la forma del token.
"""

from __future__ import annotations

import secrets
import time
from collections import Counter

from fastapi import Depends, Header
from pydantic import BaseModel, Field

from rastro_core.audit import Resultado
from rastro_core.authz import (
    ROLES_INTEGRADOS,
    Grupo,
    Operacion,
    catalogo_de_operaciones,
    esta_autorizado,
    normalizar_grupos,
    operaciones_de,
    rompe_separacion_de_funciones,
    union_de_roles,
    vista_rol,
)
from rastro_core.config import cargar_config
from rastro_core.errors import (
    ConflictoError,
    NoAutenticadoError,
    NoAutorizadoError,
    NoEncontradoError,
    ValidacionError,
)
from rastro_core.http import Contexto, contexto_actual, crear_app, obtener_repositorio
from rastro_core.maestros import (
    RepositorioMaestros,
    normalizar_correo,
    vista_usuario,
)
from rastro_core.passwords import ContrasenaInvalida, derivar, necesita_rederivar, verificar
from rastro_core.passwords import verificar_senuelo
from rastro_core.security import (
    decodificar_refresco,
    emitir_token_de_acceso,
    emitir_token_de_refresco,
    extraer_token,
    identidad_desde_token,
)

app = crear_app(
    "rastro-identidad",
    "Usuarios, sesiones y administracion de cuentas de la organizacion.",
)

#: Numero maximo de sesiones simultaneas por usuario. Sin tope, cada inicio de
#: sesion anadiria un identificador al registro y este creceria sin limite.
MAX_SESIONES = 5

_maestros: RepositorioMaestros | None = None


def maestros() -> RepositorioMaestros:
    global _maestros
    if _maestros is None:
        _maestros = RepositorioMaestros()
    return _maestros


def fijar_maestros(repositorio: RepositorioMaestros) -> None:
    """Sustituye el repositorio. Lo usan las pruebas."""
    global _maestros
    _maestros = repositorio


# --------------------------------------------------------------------------- #
# Contratos
# --------------------------------------------------------------------------- #


class Credenciales(BaseModel):
    correo: str = Field(min_length=5, max_length=160)
    clave: str = Field(min_length=1, max_length=200)


class SolicitudRefresco(BaseModel):
    refresco: str = Field(min_length=10)


class CambioDeClave(BaseModel):
    clave_actual: str = Field(min_length=1, max_length=200)
    clave_nueva: str = Field(min_length=12, max_length=200)


class NuevoUsuario(BaseModel):
    correo: str = Field(min_length=5, max_length=160)
    nombre: str = Field(min_length=2, max_length=120)
    clave: str = Field(min_length=12, max_length=200)
    grupos: list[str] = Field(min_length=1)
    telefono: str = Field(default="", max_length=40)


class RolEntrada(BaseModel):
    clave: str = Field(min_length=2, max_length=40)
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str = Field(default="", max_length=400)
    operaciones: list[str] = Field(min_length=1)


class RolActualizacion(BaseModel):
    """El nombre y los permisos se cambian; la clave no.

    La clave es lo que guardan las cuentas: cambiarla dejaria a cada usuario
    apuntando a un rol que ya no existe.
    """

    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, max_length=400)
    operaciones: list[str] | None = None


class ActualizacionUsuario(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    grupos: list[str] | None = None
    telefono: str | None = Field(default=None, max_length=40)
    activo: bool | None = None


# --------------------------------------------------------------------------- #
# Sesiones
# --------------------------------------------------------------------------- #


def _sesiones_vigentes(usuario: dict) -> list[dict]:
    """Descarta las sesiones caducadas al leerlas.

    Se limpian aqui y no con un proceso aparte porque el unico momento en que
    hace falta que la lista este al dia es cuando se usa.
    """
    ahora = int(time.time())
    return [s for s in (usuario.get("sesiones") or []) if int(s.get("expira", 0)) > ahora]


def _abrir_sesion(usuario: dict) -> tuple[dict, str]:
    """Emite el par de tokens y registra la sesion en el usuario."""
    config = cargar_config()
    sesion_id = secrets.token_urlsafe(16)

    acceso, vigencia_acceso = emitir_token_de_acceso(
        sub=usuario["sub"],
        email=usuario["correo"],
        org_id=usuario["org_id"],
        grupos=usuario["grupos"],
        sesion_id=sesion_id,
        config=config,
    )
    refresco, vigencia_refresco = emitir_token_de_refresco(
        sub=usuario["sub"], org_id=usuario["org_id"], sesion_id=sesion_id, config=config
    )

    sesiones = _sesiones_vigentes(usuario)
    sesiones.append({"sid": sesion_id, "expira": int(time.time()) + vigencia_refresco})
    # Se conservan las mas recientes: pasado el tope, la sesion mas antigua se
    # cierra sola, que es el comportamiento que espera quien cambia de
    # dispositivo con frecuencia.
    usuario["sesiones"] = sorted(sesiones, key=lambda s: s["expira"])[-MAX_SESIONES:]

    return (
        {
            "token": acceso,
            "refresco": refresco,
            "tipo": "Bearer",
            "vigencia_segundos": vigencia_acceso,
            "vigencia_refresco_segundos": vigencia_refresco,
            "usuario": vista_usuario(usuario),
        },
        sesion_id,
    )


# --------------------------------------------------------------------------- #
# Inicio de sesion
# --------------------------------------------------------------------------- #


@app.post("/auth/token", tags=["sesion"], summary="Iniciar sesion")
async def iniciar_sesion(credenciales: Credenciales) -> dict:
    """Verifica las credenciales y abre una sesion.

    Ante un fallo, la respuesta es la misma tanto si el usuario no existe como
    si la clave es incorrecta o la cuenta esta inactiva. Y cuando el usuario no
    existe se verifica igualmente contra un senuelo, para que el tiempo de
    respuesta no delate la diferencia: sin eso, medir la latencia permite
    enumerar las cuentas del sistema.
    """
    try:
        correo = normalizar_correo(credenciales.correo)
    except ValidacionError:
        verificar_senuelo(credenciales.clave)
        raise NoAutenticadoError("Correo o clave incorrectos.") from None

    registro = maestros().buscar_usuario_por_correo(correo)

    if registro is None:
        verificar_senuelo(credenciales.clave)
        raise NoAutenticadoError("Correo o clave incorrectos.")

    if not verificar(credenciales.clave, registro.get("hash_clave", "")):
        _registrar_intento(registro, "clave_incorrecta")
        raise NoAutenticadoError("Correo o clave incorrectos.")

    if not registro.get("activo", True):
        _registrar_intento(registro, "cuenta_inactiva")
        raise NoAutenticadoError("Correo o clave incorrectos.")

    # El unico momento en que el sistema tiene la clave en claro y puede
    # rederivarla con parametros mas fuertes sin pedirsela al usuario.
    if necesita_rederivar(registro["hash_clave"]):
        registro["hash_clave"] = derivar(credenciales.clave)

    sesion, sesion_id = _abrir_sesion(registro)
    maestros().guardar_usuario(registro)
    maestros().registrar_acceso(registro["org_id"], correo)

    _registrar_en_bitacora(
        registro,
        accion="sesion:iniciar",
        resultado=Resultado.ALLOW,
        detalle={"sid": sesion_id},
    )
    return sesion


@app.post("/auth/refrescar", tags=["sesion"], summary="Renovar el token de acceso")
async def refrescar(solicitud: SolicitudRefresco) -> dict:
    """Cambia un token de refresco por un par nuevo.

    El refresco se rota: el anterior deja de valer. Asi, si alguien roba uno y
    lo usa, el legitimo deja de funcionar y el robo se nota, en lugar de
    convivir en silencio con el atacante.

    Los grupos se releen del registro del usuario y no del token, de modo que un
    cambio de rol surte efecto en la siguiente renovacion.
    """
    claims = decodificar_refresco(solicitud.refresco)
    org_id = str(claims.get("custom:org_id") or "")
    sesion_id = str(claims.get("sid"))

    registro = _usuario_por_sub(org_id, str(claims.get("sub")))
    if registro is None or not registro.get("activo", True):
        raise NoAutenticadoError("La sesion ya no es valida.")

    if not any(s["sid"] == sesion_id for s in _sesiones_vigentes(registro)):
        # La sesion se cerro, caduco o el refresco ya se uso: en los tres casos
        # hay que volver a autenticarse.
        raise NoAutenticadoError("La sesion fue cerrada. Vuelva a entrar.")

    registro["sesiones"] = [s for s in _sesiones_vigentes(registro) if s["sid"] != sesion_id]
    sesion, _nuevo_sid = _abrir_sesion(registro)
    maestros().guardar_usuario(registro)
    return sesion


@app.post("/auth/salir", tags=["sesion"], summary="Cerrar la sesion actual")
async def cerrar_sesion(
    authorization: str | None = Header(default=None), todas: bool = False
) -> dict:
    """Revoca la sesion en el servidor, no solo en el navegador.

    Borrar el token del cliente basta para el uso normal, pero no si el token ya
    se copio. Revocar la sesion es lo que hace que un cierre signifique algo.
    """
    from rastro_core.security import decodificar_token

    claims = decodificar_token(extraer_token(authorization))
    org_id = str(claims.get("custom:org_id") or "")
    registro = _usuario_por_sub(org_id, str(claims.get("sub")))
    if registro is None:
        return {"cerradas": 0}

    vigentes = _sesiones_vigentes(registro)
    if todas:
        cerradas = len(vigentes)
        registro["sesiones"] = []
    else:
        sesion_id = str(claims.get("sid") or "")
        registro["sesiones"] = [s for s in vigentes if s["sid"] != sesion_id]
        cerradas = len(vigentes) - len(registro["sesiones"])

    maestros().guardar_usuario(registro)
    _registrar_en_bitacora(
        registro, accion="sesion:cerrar", resultado=Resultado.ALLOW, detalle={"cerradas": cerradas}
    )
    return {"cerradas": cerradas}


@app.get("/auth/yo", tags=["sesion"], summary="Identidad y empresa de la sesion")
async def identidad_de_sesion(authorization: str | None = Header(default=None)) -> dict:
    """Devuelve al usuario y su empresa, que es lo que la interfaz necesita al
    arrancar para saber en nombre de quien se opera."""
    identidad = identidad_desde_token(extraer_token(authorization))
    registro = maestros().obtener_usuario(identidad.org_id, identidad.email)
    empresa = maestros().obtener_empresa(identidad.org_id)

    # Los permisos efectivos, resueltos con los roles de la organizacion. La
    # interfaz los necesita para decidir que ofrecer: con roles personalizables,
    # preguntar por el nombre del rol dejo de servir -un rol que la empresa
    # invento manana no aparece en ninguna lista escrita en la pantalla-.
    #
    # No son un control. El servidor decide en cada operacion; esto solo evita
    # ofrecer botones que van a responder 403.
    definiciones = maestros().definiciones_de_rol(identidad.org_id)
    permisos = sorted(str(o) for o in operaciones_de(registro.get("grupos", []), definiciones))

    return {"usuario": vista_usuario(registro), "empresa": empresa, "permisos": permisos}


@app.post("/auth/clave", tags=["sesion"], summary="Cambiar la propia contrasena")
async def cambiar_clave(
    cambio: CambioDeClave, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    registro = maestros().obtener_usuario(ctx.org_id, ctx.identidad.email)

    if not verificar(cambio.clave_actual, registro.get("hash_clave", "")):
        ctx.registrar(
            accion="usuario:cambiar_clave",
            recurso=f"usuario/{ctx.identidad.email}",
            resultado=Resultado.DENY,
            detalle={"motivo": "clave_actual_incorrecta"},
        )
        raise NoAutenticadoError("La contrasena actual no es correcta.")

    if cambio.clave_nueva == cambio.clave_actual:
        raise ValidacionError("La contrasena nueva debe ser distinta de la actual.")

    try:
        registro["hash_clave"] = derivar(cambio.clave_nueva)
    except ContrasenaInvalida as exc:
        raise ValidacionError(str(exc)) from exc

    # Cambiar la contrasena cierra las demas sesiones: si se cambia porque se
    # sospecha que alguien la conoce, dejar sus sesiones abiertas no serviria
    # de nada.
    registro["sesiones"] = [
        s for s in _sesiones_vigentes(registro) if s["sid"] == ctx.identidad.sid
    ]
    maestros().guardar_usuario(registro)

    ctx.registrar(
        accion="usuario:cambiar_clave",
        recurso=f"usuario/{ctx.identidad.email}",
        resultado=Resultado.ALLOW,
        detalle={"sesiones_cerradas": True},
    )
    return {"cambiada": True, "sesiones_cerradas": True}


# --------------------------------------------------------------------------- #
# Administracion de usuarios
# --------------------------------------------------------------------------- #


@app.get("/usuarios", tags=["usuarios"], summary="Usuarios de la organizacion")
async def listar_usuarios(ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.USUARIO_LISTAR, recurso="usuario/lista")
    usuarios = maestros().listar_usuarios(ctx.org_id)
    ctx.registrar(
        accion=Operacion.USUARIO_LISTAR,
        recurso="usuario/lista",
        resultado=Resultado.ALLOW,
        detalle={"devueltos": len(usuarios)},
    )
    return {"usuarios": usuarios, "total": len(usuarios)}


@app.get("/equipo/mensajeros", tags=["usuarios"], summary="Mensajeros de la organizacion")
async def listar_mensajeros(ctx: Contexto = Depends(contexto_actual)) -> dict:
    """A quien se le puede asignar un envio, tomado del directorio.

    Existe porque la pantalla de asignacion necesita saber quien reparte, y esa
    lista no puede estar escrita en la interfaz: el dia que entra un mensajero
    nuevo, nadie va a recompilar el sitio para que aparezca.

    Devuelve menos que ``/usuarios`` -sujeto, nombre y telefono- y por eso lo
    puede pedir un despachador, que no administra cuentas pero si asigna.
    """
    ctx.exigir(Operacion.EQUIPO_CONSULTAR, recurso="equipo/mensajeros")

    mensajeros = [
        {
            "sub": usuario["sub"],
            "nombre": usuario["nombre"],
            "telefono": usuario.get("telefono", ""),
        }
        for usuario in maestros().listar_usuarios(ctx.org_id)
        if usuario.get("activo", True) and str(Grupo.CONDUCTOR) in usuario.get("grupos", [])
    ]
    mensajeros.sort(key=lambda m: m["nombre"])

    ctx.registrar(
        accion=Operacion.EQUIPO_CONSULTAR,
        recurso="equipo/mensajeros",
        resultado=Resultado.ALLOW,
        detalle={"devueltos": len(mensajeros)},
    )
    return {"mensajeros": mensajeros, "total": len(mensajeros)}


@app.post("/usuarios", status_code=201, tags=["usuarios"], summary="Crear un usuario")
async def crear_usuario(nuevo: NuevoUsuario, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Solo el administrador de la organizacion crea cuentas.

    El usuario se crea siempre en la organizacion de quien lo crea: aceptar la
    organizacion como dato de entrada permitiria crear cuentas en otra empresa.
    """
    ctx.exigir(Operacion.USUARIO_CREAR, recurso="usuario/nuevo")

    grupos = _exigir_roles_existentes(ctx, nuevo.grupos)

    correo = normalizar_correo(nuevo.correo)
    if maestros().buscar_usuario_por_correo(correo) is not None:
        ctx.registrar(
            accion=Operacion.USUARIO_CREAR,
            recurso=f"usuario/{correo}",
            resultado=Resultado.DENY,
            detalle={"motivo": "correo_ya_registrado"},
        )
        raise ConflictoError("Ese correo ya esta registrado.")

    try:
        hash_clave = derivar(nuevo.clave)
    except ContrasenaInvalida as exc:
        raise ValidacionError(str(exc)) from exc

    registro = maestros().guardar_usuario(
        {
            "correo": correo,
            "nombre": nuevo.nombre,
            "org_id": ctx.org_id,
            "grupos": sorted(str(g) for g in grupos),
            "hash_clave": hash_clave,
            "telefono": nuevo.telefono,
            "activo": True,
        },
        exigir_nuevo=True,
    )

    ctx.registrar(
        accion=Operacion.USUARIO_CREAR,
        recurso=f"usuario/{correo}",
        resultado=Resultado.ALLOW,
        detalle={"grupos": sorted(str(g) for g in grupos)},
    )
    return {"usuario": vista_usuario(registro)}


@app.post("/usuarios/{correo}", tags=["usuarios"], summary="Actualizar un usuario")
async def actualizar_usuario(
    correo: str, cambios: ActualizacionUsuario, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.USUARIO_EDITAR, recurso=f"usuario/{correo}")
    registro = maestros().obtener_usuario(ctx.org_id, correo)

    if cambios.nombre is not None:
        registro["nombre"] = cambios.nombre
    if cambios.telefono is not None:
        registro["telefono"] = cambios.telefono

    if cambios.grupos is not None:
        grupos = _exigir_roles_existentes(ctx, cambios.grupos)
        _exigir_que_quede_un_administrador(ctx, registro, grupos)
        registro["grupos"] = sorted(str(g) for g in grupos)

    if cambios.activo is not None:
        if not cambios.activo:
            _exigir_que_quede_un_administrador(ctx, registro, frozenset())
            # Desactivar una cuenta cierra sus sesiones: si siguieran abiertas,
            # la desactivacion no surtiria efecto hasta que caducaran.
            registro["sesiones"] = []
        registro["activo"] = cambios.activo

    maestros().guardar_usuario(registro)
    ctx.registrar(
        accion=Operacion.USUARIO_EDITAR,
        recurso=f"usuario/{registro['correo']}",
        resultado=Resultado.ALLOW,
        detalle={"campos": [c for c, v in cambios.model_dump().items() if v is not None]},
    )
    return {"usuario": vista_usuario(registro)}


def _exigir_que_quede_un_administrador(
    ctx: Contexto, registro: dict, grupos_nuevos: frozenset
) -> None:
    """Impide dejar la organizacion sin administrador.

    Sin esta comprobacion, quitarse a uno mismo el rol de administrador -o
    desactivar la ultima cuenta que lo tiene- deja la empresa sin nadie que
    pueda crear usuarios, y solo se puede arreglar desde la base de datos.
    """
    era_admin = "administrador" in (registro.get("grupos") or [])
    sigue_admin = Grupo.ADMINISTRADOR in grupos_nuevos
    if not era_admin or sigue_admin:
        return

    otros_admin = [
        u
        for u in maestros().listar_usuarios(ctx.org_id)
        if u["correo"] != registro["correo"]
        and u.get("activo", True)
        and "administrador" in u.get("grupos", [])
    ]
    if not otros_admin:
        raise ConflictoError(
            "La organizacion quedaria sin ningun administrador activo. "
            "Asigne el rol a otra cuenta antes de retirarlo de esta."
        )


# --------------------------------------------------------------------------- #
# Empresa
# --------------------------------------------------------------------------- #


@app.get("/empresa", tags=["empresa"], summary="Datos de la organizacion")
async def obtener_empresa(ctx: Contexto = Depends(contexto_actual)) -> dict:
    return {"empresa": maestros().obtener_empresa(ctx.org_id)}


# --------------------------------------------------------------------------- #
# Utilidades internas
# --------------------------------------------------------------------------- #


def _exigir_roles_existentes(ctx: Contexto, grupos) -> frozenset[str]:
    """Comprueba que los roles asignados existen en la organizacion.

    Desde que los roles se pueden personalizar, un nombre mal escrito ya no es
    un error de tipo sino un rol que no existe: la cuenta se crearia sin poder
    hacer nada y nadie sabria por que. Se rechaza aqui, con el nombre a la vista.
    """
    nombres = normalizar_grupos(grupos)
    if not nombres:
        raise ValidacionError("El usuario debe tener al menos un rol.")

    definiciones = maestros().definiciones_de_rol(ctx.org_id)
    desconocidos = sorted(nombres - set(definiciones))
    if desconocidos:
        raise ValidacionError(
            f"Estos roles no existen en la organizacion: {', '.join(desconocidos)}. "
            "Los disponibles son: " + ", ".join(sorted(definiciones)) + "."
        )

    # La separacion de funciones se comprueba sobre la suma de los roles de la
    # cuenta, no solo sobre cada uno. Sin esto, un administrador podria anadirse
    # el rol de auditor y quedarse revisando su propio rastro sin que ningun rol
    # rompiera la regla por separado.
    if rompe_separacion_de_funciones(union_de_roles(nombres, definiciones)):
        raise ValidacionError(
            "Una cuenta no puede operar y auditar a la vez: quien revisa la bitacora "
            "no puede ser quien la produce. Use cuentas distintas para las dos cosas."
        )
    return nombres


def _usuario_por_sub(org_id: str, sub: str) -> dict | None:
    return maestros().usuario_por_sub(org_id, sub)


def _registrar_intento(registro: dict, motivo: str) -> None:
    """Un intento fallido de inicio de sesion tambien queda en la bitacora.

    Es el registro que permite detectar un ataque por fuerza bruta: sin el, los
    fallos no dejan rastro y el patron es invisible.
    """
    try:
        obtener_repositorio().registrar_bitacora(
            org_id=registro["org_id"],
            actor_sub=registro.get("sub", "desconocido"),
            actor_email=registro.get("correo", ""),
            actor_grupos=registro.get("grupos", []),
            accion="sesion:iniciar",
            recurso=f"usuario/{registro.get('correo', '')}",
            resultado=Resultado.DENY,
            detalle={"motivo": motivo},
        )
    except Exception:  # noqa: BLE001 - no se impide entrar por un fallo de bitacora
        pass


def _registrar_en_bitacora(registro: dict, *, accion: str, resultado, detalle: dict) -> None:
    try:
        obtener_repositorio().registrar_bitacora(
            org_id=registro["org_id"],
            actor_sub=registro["sub"],
            actor_email=registro["correo"],
            actor_grupos=registro["grupos"],
            accion=accion,
            recurso=f"usuario/{registro['correo']}",
            resultado=resultado,
            detalle=detalle,
        )
    except Exception:  # noqa: BLE001
        pass


@app.get("/auth/roles", tags=["roles"], summary="Catalogo de operaciones del sistema")
async def catalogo_de_autorizacion() -> dict:
    """Que operaciones existen y que hace cada una, agrupadas por area.

    Es abierta porque describe el modelo de autorizacion, no los datos de
    ninguna organizacion: la misma informacion que un evaluador necesita para
    juzgar el control. Los roles concretos de una empresa -que puede
    personalizar- se piden en `/roles`.
    """
    return {
        "areas": catalogo_de_operaciones(),
        "integrados": [vista_rol(rol) for rol in ROLES_INTEGRADOS.values()],
    }


@app.get("/roles", tags=["roles"], summary="Roles de la organizacion")
async def listar_roles(ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Los roles de esta organizacion, con las operaciones que concede cada uno.

    Salen de la tabla y no del codigo: una empresa puede necesitar un
    coordinador con mas alcance que un despachador y menos que un
    administrador, y eso es una decision suya.
    """
    ctx.exigir(Operacion.ROL_CONSULTAR, recurso="rol/lista")

    definiciones = maestros().definiciones_de_rol(ctx.org_id)
    en_uso = Counter(
        grupo
        for usuario in maestros().listar_usuarios(ctx.org_id)
        for grupo in usuario.get("grupos", [])
    )

    roles = []
    for definicion in definiciones.values():
        vista = vista_rol(definicion)
        vista["cuentas"] = en_uso.get(definicion.clave, 0)
        vista["separacion_comprometida"] = rompe_separacion_de_funciones(definicion.operaciones)
        roles.append(vista)

    roles.sort(key=lambda r: (not r["integrado"], r["nombre"]))
    return {"roles": roles, "total": len(roles)}


@app.post("/roles", status_code=201, tags=["roles"], summary="Crear un rol")
async def crear_rol(entrada: RolEntrada, ctx: Contexto = Depends(contexto_actual)) -> dict:
    ctx.exigir(Operacion.ROL_ADMINISTRAR, recurso="rol/nuevo")

    clave = entrada.clave.strip().lower()
    try:
        maestros().obtener_rol(ctx.org_id, clave)
    except NoEncontradoError:
        pass
    else:
        raise ConflictoError(f"Ya existe un rol con la clave '{clave}'.")

    return {"rol": _guardar_rol(ctx, {**entrada.model_dump(mode="json"), "clave": clave})}


@app.post("/roles/{clave}", tags=["roles"], summary="Cambiar los permisos de un rol")
async def actualizar_rol(
    clave: str, entrada: RolActualizacion, ctx: Contexto = Depends(contexto_actual)
) -> dict:
    ctx.exigir(Operacion.ROL_ADMINISTRAR, recurso=f"rol/{clave}")

    actual = maestros().obtener_rol(ctx.org_id, clave)
    cambios = {c: v for c, v in entrada.model_dump(mode="json").items() if v is not None}
    return {"rol": _guardar_rol(ctx, {**actual, **cambios, "clave": clave})}


@app.post("/roles/{clave}/eliminar", tags=["roles"], summary="Eliminar un rol")
async def eliminar_rol(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict:
    """Solo se borran los roles que la organizacion creo, y solo si nadie los usa.

    Borrar un rol en uso dejaria cuentas apuntando a un rol inexistente: no
    perderian el acceso de golpe -un rol sin definicion no concede nada- pero
    nadie sabria por que esa persona dejo de poder trabajar.
    """
    ctx.exigir(Operacion.ROL_ADMINISTRAR, recurso=f"rol/{clave}")

    if clave.lower() in ROLES_INTEGRADOS:
        raise ValidacionError(
            "Los roles de fabrica no se eliminan. Puede ajustar sus permisos o "
            "dejar de asignarlos."
        )
    maestros().obtener_rol(ctx.org_id, clave)

    usuarios = [
        u["correo"] for u in maestros().listar_usuarios(ctx.org_id) if clave in u.get("grupos", [])
    ]
    if usuarios:
        raise ConflictoError(
            f"El rol lo usan {len(usuarios)} cuenta(s). Cambie su rol antes de eliminarlo.",
            {"cuentas": usuarios[:10]},
        )

    maestros().eliminar_rol(ctx.org_id, clave)
    ctx.registrar(
        accion=Operacion.ROL_ADMINISTRAR,
        recurso=f"rol/{clave}",
        resultado=Resultado.ALLOW,
        detalle={"operacion": "eliminar"},
    )
    return {"eliminado": True, "clave": clave}


def _guardar_rol(ctx: Contexto, datos: dict) -> dict:
    """Guarda con las comprobaciones que no se pueden saltar desde ninguna pantalla."""
    solicitadas = {str(o) for o in (datos.get("operaciones") or [])}

    # El orden importa: primero si la operacion existe y despues si quien pide
    # la tiene. Al reves, pedir una operacion inventada respondia «no puede
    # conceder permisos que usted no tiene», que manda a buscar el problema
    # donde no esta.
    inexistentes = sorted(solicitadas - {str(o) for o in Operacion})
    if inexistentes:
        raise ValidacionError(
            f"Estas operaciones no existen en el sistema: {', '.join(inexistentes)}."
        )

    # Una cuenta no puede operar y auditar a la vez, y un rol tampoco. Es el
    # control que sostiene el resto: quien revisa el registro de lo que se hizo
    # no puede ser quien lo hizo. Se comprueba aqui, en el unico camino de
    # escritura, y no en la pantalla.
    if rompe_separacion_de_funciones(solicitadas):
        ctx.registrar(
            accion=Operacion.ROL_ADMINISTRAR,
            recurso=f"rol/{datos.get('clave')}",
            resultado=Resultado.DENY,
            detalle={"motivo": "separacion_de_funciones", "operaciones": sorted(solicitadas)},
        )
        raise ValidacionError(
            "Un rol no puede leer la bitacora y ademas operar sobre el sistema: quien "
            "revisa el registro no puede ser quien lo produce. Separe las dos cosas en "
            "roles distintos."
        )

    # Nadie concede lo que no tiene. Hoy solo el administrador administra roles
    # y las tiene todas, de modo que no cambia nada; el dia que se delegue
    # `rol:administrar` en otro rol, esta linea es lo que impide que se
    # promocione a si mismo.
    propias = {str(o) for o in operaciones_de(ctx.identidad.grupos, ctx.roles)}
    excedidas = sorted(solicitadas - propias)
    if excedidas:
        ctx.registrar(
            accion=Operacion.ROL_ADMINISTRAR,
            recurso=f"rol/{datos.get('clave')}",
            resultado=Resultado.DENY,
            detalle={"motivo": "escalada_de_privilegios", "operaciones": excedidas},
        )
        raise NoAutorizadoError(
            "No puede conceder permisos que usted no tiene: " + ", ".join(excedidas),
            {"operaciones": excedidas},
        )

    rol = maestros().guardar_rol(ctx.org_id, datos)

    ctx.registrar(
        accion=Operacion.ROL_ADMINISTRAR,
        recurso=f"rol/{rol['clave']}",
        resultado=Resultado.ALLOW,
        detalle={"operaciones": rol["operaciones"]},
    )
    return rol
