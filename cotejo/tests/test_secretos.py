"""Pruebas de C-09: secretos en el repositorio.

Se validan en los dos sentidos, como todo el programa: que informan conformidad
cuando el repositorio esta limpio y, sobre todo, desviacion cuando no lo esta.
El caso que justifica C-09c tiene su propia prueba: un secreto borrado del arbol
sin rotarlo sale bien en C-09a y mal en C-09b, y solo C-09c dice que sigue
abriendo el sistema.

Cada prueba trabaja sobre un repositorio git temporal y, para C-09c, contra un
sistema simulado que acepta un unico secreto de firma. Ninguna toca el
repositorio real ni el sistema desplegado.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import httpx
import jwt
import pytest

from cotejo.contexto import Contexto
from cotejo.modelos import Conclusion
from cotejo.pruebas import secretos

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no esta disponible")

EMISOR = "https://rastro-api.pruebas.rastro"
AUDIENCIA = "rastro-web"
SECRETO_VIEJO = "9d41f0c2" * 8
SECRETO_NUEVO = "5ab3e7d1" * 8
DESARROLLO = next(iter(secretos.VALORES_DE_DESARROLLO))


# --------------------------------------------------------------------------- #
# Andamiaje
# --------------------------------------------------------------------------- #


def _git(raiz: Path, *argumentos: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *argumentos], check=True, capture_output=True)


def _repositorio(tmp_path: Path, *commits: dict[str, str | None]) -> Path:
    """Un repositorio con un commit por diccionario. None borra el archivo."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "main")
    for clave, valor in (
        ("user.email", "cotejo@prueba.invalid"),
        ("user.name", "Cotejo"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        _git(raiz, "config", clave, valor)
    for archivos in commits:
        for ruta, contenido in archivos.items():
            if contenido is None:
                _git(raiz, "rm", "-q", ruta)
                continue
            destino = raiz / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8")
            _git(raiz, "add", ruta)
        _git(raiz, "commit", "-q", "--allow-empty", "-m", "cambio")
    return raiz


def _sistema(secreto_vigente: str, recibidos: list[str]):
    """Un sistema que acepta un unico secreto y responde como Rastro."""

    def manejador(peticion: httpx.Request) -> httpx.Response:
        token = peticion.headers["authorization"].split()[1]
        recibidos.append(token)
        try:
            jwt.decode(token, secreto_vigente, algorithms=["HS256"], issuer=EMISOR, audience=AUDIENCIA)
        except jwt.InvalidSignatureError:
            return httpx.Response(
                401,
                json={"codigo": "NO_AUTENTICADO", "mensaje": "Token de sesion invalido: Signature verification failed"},
            )
        except jwt.InvalidTokenError as exc:
            return httpx.Response(
                401, json={"codigo": "NO_AUTENTICADO", "mensaje": f"Token de sesion invalido: {exc}"}
            )
        return httpx.Response(404, json={"codigo": "NO_ENCONTRADO", "mensaje": "El usuario no existe."})

    return manejador


def _contexto(raiz: Path, *, entorno="aws", manejador=None, emisor=EMISOR) -> Contexto:
    ctx = Contexto(
        entorno=entorno,
        url_api="http://sistema.pruebas",
        region="us-east-1",
        bucket_evidencias="rastro-evidencias-pruebas",
        alias_llave="alias/rastro",
        nombre_registro="rastro-actividad",
        tabla_bitacora="rastro-bitacora",
        usuarios=[],
        jwt_emisor=emisor,
        jwt_audiencia=AUDIENCIA,
        raiz_repositorio=raiz,
    )
    if manejador is not None:
        ctx._cliente = httpx.Client(transport=httpx.MockTransport(manejador), base_url=ctx.url_api)
    return ctx


def _serializado(*resultados) -> str:
    return json.dumps(
        [
            {"resumen": r.resumen, "detalle": r.detalle, "observaciones": [o.como_dict() for o in r.observaciones]}
            for r in resultados
        ],
        default=str,
    )


# --------------------------------------------------------------------------- #
# C-09a y C-09b: deteccion
# --------------------------------------------------------------------------- #


def test_un_repositorio_limpio_es_conforme_en_arbol_e_historial(tmp_path):
    raiz = _repositorio(tmp_path, {"README.md": "Rastro\n"}, {"app.py": "print('hola')\n"})
    ctx = _contexto(raiz)

    assert secretos.arbol_actual(ctx).conclusion is Conclusion.CONFORME
    assert secretos.historial(ctx).conclusion is Conclusion.CONFORME


def test_un_secreto_versionado_hoy_sale_mal_en_arbol_y_en_historial(tmp_path):
    raiz = _repositorio(tmp_path, {"config/.jwt.env": f"RASTRO_JWT_SECRETO={SECRETO_VIEJO}\n"})
    ctx = _contexto(raiz)

    arbol = secretos.arbol_actual(ctx)
    historia = secretos.historial(ctx)

    assert arbol.conclusion is Conclusion.DESVIADO
    assert "config/.jwt.env:1" in arbol.resumen
    assert historia.conclusion is Conclusion.DESVIADO
    assert historia.observaciones[0].salida["hallazgos"][0]["sigue_en_el_arbol_actual"] is True


def test_un_secreto_borrado_sale_bien_en_el_arbol_y_mal_en_el_historial(tmp_path):
    """Es lo que paso con H-01: borrar el archivo no lo saca del historial."""
    raiz = _repositorio(
        tmp_path,
        {"config/.jwt.env": f"RASTRO_JWT_SECRETO={SECRETO_VIEJO}\n"},
        {"config/.jwt.env": None},
    )
    ctx = _contexto(raiz)

    arbol = secretos.arbol_actual(ctx)
    historia = secretos.historial(ctx)

    assert arbol.conclusion is Conclusion.CONFORME
    assert historia.conclusion is Conclusion.DESVIADO
    hallazgo = historia.observaciones[0].salida["hallazgos"][0]
    assert hallazgo["ruta"] == "config/.jwt.env"
    assert hallazgo["commit"] in historia.detalle["commits"]
    assert hallazgo["sigue_en_el_arbol_actual"] is False
    assert hallazgo["huella_sha256_parcial"] == secretos.huella_parcial(SECRETO_VIEJO)
    assert "ya fuera del arbol actual" in historia.resumen


def test_referencias_marcadores_y_ejemplos_no_son_secretos(tmp_path):
    """Sin esta prueba, el detector acusaria al propio guion de despliegue."""
    contenido = "\n".join(
        [
            'variables="{\\"RASTRO_JWT_SECRETO\\":\\"${SECRETO_JWT}\\"}"',
            "RASTRO_JWT_SECRETO: ${RASTRO_JWT_SECRETO:-otro}",
            "printf 'RASTRO_JWT_SECRETO=%s\\n' \"$(openssl rand -hex 32)\"",
            "export RASTRO_JWT_SECRETO=\\$(openssl rand -base64 48)",
            "RASTRO_JWT_SECRETO=corto",
            "AWS_SECRET_ACCESS_KEY: localsecreto",
            "aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ]
    )
    raiz = _repositorio(tmp_path, {"deploy/guion.sh": contenido + "\n"})
    ctx = _contexto(raiz)

    assert secretos.arbol_actual(ctx).conclusion is Conclusion.CONFORME
    assert secretos.historial(ctx).conclusion is Conclusion.CONFORME


def test_una_clave_real_de_aws_si_se_detecta(tmp_path):
    # Se arma en ejecucion: escrita entera en este archivo, C-09a la hallaria en
    # el repositorio real y acusaria a sus propias pruebas.
    identificador = "ASIA" + "4GQ7ZK2LMN3PQRS5"
    raiz = _repositorio(
        tmp_path,
        {".aws/config.ini": f"aws_access_key_id = {identificador}\n"
                            "aws_secret_access_key = " + "Ab3/" * 10 + "\n"},
    )
    resultado = secretos.arbol_actual(_contexto(raiz))

    assert resultado.conclusion is Conclusion.DESVIADO
    tipos = {h["tipo"] for h in resultado.observaciones[0].salida["hallazgos"]}
    assert tipos == {"id_de_clave_aws", "clave_secreta_aws"}


def test_un_archivo_con_nombre_de_secreto_se_detecta_aunque_no_se_lea_su_contenido(tmp_path):
    raiz = _repositorio(tmp_path, {"certificados/servidor.key": "contenido binario\n"})
    resultado = secretos.arbol_actual(_contexto(raiz))

    assert resultado.conclusion is Conclusion.DESVIADO
    assert resultado.observaciones[0].salida["hallazgos"][0]["tipo"] == "archivo_sensible"


def test_el_valor_de_desarrollo_declarado_no_es_hallazgo(tmp_path):
    raiz = _repositorio(tmp_path, {".env.example": f"RASTRO_JWT_SECRETO={DESARROLLO}\n"})
    ctx = _contexto(raiz)

    arbol = secretos.arbol_actual(ctx)
    assert arbol.conclusion is Conclusion.CONFORME
    assert len(arbol.observaciones[0].salida["valores_de_desarrollo_declarados"]) == 1
    assert secretos.historial(ctx).conclusion is Conclusion.CONFORME


def test_sin_repositorio_git_no_se_concluye(tmp_path):
    """En el contenedor de la API no hay .git: sin ejecutar, nunca conforme."""
    vacio = tmp_path / "sin-git"
    vacio.mkdir()
    ctx = _contexto(vacio, manejador=_sistema(SECRETO_NUEVO, []))

    assert secretos.arbol_actual(ctx).conclusion is Conclusion.NO_EJECUTADA
    assert secretos.historial(ctx).conclusion is Conclusion.NO_EJECUTADA
    assert secretos.vigencia(ctx).conclusion is Conclusion.NO_EJECUTADA


# --------------------------------------------------------------------------- #
# C-09c: vigencia
# --------------------------------------------------------------------------- #


def _secreto_borrado(tmp_path: Path) -> Path:
    return _repositorio(
        tmp_path,
        {"config/.jwt.env": f"RASTRO_JWT_SECRETO={SECRETO_VIEJO}\n"},
        {"config/.jwt.env": None},
    )


def test_un_secreto_rotado_es_rechazado_y_la_vigencia_es_conforme(tmp_path):
    ctx = _contexto(_secreto_borrado(tmp_path), manejador=_sistema(SECRETO_NUEVO, []))
    resultado = secretos.vigencia(ctx)

    assert resultado.conclusion is Conclusion.CONFORME
    veredictos = {p["huella_sha256_parcial"]: p["veredicto"] for p in resultado.observaciones[0].salida["pruebas"]}
    assert veredictos[secretos.huella_parcial(SECRETO_VIEJO)] == "rechazado"


def test_un_secreto_borrado_sin_rotar_sigue_vigente_y_solo_c09c_lo_dice(tmp_path):
    """El caso que justifica C-09c: el arbol limpio no significa riesgo mitigado."""
    ctx = _contexto(_secreto_borrado(tmp_path), manejador=_sistema(SECRETO_VIEJO, []))

    assert secretos.arbol_actual(ctx).conclusion is Conclusion.CONFORME
    assert secretos.historial(ctx).conclusion is Conclusion.DESVIADO
    vigencia = secretos.vigencia(ctx)
    assert vigencia.conclusion is Conclusion.DESVIADO
    assert "ACEPTADO" in vigencia.resumen


def test_un_despliegue_que_acepta_el_valor_de_desarrollo_se_detecta(tmp_path):
    raiz = _repositorio(tmp_path, {".env.example": f"RASTRO_JWT_SECRETO={DESARROLLO}\n"})
    ctx = _contexto(raiz, entorno="aws", manejador=_sistema(DESARROLLO, []))

    resultado = secretos.vigencia(ctx)
    assert resultado.conclusion is Conclusion.DESVIADO


def test_en_local_el_valor_de_desarrollo_no_se_prueba(tmp_path):
    """La pila local usa el valor de desarrollo por diseno: no es un hallazgo."""
    raiz = _repositorio(tmp_path, {".env.example": f"RASTRO_JWT_SECRETO={DESARROLLO}\n"})
    recibidos: list[str] = []
    ctx = _contexto(raiz, entorno="local", manejador=_sistema(DESARROLLO, recibidos))

    resultado = secretos.vigencia(ctx)
    assert resultado.conclusion is Conclusion.CONFORME
    assert recibidos == []


def test_fuera_de_local_el_valor_de_desarrollo_se_prueba_aunque_nadie_lo_copie(tmp_path):
    raiz = _repositorio(tmp_path, {"README.md": "Rastro\n"})
    recibidos: list[str] = []
    ctx = _contexto(raiz, entorno="aws", manejador=_sistema(SECRETO_NUEVO, recibidos))

    resultado = secretos.vigencia(ctx)
    assert resultado.conclusion is Conclusion.CONFORME
    assert len(recibidos) == 1


def test_si_la_interfaz_no_responde_la_vigencia_queda_sin_ejecutar(tmp_path):
    def caido(_peticion):
        raise httpx.ConnectError("sin conexion")

    ctx = _contexto(_secreto_borrado(tmp_path), manejador=caido)
    assert secretos.vigencia(ctx).conclusion is Conclusion.NO_EJECUTADA


def test_un_rechazo_por_emisor_no_se_toma_por_firma_invalida(tmp_path):
    """Si el token se rechaza por el emisor, la prueba no llego a juzgar la firma."""
    ctx = _contexto(
        _secreto_borrado(tmp_path),
        manejador=_sistema(SECRETO_VIEJO, []),
        emisor="https://otro-emisor.invalid",
    )
    assert secretos.vigencia(ctx).conclusion is Conclusion.NO_EJECUTADA


def test_un_secreto_sin_prueba_de_uso_no_se_presume_invalidado(tmp_path):
    raiz = _repositorio(tmp_path, {"certificados/servidor.key": "contenido\n"})
    ctx = _contexto(raiz, manejador=_sistema(SECRETO_NUEVO, []))

    resultado = secretos.vigencia(ctx)
    assert resultado.conclusion is Conclusion.NO_EJECUTADA
    assert "certificados/servidor.key" in resultado.resumen


# --------------------------------------------------------------------------- #
# Ningun papel expone lo que encontro
# --------------------------------------------------------------------------- #


def test_ningun_resultado_contiene_el_secreto_ni_el_token(tmp_path):
    """Un papel que cita el secreto lo vuelve a exponer, y los papeles circulan."""
    raiz = _repositorio(
        tmp_path,
        {"config/.jwt.env": f"RASTRO_JWT_SECRETO={SECRETO_VIEJO}\n", "otro.env": f"RASTRO_JWT_SECRETO={SECRETO_NUEVO}\n"},
        {"config/.jwt.env": None},
    )
    recibidos: list[str] = []
    ctx = _contexto(raiz, manejador=_sistema(SECRETO_NUEVO, recibidos))

    texto = _serializado(secretos.arbol_actual(ctx), secretos.historial(ctx), secretos.vigencia(ctx))

    assert recibidos, "la prueba de vigencia deberia haber presentado tokens"
    for valor in (SECRETO_VIEJO, SECRETO_NUEVO, DESARROLLO, *recibidos):
        assert valor not in texto


def test_la_representacion_de_un_hallazgo_no_muestra_el_valor():
    hallado = secretos._extraer(f"RASTRO_JWT_SECRETO={SECRETO_VIEJO}", "config/.jwt.env", "abc1234", 1)[0]
    assert SECRETO_VIEJO not in repr(hallado)
    assert SECRETO_VIEJO not in json.dumps(hallado.como_dict())
