"""Contexto de ejecucion del programa de auditoria.

Reune lo que toda prueba necesita: contra que sistema se ejecuta, con que
credenciales de prueba y bajo que identidad de sesion. La identidad forma parte
del papel de trabajo porque un resultado sin saber quien lo obtuvo no es
evidencia de auditoria.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

RAIZ_COTEJO = Path(__file__).resolve().parents[1]
RAIZ_PROYECTO = RAIZ_COTEJO.parent


@dataclass
class UsuarioDePrueba:
    """Credenciales de un usuario sintetico usado en las pruebas sustantivas."""

    etiqueta: str
    usuario: str
    clave: str
    org_id: str
    grupo: str


#: Usuarios sinteticos del sistema auditado. Cubren los dos ejes que las pruebas
#: sustantivas necesitan cruzar: el rol y la organizacion.
#: Roles que las pruebas sustantivas necesitan cruzar, y con que etiqueta se
#: nombran en el catalogo. El sufijo dice la organizacion: `_a` la primera y
#: `_b` la segunda, porque el aislamiento solo puede probarse con dos.
ROLES_NECESARIOS = (
    ("despachador_a", "despachador", 0),
    ("conductor_a", "conductor", 0),
    ("auditor_a", "auditor", 0),
    ("despachador_b", "despachador", 1),
    ("auditor_b", "auditor", 1),
)


def _claves_conocidas(entorno: str) -> dict[str, str]:
    """De donde salen las contrasenas de los usuarios de prueba.

    De la base de datos no pueden salir: alli estan derivadas con PBKDF2 y no
    hay forma de recuperarlas, que es justamente lo que se quiere de un sistema
    que guarda contrasenas. De modo que son lo unico que el programa recibe por
    configuracion, y no por descubrimiento.

    Orden de precedencia:

    1. ``COTEJO_CLAVES``, un JSON de correo a clave. Es lo que usa un despliegue
       con datos reales, donde las claves de la semilla ya no valen.
    2. En el entorno local, el mismo archivo de semilla que creo esas cuentas.
       No se copia aqui: duplicarlo significaria que al cambiar una clave el
       programa de auditoria dejaria de entrar sin que nadie supiera por que.
    """
    crudo = os.getenv("COTEJO_CLAVES")
    if crudo:
        try:
            return {str(c).strip().lower(): str(v) for c, v in json.loads(crudo).items()}
        except (json.JSONDecodeError, AttributeError) as exc:
            raise ErrorContexto(
                'COTEJO_CLAVES no es un JSON valido: se espera {"correo": "clave"}.'
            ) from exc

    semilla = RAIZ_PROYECTO / "seed" / "organizaciones.json"
    if entorno == "local" and semilla.is_file():
        datos = json.loads(semilla.read_text(encoding="utf-8"))
        return {
            usuario["correo"].strip().lower(): usuario["clave"]
            for organizacion in datos["organizaciones"]
            for usuario in organizacion["usuarios"]
        }

    return {}


def descubrir_usuarios(
    *, region: str, endpoint_dynamodb: str | None, tabla_maestros: str, entorno: str
) -> list[UsuarioDePrueba]:
    """Averigua contra que cuentas ejecutar, leyendo el directorio del sistema.

    Antes esta lista estaba escrita en el codigo: cinco correos con su clave y su
    organizacion. Tenia dos problemas. El primero, que un despliegue con otras
    cuentas obligaba a editar el programa de auditoria, y un programa que hay que
    editar para poder ejecutarlo deja de ser reproducible. El segundo, que las
    claves quedaban versionadas en el repositorio.

    Ahora las identidades salen de la tabla de maestros -que es donde el sistema
    auditado dice quien existe y con que rol- y las claves, de la configuracion.
    Si falta la clave de alguna, esa etiqueta no se emite: las pruebas que la
    necesiten se reportan como no ejecutadas, con su motivo, que es la conducta
    correcta para una prueba que no se pudo hacer.
    """
    import boto3
    from boto3.dynamodb.conditions import Attr

    argumentos: dict[str, Any] = {"region_name": region}
    if endpoint_dynamodb:
        argumentos["endpoint_url"] = endpoint_dynamodb

    try:
        tabla = boto3.resource("dynamodb", **argumentos).Table(tabla_maestros)
        respuesta = tabla.scan(
            FilterExpression=Attr("sk").begins_with("USR#"),
            # Solo lo necesario para elegir: ni el hash de la contrasena ni las
            # sesiones abiertas tienen nada que hacer en un papel de trabajo.
            ProjectionExpression="correo, org_id, grupos, activo",
        )
    except Exception as exc:  # noqa: BLE001 - se traduce a un error de contexto
        raise ErrorContexto(
            f"No fue posible leer el directorio de usuarios en {tabla_maestros}: {exc}"
        ) from exc

    registros = [r for r in respuesta.get("Items", []) if r.get("activo", True)]
    if not registros:
        raise ErrorContexto(
            f"El directorio {tabla_maestros} no tiene usuarios activos: no hay contra "
            "que ejecutar las pruebas sustantivas."
        )

    claves = _claves_conocidas(entorno)
    organizaciones = sorted({str(r["org_id"]) for r in registros})

    usuarios: list[UsuarioDePrueba] = []
    for etiqueta, grupo, indice in ROLES_NECESARIOS:
        if indice >= len(organizaciones):
            continue
        org_id = organizaciones[indice]

        candidatos = sorted(
            (
                r
                for r in registros
                if r["org_id"] == org_id and grupo in [str(g) for g in r.get("grupos", [])]
            ),
            key=lambda r: str(r["correo"]),
        )
        for candidato in candidatos:
            correo = str(candidato["correo"]).strip().lower()
            if correo in claves:
                usuarios.append(UsuarioDePrueba(etiqueta, correo, claves[correo], org_id, grupo))
                break

    return usuarios


class ErrorContexto(Exception):
    """El contexto no pudo prepararse: sin el, ninguna prueba puede ejecutarse."""


@dataclass
class Contexto:
    entorno: str
    url_api: str
    region: str
    bucket_evidencias: str
    alias_llave: str
    nombre_registro: str
    tabla_bitacora: str
    usuarios: list[UsuarioDePrueba]
    endpoint_s3: str | None = None
    endpoint_dynamodb: str | None = None
    #: Quien pidio la ejecucion, cuando se sabe. Desde la linea de comandos no
    #: se sabe mas que el usuario del sistema operativo; desde la interfaz web
    #: si, porque hubo que autenticarse para llegar. Un papel que dice
    #: "local:desconocido" incumple el principio del propio modulo: un resultado
    #: del que no consta quien lo obtuvo no es evidencia de auditoria.
    identidad_declarada: str | None = None
    _tokens: dict[str, str] = field(default_factory=dict, repr=False)
    _cliente: httpx.Client | None = field(default=None, repr=False)

    # -- construccion ------------------------------------------------------ #

    @classmethod
    def desde_entorno(cls) -> "Contexto":
        """Lee la configuracion del despliegue, con precedencia a las variables.

        Si existe config/deployment.json, el programa audita lo que ese archivo
        describe. Es el mismo archivo que leen los servicios, de modo que no hay
        forma de auditar una configuracion distinta de la que opera.
        """
        despliegue: dict = {}
        ruta = RAIZ_PROYECTO / "config" / "deployment.json"
        if ruta.is_file():
            try:
                despliegue = json.loads(ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ErrorContexto(f"El archivo de despliegue no es JSON valido: {exc}") from exc

        def valor(env: str, clave: str, defecto=None):
            return os.getenv(env) or despliegue.get(clave) or defecto

        entorno = valor("COTEJO_ENTORNO", "entorno", "local")
        cuenta = valor("COTEJO_ACCOUNT_ID", "account_id", "local")

        return cls(
            entorno=entorno,
            url_api=valor("COTEJO_URL_API", "url_publica_api", "http://localhost:8080"),
            region=valor("AWS_REGION", "region", "us-east-1"),
            bucket_evidencias=valor(
                "COTEJO_BUCKET", "bucket_evidencias",
                "rastro-evidencias-local" if entorno == "local" else f"rastro-evidencias-{cuenta}",
            ),
            alias_llave=valor("COTEJO_ALIAS_LLAVE", "alias_llave", "alias/rastro"),
            nombre_registro=valor("COTEJO_REGISTRO", "registro_actividad", "rastro-actividad"),
            tabla_bitacora=valor("COTEJO_TABLA_BITACORA", "tabla_bitacora", "rastro-bitacora"),
            endpoint_s3=valor("COTEJO_ENDPOINT_S3", "endpoint_s3_publico", None),
            endpoint_dynamodb=valor("COTEJO_ENDPOINT_DYNAMODB", "endpoint_dynamodb", None),
            usuarios=descubrir_usuarios(
                region=valor("AWS_REGION", "region", "us-east-1"),
                endpoint_dynamodb=valor("COTEJO_ENDPOINT_DYNAMODB", "endpoint_dynamodb", None),
                tabla_maestros=valor("COTEJO_TABLA_MAESTROS", "tabla_maestros", "rastro-maestros"),
                entorno=entorno,
            ),
        )

    @property
    def es_local(self) -> bool:
        return self.entorno == "local"

    # -- acceso al sistema auditado ---------------------------------------- #

    @property
    def cliente(self) -> httpx.Client:
        if self._cliente is None:
            self._cliente = httpx.Client(base_url=self.url_api, timeout=30)
        return self._cliente

    def usuario(self, etiqueta: str) -> UsuarioDePrueba:
        for candidato in self.usuarios:
            if candidato.etiqueta == etiqueta:
                return candidato
        raise ErrorContexto(f"No hay usuario de prueba con la etiqueta {etiqueta}.")

    def token(self, etiqueta: str) -> str:
        """Autentica al usuario de prueba y conserva su token durante la ejecucion."""
        if etiqueta in self._tokens:
            return self._tokens[etiqueta]

        usuario = self.usuario(etiqueta)
        respuesta = self.cliente.post(
            "/auth/token", json={"correo": usuario.usuario, "clave": usuario.clave}
        )
        if respuesta.status_code != 200:
            raise ErrorContexto(
                f"No fue posible autenticar al usuario de prueba {etiqueta}: "
                f"{respuesta.status_code} {respuesta.text[:200]}"
            )
        self._tokens[etiqueta] = respuesta.json()["token"]
        return self._tokens[etiqueta]

    def cabeceras(self, etiqueta: str) -> dict:
        return {"Authorization": f"Bearer {self.token(etiqueta)}"}

    # -- acceso a la configuracion de la infraestructura -------------------- #

    def cliente_aws(self, servicio: str):
        """Cliente en modo lectura para las pruebas de cumplimiento.

        El programa no deberia disponer de permisos de escritura sobre lo que
        audita. En este entorno los tiene, porque el laboratorio impone un rol
        unico y compartido: la limitacion se declara como hallazgo permanente
        H-PERM-02 y no se presenta como una condicion aceptable.
        """
        import boto3

        argumentos = {"region_name": self.region}
        if servicio == "s3" and self.endpoint_s3:
            argumentos["endpoint_url"] = self.endpoint_s3
        if servicio == "dynamodb" and self.endpoint_dynamodb:
            argumentos["endpoint_url"] = self.endpoint_dynamodb
        return boto3.client(servicio, **argumentos)

    def identidad_de_sesion(self) -> str:
        """Bajo que identidad se ejecuta el programa. Va en cada papel de trabajo."""
        if self.identidad_declarada:
            return self.identidad_declarada
        if self.es_local:
            return f"local:{os.getenv('USERNAME') or os.getenv('USER') or 'desconocido'}"
        try:
            identidad = self.cliente_aws("sts").get_caller_identity()
            return f"{identidad['Account']}:{identidad['Arn'].rsplit('/', 1)[-1]}"
        except Exception as exc:  # noqa: BLE001 - la identidad no debe detener la ejecucion
            return f"desconocida ({type(exc).__name__})"

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
            self._cliente = None
