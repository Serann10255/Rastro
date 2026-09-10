"""Datos maestros: empresas, usuarios, tiendas, clientes y transportistas.

Todo vive en una tabla aparte de la de envios. La razon no es organizativa: la
tabla de envios crece con el volumen de operacion y la de maestros no, de modo
que mezclarlas haria que un listado de tiendas compitiera por capacidad con el
trafico de eventos de rastreo.

El aislamiento entre organizaciones se aplica igual que en los envios: la clave
de particion es la organizacion y ninguna funcion construye una clave sin ella.

Claves:

    PK                SK                     Contenido
    ORG#<org>         PERFIL                 datos de la empresa
    ORG#<org>         USR#<email>            usuario con su hash de contrasena
    ORG#<org>         TIENDA#<id>            tienda, almacen o estacion
    ORG#<org>         CLIENTE#<id>           cliente remitente
    ORG#<org>         TRANSP#<id>            transportista
    ORG#<org>         MODULO#<clave>         modulo del sistema y si esta disponible
    ORG#<org>         ROL#<clave>            rol con las operaciones que concede

El indice ``gsi_email`` resuelve el inicio de sesion: el usuario escribe su
correo y no su organizacion, de modo que hay que encontrarlo sin saber en que
particion esta.
"""

from __future__ import annotations

import re
import uuid
from enum import StrEnum
from typing import Any

from .errors import ConflictoError, NoEncontradoError, ValidacionError
from .ids import marca_tiempo

SK_PERFIL = "PERFIL"
PREFIJO_USUARIO = "USR#"
PREFIJO_TIENDA = "TIENDA#"
PREFIJO_CLIENTE = "CLIENTE#"
PREFIJO_TRANSPORTISTA = "TRANSP#"
PREFIJO_MODULO = "MODULO#"
PREFIJO_ROL = "ROL#"

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TipoTienda(StrEnum):
    TIENDA = "tienda"
    ALMACEN = "almacen"
    ESTACION = "estacion"


class TipoTransportista(StrEnum):
    PROPIO = "propio"
    TERCERO = "tercero"


def normalizar_correo(correo: str) -> str:
    """El correo es la clave del usuario: se normaliza para que no haya dos.

    Sin esto, ``Ana@Empresa.com`` y ``ana@empresa.com`` serian cuentas distintas
    y la misma persona podria registrarse dos veces sin notarlo.
    """
    correo = (correo or "").strip().lower()
    if not _CORREO.match(correo):
        raise ValidacionError("El correo no tiene un formato valido.")
    return correo


def nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


def _exigir(valor: str, campo: str, minimo: int = 2, maximo: int = 160) -> str:
    valor = (valor or "").strip()
    if len(valor) < minimo:
        raise ValidacionError(f"El campo '{campo}' es obligatorio.")
    if len(valor) > maximo:
        raise ValidacionError(f"El campo '{campo}' excede {maximo} caracteres.")
    return valor


# --------------------------------------------------------------------------- #
# Repositorio
# --------------------------------------------------------------------------- #


class RepositorioMaestros:
    """Acceso a los datos maestros. Sobre DynamoDB local o en AWS."""

    def __init__(self, config=None, recurso=None) -> None:
        from .config import cargar_config

        self.config = config or cargar_config()
        if recurso is None:
            import boto3

            recurso = boto3.resource(
                "dynamodb",
                region_name=self.config.region,
                endpoint_url=self.config.endpoint_dynamodb,
            )
        self._tabla = recurso.Table(self.config.tabla_maestros)

    # -- utilidades -------------------------------------------------------- #

    @staticmethod
    def _pk(org_id: str) -> str:
        from .claves import gsi_org_pk

        return gsi_org_pk(org_id)

    def _obtener(self, org_id: str, sk: str) -> dict | None:
        from .repository import _limpiar

        respuesta = self._tabla.get_item(Key={"pk": self._pk(org_id), "sk": sk})
        item = respuesta.get("Item")
        return _limpiar(item) if item else None

    def _listar(self, org_id: str, prefijo: str, limite: int = 500) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        from .repository import _limpiar

        respuesta = self._tabla.query(
            KeyConditionExpression=(
                Key("pk").eq(self._pk(org_id)) & Key("sk").begins_with(prefijo)
            ),
            Limit=limite,
        )
        return [_limpiar(i) for i in respuesta.get("Items", [])]

    def _guardar(self, org_id: str, sk: str, datos: dict, *, exigir_nuevo: bool = False) -> dict:
        from botocore.exceptions import ClientError

        from .repository import _sin_nulos

        item = {**_sin_nulos(datos), "pk": self._pk(org_id), "sk": sk}
        argumentos: dict[str, Any] = {"Item": item}
        if exigir_nuevo:
            argumentos["ConditionExpression"] = "attribute_not_exists(pk)"
        try:
            self._tabla.put_item(**argumentos)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConflictoError("El registro ya existe.") from exc
            raise
        return datos

    def _eliminar(self, org_id: str, sk: str) -> None:
        self._tabla.delete_item(Key={"pk": self._pk(org_id), "sk": sk})

    # -- empresa ----------------------------------------------------------- #

    def guardar_empresa(self, empresa: dict) -> dict:
        datos = {
            "org_id": _exigir(empresa["org_id"], "org_id"),
            "nombre": _exigir(empresa["nombre"], "nombre"),
            "nit": (empresa.get("nit") or "").strip(),
            "direccion": (empresa.get("direccion") or "").strip(),
            "ciudad": (empresa.get("ciudad") or "").strip(),
            "departamento": (empresa.get("departamento") or "").strip(),
            "pais": (empresa.get("pais") or "Colombia").strip(),
            "telefono": (empresa.get("telefono") or "").strip(),
            "correo_contacto": (empresa.get("correo_contacto") or "").strip(),
            "activa": bool(empresa.get("activa", True)),
            "creada_en": empresa.get("creada_en") or marca_tiempo(),
            "actualizada_en": marca_tiempo(),
        }
        return self._guardar(datos["org_id"], SK_PERFIL, datos)

    def obtener_empresa(self, org_id: str) -> dict:
        empresa = self._obtener(org_id, SK_PERFIL)
        if empresa is None:
            raise NoEncontradoError("La organizacion no existe.", {"org_id": org_id})
        return empresa

    # -- usuarios ---------------------------------------------------------- #

    def guardar_usuario(self, usuario: dict, *, exigir_nuevo: bool = False) -> dict:
        correo = normalizar_correo(usuario["correo"])
        datos = {
            "sub": usuario.get("sub") or f"u-{nuevo_id()}",
            "correo": correo,
            "nombre": _exigir(usuario["nombre"], "nombre"),
            "org_id": _exigir(usuario["org_id"], "org_id"),
            "grupos": sorted({str(g).strip().lower() for g in usuario["grupos"] if str(g).strip()}),
            "hash_clave": usuario["hash_clave"],
            "activo": bool(usuario.get("activo", True)),
            "telefono": (usuario.get("telefono") or "").strip(),
            "creado_en": usuario.get("creado_en") or marca_tiempo(),
            "actualizado_en": marca_tiempo(),
            "ultimo_acceso": usuario.get("ultimo_acceso"),
            # Sesiones abiertas: cada una con su identificador y su caducidad.
            # Se guardan para poder revocarlas; sin esta lista, cerrar sesion
            # solo borraria el token del navegador y un token ya copiado
            # seguiria sirviendo hasta caducar.
            "sesiones": list(usuario.get("sesiones") or []),
            # Indice para encontrar al usuario por correo sin conocer su
            # organizacion, que es la situacion del inicio de sesion.
            "gsi_email_pk": f"EMAIL#{correo}",
        }
        if not datos["grupos"]:
            raise ValidacionError("El usuario debe pertenecer al menos a un grupo.")
        return self._guardar(
            datos["org_id"], f"{PREFIJO_USUARIO}{correo}", datos, exigir_nuevo=exigir_nuevo
        )

    def buscar_usuario_por_correo(self, correo: str) -> dict | None:
        """Busqueda global por correo: la unica consulta sin filtro por organizacion.

        Es una excepcion necesaria y acotada: el usuario escribe su correo y no
        sabe a que organizacion pertenece. Devuelve el registro completo, que
        incluye su ``org_id``; a partir de ahi, todo lo demas vuelve a filtrarse
        por organizacion.
        """
        from boto3.dynamodb.conditions import Key

        from .repository import _limpiar

        correo = normalizar_correo(correo)
        respuesta = self._tabla.query(
            IndexName="gsi_email",
            KeyConditionExpression=Key("gsi_email_pk").eq(f"EMAIL#{correo}"),
            Limit=2,
        )
        items = respuesta.get("Items", [])
        if not items:
            return None
        if len(items) > 1:
            # Dos organizaciones con el mismo correo romperia la premisa de que
            # el correo identifica a una persona. Se impide al crear el usuario.
            raise ConflictoError("El correo esta registrado en mas de una organizacion.")
        return _limpiar(items[0])

    def obtener_usuario(self, org_id: str, correo: str) -> dict:
        usuario = self._obtener(org_id, f"{PREFIJO_USUARIO}{normalizar_correo(correo)}")
        if usuario is None:
            raise NoEncontradoError("El usuario no existe.")
        return usuario

    def listar_usuarios(self, org_id: str) -> list[dict]:
        """Sin el hash de la contrasena: no sale nunca del servicio de identidad."""
        return [_sin_hash(u) for u in self._listar(org_id, PREFIJO_USUARIO)]

    def listar_usuarios_completos(self, org_id: str) -> list[dict]:
        """Con el hash. Solo para uso interno del servicio de identidad."""
        return self._listar(org_id, PREFIJO_USUARIO)

    def usuario_por_sub(self, org_id: str, sub: str) -> dict | None:
        """Busca dentro de la organizacion por el sujeto del token."""
        if not org_id or not sub:
            return None
        return next(
            (u for u in self.listar_usuarios_completos(org_id) if u.get("sub") == sub), None
        )

    def eliminar_usuario(self, org_id: str, correo: str) -> None:
        self._eliminar(org_id, f"{PREFIJO_USUARIO}{normalizar_correo(correo)}")

    def registrar_acceso(self, org_id: str, correo: str) -> None:
        """Deja constancia del ultimo acceso. Es dato de auditoria, no de sesion."""
        self._tabla.update_item(
            Key={"pk": self._pk(org_id), "sk": f"{PREFIJO_USUARIO}{normalizar_correo(correo)}"},
            UpdateExpression="SET ultimo_acceso = :ts",
            ExpressionAttributeValues={":ts": marca_tiempo()},
        )

    # -- tiendas ----------------------------------------------------------- #

    def guardar_tienda(self, org_id: str, tienda: dict) -> dict:
        datos = {
            "tienda_id": tienda.get("tienda_id") or nuevo_id(),
            "org_id": org_id,
            "nombre": _exigir(tienda["nombre"], "nombre"),
            "codigo": _exigir(tienda.get("codigo") or tienda["nombre"], "codigo").upper(),
            "tipo": str(TipoTienda(tienda.get("tipo", "tienda"))),
            "direccion": (tienda.get("direccion") or "").strip(),
            "ciudad": _exigir(tienda.get("ciudad", ""), "ciudad"),
            "departamento": _exigir(tienda.get("departamento", ""), "departamento"),
            "telefono": (tienda.get("telefono") or "").strip(),
            "responsable": (tienda.get("responsable") or "").strip(),
            "activa": bool(tienda.get("activa", True)),
            "creada_en": tienda.get("creada_en") or marca_tiempo(),
            "actualizada_en": marca_tiempo(),
        }
        return self._guardar(org_id, f"{PREFIJO_TIENDA}{datos['tienda_id']}", datos)

    def listar_tiendas(self, org_id: str) -> list[dict]:
        return self._listar(org_id, PREFIJO_TIENDA)

    def obtener_tienda(self, org_id: str, tienda_id: str) -> dict:
        tienda = self._obtener(org_id, f"{PREFIJO_TIENDA}{tienda_id}")
        if tienda is None:
            raise NoEncontradoError("La tienda no existe.")
        return tienda

    def eliminar_tienda(self, org_id: str, tienda_id: str) -> None:
        self._eliminar(org_id, f"{PREFIJO_TIENDA}{tienda_id}")

    # -- clientes ---------------------------------------------------------- #

    def guardar_cliente(self, org_id: str, cliente: dict) -> dict:
        datos = {
            "cliente_id": cliente.get("cliente_id") or nuevo_id(),
            "org_id": org_id,
            "nombre": _exigir(cliente["nombre"], "nombre"),
            "correo": normalizar_correo(cliente["correo"]) if cliente.get("correo") else "",
            "telefono": (cliente.get("telefono") or "").strip(),
            "documento": (cliente.get("documento") or "").strip(),
            "direccion": (cliente.get("direccion") or "").strip(),
            "ciudad": (cliente.get("ciudad") or "").strip(),
            "departamento": (cliente.get("departamento") or "").strip(),
            "activo": bool(cliente.get("activo", True)),
            "creado_en": cliente.get("creado_en") or marca_tiempo(),
            "actualizado_en": marca_tiempo(),
        }
        return self._guardar(org_id, f"{PREFIJO_CLIENTE}{datos['cliente_id']}", datos)

    def listar_clientes(self, org_id: str) -> list[dict]:
        return self._listar(org_id, PREFIJO_CLIENTE)

    def obtener_cliente(self, org_id: str, cliente_id: str) -> dict:
        cliente = self._obtener(org_id, f"{PREFIJO_CLIENTE}{cliente_id}")
        if cliente is None:
            raise NoEncontradoError("El cliente no existe.")
        return cliente

    def eliminar_cliente(self, org_id: str, cliente_id: str) -> None:
        self._eliminar(org_id, f"{PREFIJO_CLIENTE}{cliente_id}")

    # -- transportistas ---------------------------------------------------- #

    def guardar_transportista(self, org_id: str, transportista: dict) -> dict:
        datos = {
            "transportista_id": transportista.get("transportista_id") or nuevo_id(),
            "org_id": org_id,
            "nombre": _exigir(transportista["nombre"], "nombre"),
            "correo": (
                normalizar_correo(transportista["correo"]) if transportista.get("correo") else ""
            ),
            "telefono": (transportista.get("telefono") or "").strip(),
            "tipo": str(TipoTransportista(transportista.get("tipo", "tercero"))),
            "nit": (transportista.get("nit") or "").strip(),
            "ciudad": (transportista.get("ciudad") or "").strip(),
            "departamento": (transportista.get("departamento") or "").strip(),
            "activo": bool(transportista.get("activo", True)),
            "creado_en": transportista.get("creado_en") or marca_tiempo(),
            "actualizado_en": marca_tiempo(),
        }
        return self._guardar(
            org_id, f"{PREFIJO_TRANSPORTISTA}{datos['transportista_id']}", datos
        )

    def listar_transportistas(self, org_id: str) -> list[dict]:
        return self._listar(org_id, PREFIJO_TRANSPORTISTA)

    def obtener_transportista(self, org_id: str, transportista_id: str) -> dict:
        registro = self._obtener(org_id, f"{PREFIJO_TRANSPORTISTA}{transportista_id}")
        if registro is None:
            raise NoEncontradoError("El transportista no existe.")
        return registro

    def eliminar_transportista(self, org_id: str, transportista_id: str) -> None:
        self._eliminar(org_id, f"{PREFIJO_TRANSPORTISTA}{transportista_id}")

    # -- modulos ------------------------------------------------------------ #

    def guardar_modulo(self, org_id: str, modulo: dict) -> dict:
        """Un modulo del sistema tal como lo tiene esta organizacion.

        Que modulos ve una empresa es un dato suyo, no una constante del
        programa: una empresa puede tener contratada la operacion y no la
        auditoria, y la interfaz tiene que reflejarlo sin recompilarse.
        """
        clave = _exigir(modulo["clave"], "clave", minimo=2, maximo=40).lower()
        datos = {
            "clave": clave,
            "org_id": org_id,
            "nombre": _exigir(modulo["nombre"], "nombre"),
            "descripcion": (modulo.get("descripcion") or "").strip()[:240],
            # El nombre del icono, no el icono. La interfaz lo resuelve contra
            # su juego de trazados; si no lo conoce dibuja el generico.
            "icono": (modulo.get("icono") or "").strip()[:40],
            "ruta": (modulo.get("ruta") or "").strip()[:120],
            "grupos": sorted(
                {str(g).strip().lower() for g in (modulo.get("grupos") or []) if str(g).strip()}
            ),
            "orden": int(modulo.get("orden", 100)),
            # Si el modulo va en la navegacion principal o solo en el menu de
            # operaciones. Una barra con catorce entradas no es una barra.
            "destacado": bool(modulo.get("destacado", False)),
            "disponible": bool(modulo.get("disponible", True)),
            # Por que no esta disponible. Un modulo apagado sin motivo parece un
            # olvido; con motivo es una decision que se puede discutir.
            "motivo": (modulo.get("motivo") or "").strip()[:400],
            "contador": (modulo.get("contador") or "").strip()[:40],
            "actualizado_en": marca_tiempo(),
        }
        if datos["disponible"] and not datos["ruta"]:
            raise ValidacionError("Un modulo disponible necesita una ruta.")
        if not datos["disponible"] and not datos["motivo"]:
            raise ValidacionError("Un modulo no disponible tiene que decir por que.")
        return self._guardar(org_id, f"{PREFIJO_MODULO}{clave}", datos)

    def listar_modulos(self, org_id: str) -> list[dict]:
        modulos = self._listar(org_id, PREFIJO_MODULO)
        return sorted(modulos, key=lambda m: (int(m.get("orden", 100)), str(m.get("nombre", ""))))

    # -- roles -------------------------------------------------------------- #

    def guardar_rol(self, org_id: str, rol: dict) -> dict:
        """Un rol de la organizacion, con las operaciones que concede.

        Las operaciones se validan contra el catalogo del codigo: un rol es una
        seleccion de lo que el sistema sabe hacer, nunca una invencion. Lo que
        no exista en el catalogo se rechaza aunque venga escrito en la peticion.
        """
        from .authz import Grupo, Operacion, ROLES_INTEGRADOS

        clave = _exigir(rol["clave"], "clave", minimo=2, maximo=40).lower().replace(" ", "-")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", clave):
            raise ValidacionError(
                "La clave del rol solo admite minusculas, numeros y guiones."
            )

        if clave == Grupo.ADMINISTRADOR:
            raise ValidacionError(
                "El rol de administrador no se edita: es el seguro contra que una "
                "organizacion se quede sin nadie que pueda entrar a deshacer un cambio."
            )

        operaciones = sorted({str(o).strip() for o in (rol.get("operaciones") or [])})
        desconocidas = [o for o in operaciones if o not in {str(x) for x in Operacion}]
        if desconocidas:
            raise ValidacionError(
                f"Estas operaciones no existen en el sistema: {', '.join(desconocidas)}."
            )
        if not operaciones:
            raise ValidacionError(
                "Un rol sin operaciones no deja hacer nada: desactive las cuentas en su lugar."
            )

        integrado = clave in ROLES_INTEGRADOS
        datos = {
            "clave": clave,
            "org_id": org_id,
            "nombre": _exigir(rol["nombre"], "nombre", maximo=60),
            "descripcion": (rol.get("descripcion") or "").strip()[:400],
            "operaciones": operaciones,
            "integrado": integrado,
            "editable": True,
            "actualizado_en": marca_tiempo(),
        }
        return self._guardar(org_id, f"{PREFIJO_ROL}{clave}", datos)

    def listar_roles(self, org_id: str) -> list[dict]:
        return sorted(self._listar(org_id, PREFIJO_ROL), key=lambda r: str(r.get("nombre", "")))

    def obtener_rol(self, org_id: str, clave: str) -> dict:
        rol = self._obtener(org_id, f"{PREFIJO_ROL}{(clave or '').lower()}")
        if rol is None:
            raise NoEncontradoError("El rol no existe en esta organizacion.")
        return rol

    def eliminar_rol(self, org_id: str, clave: str) -> None:
        self._eliminar(org_id, f"{PREFIJO_ROL}{(clave or '').lower()}")

    def definiciones_de_rol(self, org_id: str) -> dict:
        """Los roles de la organizacion, listos para resolver una autorizacion.

        Si la organizacion no tiene ninguno -una instalacion que todavia no se
        ha aprovisionado- se devuelven los de fabrica, de modo que el sistema
        nunca se queda sin criterio y falla cerrado en lugar de abierto.
        """
        from .authz import DefinicionRol, Operacion, ROLES_INTEGRADOS

        registros = self._listar(org_id, PREFIJO_ROL)
        if not registros:
            return dict(ROLES_INTEGRADOS)

        definiciones = dict(ROLES_INTEGRADOS)
        for registro in registros:
            operaciones = set()
            for nombre in registro.get("operaciones") or []:
                try:
                    operaciones.add(Operacion(str(nombre)))
                except ValueError:
                    # Una operacion que ya no existe -se retiro del catalogo-
                    # simplemente no concede nada. Fallar aqui dejaria fuera al
                    # usuario por un permiso que nadie usa.
                    continue
            clave = str(registro["clave"])
            definiciones[clave] = DefinicionRol(
                clave=clave,
                nombre=str(registro.get("nombre") or clave),
                descripcion=str(registro.get("descripcion") or ""),
                operaciones=frozenset(operaciones),
                integrado=bool(registro.get("integrado", False)),
                editable=bool(registro.get("editable", True)),
            )
        # El administrador nunca sale de la tabla: se impone el de fabrica.
        definiciones[str(ROLES_INTEGRADOS["administrador"].clave)] = ROLES_INTEGRADOS[
            "administrador"
        ]
        return definiciones

    def obtener_modulo(self, org_id: str, clave: str) -> dict:
        modulo = self._obtener(org_id, f"{PREFIJO_MODULO}{(clave or '').lower()}")
        if modulo is None:
            raise NoEncontradoError("El modulo no existe en esta organizacion.")
        return modulo


def _sin_hash(usuario: dict) -> dict:
    """El hash de la contrasena no sale nunca del servicio de identidad."""
    return {c: v for c, v in usuario.items() if c not in {"hash_clave", "gsi_email_pk"}}


def vista_usuario(usuario: dict) -> dict:
    """Los datos de un usuario tal como los ve el resto del sistema."""
    return {
        "sub": usuario["sub"],
        "correo": usuario["correo"],
        "nombre": usuario["nombre"],
        "org_id": usuario["org_id"],
        "grupos": list(usuario["grupos"]),
        "activo": usuario.get("activo", True),
        "telefono": usuario.get("telefono", ""),
        "creado_en": usuario.get("creado_en"),
        "ultimo_acceso": usuario.get("ultimo_acceso"),
    }


# --------------------------------------------------------------------------- #
# Implementacion en memoria (pruebas)
# --------------------------------------------------------------------------- #


class TablaEnMemoria:
    """Sustituto minimo de una tabla de DynamoDB para las pruebas.

    Implementa solo lo que ``RepositorioMaestros`` usa: obtener por clave,
    consultar por prefijo de ordenamiento, consultar el indice de correo,
    escribir y borrar. Reutilizar el repositorio real contra esta tabla -en vez
    de escribir un repositorio falso aparte- es lo que hace que las pruebas
    ejerciten la misma construccion de claves que corre en produccion.
    """

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}

    # -- lectura ----------------------------------------------------------- #

    def get_item(self, Key: dict) -> dict:  # noqa: N803 - firma del servicio
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def query(self, **argumentos) -> dict:
        condicion = argumentos["KeyConditionExpression"]
        indice = argumentos.get("IndexName")
        limite = argumentos.get("Limit")

        if indice == "gsi_email":
            valor = _valor_de_condicion(condicion)
            encontrados = [
                dict(i) for i in self.items.values() if i.get("gsi_email_pk") == valor
            ]
        else:
            pk, prefijo = _pk_y_prefijo(condicion)
            encontrados = [
                dict(i)
                for (clave_pk, clave_sk), i in self.items.items()
                if clave_pk == pk and (prefijo is None or clave_sk.startswith(prefijo))
            ]
            encontrados.sort(key=lambda i: i.get("sk", ""))

        return {"Items": encontrados[:limite] if limite else encontrados}

    # -- escritura --------------------------------------------------------- #

    def put_item(self, Item: dict, ConditionExpression: str | None = None) -> dict:  # noqa: N803
        clave = (Item["pk"], Item["sk"])
        if ConditionExpression and "attribute_not_exists" in ConditionExpression:
            if clave in self.items:
                raise _conflicto()
        self.items[clave] = dict(Item)
        return {}

    def update_item(self, Key: dict, UpdateExpression: str, ExpressionAttributeValues: dict) -> dict:  # noqa: N803
        item = self.items.get((Key["pk"], Key["sk"]))
        if item is None:
            return {}
        # Solo se soporta la forma "SET campo = :valor", que es la unica que usa
        # el repositorio. Ampliarla sin necesidad seria construir un motor.
        campo = UpdateExpression.split("SET", 1)[1].split("=")[0].strip()
        item[campo] = next(iter(ExpressionAttributeValues.values()))
        return {}

    def delete_item(self, Key: dict) -> dict:  # noqa: N803
        self.items.pop((Key["pk"], Key["sk"]), None)
        return {}

    def scan(self, Limit: int | None = None) -> dict:  # noqa: N803
        items = list(self.items.values())[: Limit or None]
        return {"Items": [dict(i) for i in items], "Count": len(items)}


class _RecursoEnMemoria:
    def __init__(self, tabla: TablaEnMemoria) -> None:
        self._tabla = tabla

    def Table(self, _nombre: str) -> TablaEnMemoria:  # noqa: N802 - firma del servicio
        return self._tabla


def repositorio_maestros_en_memoria(config=None) -> RepositorioMaestros:
    """Repositorio real sobre una tabla en memoria. Para pruebas."""
    from .config import cargar_config

    return RepositorioMaestros(config or cargar_config(), recurso=_RecursoEnMemoria(TablaEnMemoria()))


def _conflicto():
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "ya existe"}}, "PutItem"
    )


def _valor_de_condicion(condicion) -> str:
    """Extrae el valor de una condicion de igualdad de boto3."""
    return condicion._values[1]  # noqa: SLF001 - estructura estable de boto3


def _pk_y_prefijo(condicion) -> tuple[str, str | None]:
    """Descompone ``Key(pk).eq(x)`` o ``Key(pk).eq(x) & Key(sk).begins_with(y)``."""
    if hasattr(condicion, "_values") and len(condicion._values) == 2:  # noqa: SLF001
        primero, segundo = condicion._values  # noqa: SLF001
        if hasattr(primero, "_values") and hasattr(segundo, "_values"):  # noqa: SLF001
            return primero._values[1], segundo._values[1]  # noqa: SLF001
        return _valor_de_condicion(condicion), None
    return _valor_de_condicion(condicion), None
