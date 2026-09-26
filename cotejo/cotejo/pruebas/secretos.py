"""Ausencia de secretos en el repositorio (C-09a, C-09b y C-09c).

Surge de un incidente real: el secreto de firma de los tokens quedo versionado
en el repositorio publico y hubo que rotarlo (hallazgo H-01, 2026-09-26).
Ninguno de los ocho controles originales lo habria detectado.

Son tres comprobaciones y no una, porque "hay un secreto en el repositorio"
mezcla tres condiciones con riesgo muy distinto:

- C-09a, arbol actual: lo que hoy esta versionado en la rama.
- C-09b, historial: lo que estuvo versionado alguna vez. Borrar el archivo no
  lo saca de ahi.
- C-09c, vigencia: si lo hallado sigue siendo aceptado por el sistema auditado.
  Es lo que decide el riesgo residual: un secreto invalidado en el historial es
  una limpieza pendiente; uno vigente es una puerta abierta.

Separar arbol e historial no basta para distinguir lo vivo de lo invalidado. Un
secreto que se borro del arbol sin rotarlo sale bien en C-09a, mal en C-09b, y
sigue abriendo el sistema. Solo C-09c lo distingue, y por eso existe.

Regla sin excepcion: **ningun papel contiene el valor hallado.** Se reporta el
tipo, la ruta, el commit y los primeros 16 caracteres de la huella SHA-256, que
bastan para cruzarlo con otra evidencia sin revelarlo. Los papeles circulan
hacia el docente, y un papel que cita el secreto lo vuelve a exponer. Tampoco
el token fabricado en C-09c llega al papel.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..contexto import Contexto
from ..modelos import Conclusion, Observacion, ResultadoPrueba

# --------------------------------------------------------------------------- #
# Que cuenta como secreto: declarado antes de ejecutar
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Patron:
    tipo: str
    expresion: re.Pattern
    #: Por debajo de esta longitud el valor no puede ser un secreto real de ese
    #: tipo: es una referencia, un marcador o un valor de juguete.
    longitud_minima: int
    #: Si existe una prueba de uso contra el sistema auditado (C-09c).
    comprobable: bool


PATRONES: tuple[Patron, ...] = (
    # El sistema rechaza desplegar con un secreto de menos de 32 caracteres
    # (deploy/aws/30-funciones.sh), de modo que uno mas corto no puede ser el
    # que firma los tokens del despliegue.
    Patron(
        "secreto_de_firma",
        re.compile(r"RASTRO_JWT_SECRETO[\"']?\s*[:=]\s*[\"']?([^\s\"',}#`]+)"),
        32,
        True,
    ),
    Patron("id_de_clave_aws", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), 20, False),
    # Una clave secreta de AWS tiene 40 caracteres. La de MinIO local
    # (localsecreto) queda fuera por longitud, que es lo correcto: no abre nada.
    Patron(
        "clave_secreta_aws",
        re.compile(r"(?i)aws_secret_access_key[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9/+=]+)"),
        40,
        False,
    ),
    Patron(
        "token_de_sesion_aws",
        re.compile(r"(?i)aws_session_token[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9/+=]+)"),
        100,
        False,
    ),
    Patron("llave_privada", re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)"), 0, False),
)

#: Lo que git grep preselecciona; la decision la toman los patrones de arriba.
PRESELECCION = r"RASTRO_JWT_SECRETO|AKIA|ASIA|aws_secret_access_key|aws_session_token|PRIVATE KEY-----"

#: Archivos cuyo nombre ya dice que guardan un secreto, contengan lo que
#: contengan. `.env.example` no entra: es la plantilla, no el archivo.
NOMBRE_SENSIBLE = re.compile(
    r"(^|/)(\.jwt\.env|\.env|id_rsa|id_ed25519|credentials)$|\.(pem|p12|pfx|key)$"
)

#: Una referencia o un marcador, no un valor: ${VAR}, \$(openssl ...), %s, <...>.
MARCADOR = re.compile(r"^[$\\%<{\-]|^[.*xX]+$")

#: Valores publicos por diseno. No cuentan como hallazgo en C-09a ni en C-09b,
#: pero C-09c comprueba que el sistema desplegado no los acepte: un valor de
#: desarrollo publicado solo es aceptable mientras nada real lo acepte.
VALORES_DE_DESARROLLO: dict[str, str] = {
    "rastro-secreto-local-solo-para-desarrollo-32b": (
        "secreto del emisor local de docker compose (.env.example, "
        "docker-compose.yml y valor por omision de rastro_core.config)"
    ),
}


def _es_ejemplo_del_proveedor(valor: str) -> bool:
    """AWS publica claves de ejemplo que terminan en EXAMPLE o EXAMPLEKEY."""
    return "EXAMPLE" in valor


def huella_parcial(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Hallazgos
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Hallado:
    tipo: str
    ruta: str
    commit: str | None = None
    linea: int | None = None
    huella: str | None = None
    comprobable: bool = False
    #: El valor solo vive en memoria para la prueba de uso de C-09c. No entra en
    #: `como_dict` ni en la representacion del objeto.
    valor: str | None = None
    desarrollo: str | None = None

    def __repr__(self) -> str:  # nunca muestra el valor, ni por accidente
        return f"Hallado({self.tipo}, {self.ruta}, commit={self.commit}, huella={self.huella})"

    def como_dict(self) -> dict:
        datos = {"tipo": self.tipo, "ruta": self.ruta}
        if self.commit:
            datos["commit"] = self.commit
        if self.linea:
            datos["linea"] = self.linea
        if self.huella:
            datos["huella_sha256_parcial"] = self.huella
        if self.desarrollo:
            datos["valor_de_desarrollo_declarado"] = self.desarrollo
        return datos


def _extraer(linea: str, ruta: str, commit: str | None, numero: int | None) -> list[Hallado]:
    hallados = []
    for patron in PATRONES:
        for coincidencia in patron.expresion.finditer(linea):
            valor = coincidencia.group(1)
            if patron.longitud_minima and len(valor) < patron.longitud_minima:
                continue
            if MARCADOR.search(valor) or _es_ejemplo_del_proveedor(valor):
                continue
            con_valor = patron.tipo != "llave_privada"
            hallados.append(
                Hallado(
                    tipo=patron.tipo,
                    ruta=ruta,
                    commit=commit,
                    linea=numero,
                    huella=huella_parcial(valor) if con_valor else None,
                    comprobable=patron.comprobable,
                    valor=valor if patron.comprobable else None,
                    desarrollo=VALORES_DE_DESARROLLO.get(valor),
                )
            )
    return hallados


# --------------------------------------------------------------------------- #
# Acceso al repositorio
# --------------------------------------------------------------------------- #


class ErrorRepositorio(Exception):
    """No hay repositorio git que revisar: la prueba no puede ejecutarse."""


def _git(raiz: Path, *argumentos: str, codigos_validos=(0,)) -> str:
    try:
        salida = subprocess.run(
            ["git", "-C", str(raiz), "-c", "core.quotepath=off", *argumentos],
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise ErrorRepositorio("git no esta instalado en esta maquina") from exc
    if salida.returncode not in codigos_validos:
        mensaje = salida.stderr.decode("utf-8", "replace").strip()[:300]
        raise ErrorRepositorio(f"git {argumentos[0]} fallo en {raiz}: {mensaje}")
    return salida.stdout.decode("utf-8", "replace")


def revisar_arbol(raiz: Path) -> tuple[list[Hallado], dict]:
    """Secretos en el commit al que apunta HEAD."""
    commit = _git(raiz, "rev-parse", "--short", "HEAD").strip()
    archivos = [a for a in _git(raiz, "ls-tree", "-r", "--name-only", "HEAD").splitlines() if a]

    hallados: list[Hallado] = []
    # git grep devuelve 1 cuando no hay coincidencias: no es un error.
    salida = _git(
        raiz, "grep", "-I", "-n", "-i", "--no-color", "-E", PRESELECCION, "HEAD",
        codigos_validos=(0, 1),
    )
    for linea in salida.splitlines():
        partes = re.match(r"^HEAD:(.*?):(\d+):(.*)$", linea)
        if partes:
            ruta, numero, contenido = partes.group(1), int(partes.group(2)), partes.group(3)
            hallados.extend(_extraer(contenido, ruta, None, numero))

    con_contenido = {h.ruta for h in hallados}
    for ruta in archivos:
        if NOMBRE_SENSIBLE.search(ruta) and ruta not in con_contenido:
            hallados.append(Hallado(tipo="archivo_sensible", ruta=ruta))

    return hallados, {"commit_revisado": commit, "archivos_revisados": len(archivos)}


def revisar_historial(raiz: Path) -> tuple[list[Hallado], dict]:
    """Secretos agregados en cualquier commit alcanzable desde cualquier referencia."""
    total = int(_git(raiz, "rev-list", "--all", "--count").strip() or 0)
    salida = _git(
        raiz, "log", "--all", "-p", "-U0", "--no-color", "--no-ext-diff",
        "--format=@@COMMIT %h",
    )

    hallados: list[Hallado] = []
    vistos: set[tuple] = set()
    commit = ruta = None
    rutas_con_contenido: set[tuple] = set()
    for linea in salida.splitlines():
        if linea.startswith("@@COMMIT "):
            commit = linea.split()[1]
            continue
        if linea.startswith("+++ "):
            ruta = linea[6:] if linea.startswith("+++ b/") else None
            if ruta and NOMBRE_SENSIBLE.search(ruta):
                clave = (commit, ruta, "archivo_sensible", None)
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(Hallado(tipo="archivo_sensible", ruta=ruta, commit=commit))
            continue
        if ruta is None or not linea.startswith("+"):
            continue
        for hallado in _extraer(linea[1:], ruta, commit, None):
            clave = (commit, ruta, hallado.tipo, hallado.huella)
            if clave not in vistos:
                vistos.add(clave)
                hallados.append(hallado)
                rutas_con_contenido.add((commit, ruta))

    # Si el archivo sensible tambien tiene su contenido identificado, el
    # hallazgo por nombre sobra: es el mismo secreto contado dos veces.
    hallados = [
        h for h in hallados
        if not (h.tipo == "archivo_sensible" and (h.commit, h.ruta) in rutas_con_contenido)
    ]
    return hallados, {"commits_revisados": total, "referencias": "todas (--all)"}


def _describir(hallado: Hallado) -> str:
    donde = hallado.ruta
    if hallado.linea:
        donde += f":{hallado.linea}"
    if hallado.commit:
        donde += f" (commit {hallado.commit})"
    return f"{hallado.tipo} en {donde}"


def _repositorio(ctx: Contexto) -> Path:
    return Path(ctx.raiz_repositorio)


# --------------------------------------------------------------------------- #
# C-09a: arbol actual
# --------------------------------------------------------------------------- #


def arbol_actual(ctx: Contexto) -> ResultadoPrueba:
    raiz = _repositorio(ctx)
    procedimiento = f"git -C {raiz} grep -I -n -i -E '<patrones>' HEAD; git ls-tree -r HEAD"
    try:
        hallados, alcance = revisar_arbol(raiz)
    except ErrorRepositorio as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)

    secretos = [h for h in hallados if not h.desarrollo]
    desarrollo = [h for h in hallados if h.desarrollo]
    observacion = Observacion(
        procedimiento,
        {
            **alcance,
            "hallazgos": [h.como_dict() for h in secretos],
            "valores_de_desarrollo_declarados": [h.como_dict() for h in desarrollo],
        },
    )

    if secretos:
        fallos = [_describir(h) for h in secretos]
        return ResultadoPrueba(
            conclusion=Conclusion.DESVIADO,
            observaciones=[observacion],
            resumen=(
                f"{len(secretos)} secreto(s) versionado(s) en el arbol actual "
                f"(commit {alcance['commit_revisado']}): " + "; ".join(fallos)
            ),
            detalle={
                "fallos": fallos,
                "causa": (
                    "El archivo esta versionado en la rama: falta su exclusion en "
                    ".gitignore, o la exclusion se retiro."
                ),
            },
        )

    return ResultadoPrueba(
        conclusion=Conclusion.CONFORME,
        observaciones=[observacion],
        resumen=(
            f"Ningun secreto versionado en el arbol actual (commit "
            f"{alcance['commit_revisado']}, {alcance['archivos_revisados']} archivos). "
            f"Valores de desarrollo declarados: {len(desarrollo)}, cuya vigencia mide C-09c."
        ),
    )


# --------------------------------------------------------------------------- #
# C-09b: historial
# --------------------------------------------------------------------------- #


def historial(ctx: Contexto) -> ResultadoPrueba:
    raiz = _repositorio(ctx)
    procedimiento = f"git -C {raiz} log --all -p -U0 (lineas agregadas en cada commit)"
    try:
        hallados, alcance = revisar_historial(raiz)
        en_arbol = {(h.tipo, h.huella, h.ruta) for h in revisar_arbol(raiz)[0]}
    except ErrorRepositorio as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)

    secretos = [h for h in hallados if not h.desarrollo]
    registros = []
    for h in secretos:
        datos = h.como_dict()
        datos["sigue_en_el_arbol_actual"] = (h.tipo, h.huella, h.ruta) in en_arbol
        registros.append(datos)

    observacion = Observacion(
        procedimiento,
        {
            **alcance,
            "hallazgos": registros,
            "valores_de_desarrollo_declarados": len([h for h in hallados if h.desarrollo]),
        },
    )

    if secretos:
        fallos = [
            _describir(h) + ("" if r["sigue_en_el_arbol_actual"] else ", ya fuera del arbol actual")
            for h, r in zip(secretos, registros)
        ]
        commits = sorted({h.commit for h in secretos if h.commit})
        return ResultadoPrueba(
            conclusion=Conclusion.DESVIADO,
            observaciones=[observacion],
            resumen=(
                f"{len(secretos)} secreto(s) en el historial ({alcance['commits_revisados']} "
                "commits revisados): " + "; ".join(fallos)
                + ". Si siguen siendo validos lo mide C-09c."
            ),
            detalle={
                "fallos": fallos,
                "commits": commits,
                "causa": (
                    f"Se versiono en {', '.join(commits)}. Retirar el archivo despues "
                    "no lo saca del historial: cada commit conserva su contenido."
                ),
            },
        )

    return ResultadoPrueba(
        conclusion=Conclusion.CONFORME,
        observaciones=[observacion],
        resumen=f"Ningun secreto en el historial ({alcance['commits_revisados']} commits revisados).",
    )


# --------------------------------------------------------------------------- #
# C-09c: vigencia de lo hallado
# --------------------------------------------------------------------------- #

RUTA_DE_PRUEBA = "/auth/yo"
FIRMA_INVALIDA = "Signature verification failed"


def _probar(ctx: Contexto, valor: str) -> tuple[str, dict]:
    """Presenta un token firmado con `valor`. Devuelve rechazado, ACEPTADO o no comprobable.

    El token lleva emisor y audiencia correctos, de modo que lo unico que puede
    fallar es la firma. Va a nombre de un usuario inexistente y sin ningun rol:
    si el secreto resultara vigente, el token no tendria permiso para nada.
    """
    import httpx
    import jwt

    ahora = int(time.time())
    token = jwt.encode(
        {
            "iss": ctx.jwt_emisor,
            "aud": ctx.jwt_audiencia,
            "sub": "cotejo-c09c@prueba.invalid",
            "org": "org-inexistente-cotejo",
            "grupos": [],
            "iat": ahora,
            "exp": ahora + 120,
        },
        valor,
        algorithm="HS256",
    )
    try:
        respuesta = ctx.cliente.get(RUTA_DE_PRUEBA, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        return "no comprobable", {"error": f"{type(exc).__name__}: la interfaz no respondio"}
    finally:
        del token

    try:
        mensaje = str(respuesta.json().get("mensaje", ""))
    except (ValueError, AttributeError):
        mensaje = respuesta.text[:200]
    datos = {"ruta": f"GET {RUTA_DE_PRUEBA}", "codigo": respuesta.status_code, "mensaje": mensaje[:200]}

    if respuesta.status_code == 401 and FIRMA_INVALIDA in mensaje:
        return "rechazado", datos
    if respuesta.status_code == 401 and "Token de sesion invalido" in mensaje:
        # El token se rechazo por otra cosa (emisor, audiencia): la prueba no
        # llego a juzgar la firma, y presumir que la rechazo seria concluir sin
        # evidencia.
        return "no comprobable", datos
    return "ACEPTADO", datos


def vigencia(ctx: Contexto) -> ResultadoPrueba:
    raiz = _repositorio(ctx)
    procedimiento = (
        f"Por cada secreto de firma distinto hallado en {raiz} (arbol e historial), "
        f"firmar un token sin roles y presentarlo en GET {RUTA_DE_PRUEBA}"
    )
    try:
        hallados = revisar_arbol(raiz)[0] + revisar_historial(raiz)[0]
    except ErrorRepositorio as exc:
        return ResultadoPrueba.no_ejecutada(str(exc), procedimiento)

    # Un secreto se prueba una vez aunque aparezca en varios commits.
    por_huella: dict[str, Hallado] = {}
    sin_prueba: list[Hallado] = []
    for h in hallados:
        if h.desarrollo and ctx.es_local:
            continue  # en local el sistema usa el valor de desarrollo por diseno
        if h.comprobable and h.valor:
            por_huella.setdefault(h.huella, h)
        elif not h.desarrollo:
            sin_prueba.append(h)

    # Los valores de desarrollo se prueban fuera del entorno local aunque nadie
    # los haya copiado a otro archivo: si el despliegue los aceptara, cualquiera
    # que lea el repositorio tendria el secreto.
    if not ctx.es_local:
        for valor, descripcion in VALORES_DE_DESARROLLO.items():
            por_huella.setdefault(
                huella_parcial(valor),
                Hallado("secreto_de_firma", "declarado en la prueba", huella=huella_parcial(valor),
                        comprobable=True, valor=valor, desarrollo=descripcion),
            )

    pruebas, aceptados, no_comprobados = [], [], []
    for huella, hallado in por_huella.items():
        veredicto, datos = _probar(ctx, hallado.valor)
        registro = {
            "huella_sha256_parcial": huella,
            "origen": _describir(hallado),
            "valor_de_desarrollo": bool(hallado.desarrollo),
            "veredicto": veredicto,
            **datos,
        }
        pruebas.append(registro)
        if veredicto == "ACEPTADO":
            aceptados.append(registro)
        elif veredicto == "no comprobable":
            no_comprobados.append(registro)

    observacion = Observacion(
        procedimiento,
        {
            "entorno": ctx.entorno,
            "interfaz": ctx.url_api,
            "pruebas": pruebas,
            "hallazgos_sin_prueba_de_uso": [h.como_dict() for h in sin_prueba],
        },
    )

    if aceptados:
        fallos = [f"{r['origen']} (huella {r['huella_sha256_parcial']}) sigue siendo ACEPTADO" for r in aceptados]
        return ResultadoPrueba(
            conclusion=Conclusion.DESVIADO,
            observaciones=[observacion],
            resumen=f"{len(aceptados)} secreto(s) publicado(s) siguen abriendo el sistema: " + "; ".join(fallos),
            detalle={
                "fallos": fallos,
                "causa": "El secreto se publico y no se roto despues, o el despliegue usa un valor de desarrollo.",
            },
        )

    if no_comprobados or sin_prueba:
        pendientes = [r["origen"] for r in no_comprobados] + [_describir(h) for h in sin_prueba]
        return ResultadoPrueba(
            conclusion=Conclusion.NO_EJECUTADA,
            observaciones=[observacion],
            resumen=(
                "No se pudo comprobar la vigencia de: " + "; ".join(pendientes)
                + ". No se presume invalidado lo que no se probo."
            ),
        )

    if not pruebas:
        return ResultadoPrueba(
            conclusion=Conclusion.CONFORME,
            observaciones=[observacion],
            resumen="No se hallo ningun secreto de firma que probar.",
        )

    return ResultadoPrueba(
        conclusion=Conclusion.CONFORME,
        observaciones=[observacion],
        resumen=(
            f"Los {len(pruebas)} secreto(s) de firma probados son rechazados por firma "
            "invalida: " + "; ".join(r["origen"] for r in pruebas) + "."
        ),
    )
