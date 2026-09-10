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
USUARIOS_LOCAL = [
    UsuarioDePrueba("despachador_a", "despacho@andes.test", "Andes.2026", "org-andes", "despachador"),
    UsuarioDePrueba("conductor_a", "carlos@andes.test", "Andes.2026", "org-andes", "conductor"),
    UsuarioDePrueba("auditor_a", "auditor@andes.test", "Andes.2026", "org-andes", "auditor"),
    UsuarioDePrueba("despachador_b", "despacho@sabana.test", "Sabana.2026", "org-sabana", "despachador"),
    UsuarioDePrueba("auditor_b", "auditor@sabana.test", "Sabana.2026", "org-sabana", "auditor"),
]


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
            usuarios=list(USUARIOS_LOCAL),
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
            "/auth/token", json={"usuario": usuario.usuario, "clave": usuario.clave}
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
