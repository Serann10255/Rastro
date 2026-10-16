"""Cotejo como funcion Lambda: papeles en S3 y ejecucion diferida.

En AWS la funcion no conserva su disco y API Gateway corta a los 30 segundos.
Estas pruebas fijan las dos cosas que el punto de entrada (``api/aws.py``)
resuelve, con S3 y Lambda simulados: que lo escrito en una peticion llega al
almacen y se recupera en otro contenedor byte a byte, y que encargar una
ejecucion responde enseguida y deja constancia de como termino.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_API = Path(__file__).resolve().parents[1] / "api"


class S3Simulado:
    def __init__(self) -> None:
        self.objetos: dict[str, bytes] = {}

    def get_paginator(self, _nombre):
        objetos = self.objetos

        class Paginador:
            def paginate(self, Bucket, Prefix):  # noqa: N803 - firma de boto3
                yield {
                    "Contents": [
                        {"Key": clave, "Size": len(datos)}
                        for clave, datos in sorted(objetos.items())
                        if clave.startswith(Prefix)
                    ]
                }

        return Paginador()

    def upload_file(self, ruta, _bucket, clave):
        self.objetos[clave] = Path(ruta).read_bytes()

    def download_file(self, _bucket, clave, ruta):
        Path(ruta).write_bytes(self.objetos[clave])


class LambdaSimulado:
    def __init__(self) -> None:
        self.invocaciones: list[dict] = []

    def invoke(self, **argumentos):
        self.invocaciones.append({**argumentos, "Payload": json.loads(argumentos["Payload"])})


AUDITOR = {"sub": "u-aud", "email": "auditor@andes.test", "org_id": "org-andes"}


@pytest.fixture
def nube(monkeypatch, tmp_path):
    monkeypatch.setenv("COTEJO_BUCKET_PAPELES", "papeles-de-prueba")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "rastro-cotejo")
    monkeypatch.syspath_prepend(str(RAIZ_API))

    main = importlib.import_module("main")
    sys.modules.pop("aws", None)
    aws = importlib.import_module("aws")

    papeles = tmp_path / "papeles"
    papeles.mkdir()
    s3, lambda_ = S3Simulado(), LambdaSimulado()
    monkeypatch.setattr(aws, "_s3", s3)
    monkeypatch.setattr(aws, "_lambda", lambda_)
    monkeypatch.setattr(aws, "DIR_PAPELES", papeles)
    monkeypatch.setattr(main, "DIR_PAPELES", papeles)
    monkeypatch.setattr(main, "DIR_ESTADOS", papeles / "_estados")
    # Importar aws.py fija el lanzador; se restituye al terminar para que el
    # resto de las pruebas siga viendo la ejecucion en linea de local.
    monkeypatch.setattr(main, "LANZADOR", aws._lanzar)
    main.app.dependency_overrides[main.auditor] = lambda: AUDITOR

    yield {"main": main, "aws": aws, "s3": s3, "lambda": lambda_, "papeles": papeles}
    main.app.dependency_overrides.clear()


def _informe_falso(nube):
    """Sustituye el recorrido real del catalogo: aqui se prueba el transporte."""

    def completar(ejecucion_id, solo, quien):
        base = nube["papeles"] / ejecucion_id
        (base / "evidencias").mkdir(parents=True)
        (base / "evidencias" / "C-05.json").write_text('{"respuesta": 403}', encoding="utf-8")
        (base / "informe.json").write_text(
            json.dumps({"ejecucion_id": ejecucion_id, "solicitada_por": quien["sub"]}),
            encoding="utf-8",
        )
        return {"ejecucion_id": ejecucion_id}

    return completar


def test_encargar_una_ejecucion_responde_enseguida_y_la_lanza_aparte(nube):
    with TestClient(nube["main"].app) as cliente:
        respuesta = cliente.post("/ejecuciones", json={"solo": ["C-05"]})

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "en_curso"
    ejecucion_id = cuerpo["ejecucion_id"]

    (invocacion,) = nube["lambda"].invocaciones
    assert invocacion["InvocationType"] == "Event"
    assert invocacion["FunctionName"] == "rastro-cotejo"
    assert invocacion["Payload"] == {
        "cotejo": "ejecutar",
        "ejecucion_id": ejecucion_id,
        "solo": ["C-05"],
        "quien": AUDITOR,
    }
    # El estado ya esta en el almacen: la interfaz preguntara desde otro contenedor.
    assert f"papeles/_estados/{ejecucion_id}.json" in nube["s3"].objetos


def test_la_ejecucion_diferida_deja_sus_papeles_en_el_almacen(nube, monkeypatch):
    monkeypatch.setattr(nube["main"], "completar_ejecucion", _informe_falso(nube))

    nube["aws"].manejador(
        {"cotejo": "ejecutar", "ejecucion_id": "20261016T160000000Z-abc123", "solo": None, "quien": AUDITOR},
        None,
    )

    objetos = nube["s3"].objetos
    assert objetos["papeles/20261016T160000000Z-abc123/evidencias/C-05.json"] == b'{"respuesta": 403}'
    assert "papeles/20261016T160000000Z-abc123/informe.json" in objetos
    estado = json.loads(objetos["papeles/_estados/20261016T160000000Z-abc123.json"])
    assert estado["estado"] == "lista"


def test_otro_contenedor_recupera_los_papeles_tal_cual(nube, monkeypatch, tmp_path):
    monkeypatch.setattr(nube["main"], "completar_ejecucion", _informe_falso(nube))
    nube["aws"].manejador(
        {"cotejo": "ejecutar", "ejecucion_id": "20261016T160000000Z-abc123", "solo": None, "quien": AUDITOR},
        None,
    )

    # Un contenedor nuevo empieza con el disco vacio.
    vacio = tmp_path / "otro-contenedor"
    vacio.mkdir()
    for modulo, atributo, valor in (
        (nube["aws"], "DIR_PAPELES", vacio),
        (nube["main"], "DIR_PAPELES", vacio),
        (nube["main"], "DIR_ESTADOS", vacio / "_estados"),
    ):
        monkeypatch.setattr(modulo, atributo, valor)

    nube["aws"]._traer()

    assert (vacio / "20261016T160000000Z-abc123" / "evidencias" / "C-05.json").read_bytes() == (
        b'{"respuesta": 403}'
    )
    with TestClient(nube["main"].app) as cliente:
        estado = cliente.get("/ejecuciones/20261016T160000000Z-abc123/estado").json()
    assert estado == {"ejecucion_id": "20261016T160000000Z-abc123", "estado": "lista"}


def test_lo_traido_no_se_vuelve_a_subir(nube, monkeypatch):
    pytest.importorskip("mangum", reason="el adaptador de Lambda solo viaja en el paquete")
    nube["s3"].objetos["papeles/viejo/informe.json"] = b"{}"
    subidos: list[str] = []
    original = nube["s3"].upload_file
    monkeypatch.setattr(
        nube["s3"], "upload_file", lambda ruta, b, clave: (subidos.append(clave), original(ruta, b, clave))
    )

    nube["aws"].manejador(
        {"version": "2.0", "routeKey": "GET /salud", "rawPath": "/salud", "rawQueryString": "",
         "headers": {}, "requestContext": {"http": {"method": "GET", "path": "/salud",
         "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}, "stage": "$default"}, "isBase64Encoded": False},
        None,
    )

    assert subidos == []


def test_una_ejecucion_que_falla_queda_anotada_y_no_se_reintenta(nube, monkeypatch):
    def falla(*_argumentos):
        raise RuntimeError("Rastro no respondio")

    monkeypatch.setattr(nube["main"], "completar_ejecucion", falla)

    # No lanza: Lambda reintentaria la invocacion asincrona.
    nube["aws"].manejador(
        {"cotejo": "ejecutar", "ejecucion_id": "20261016T160000000Z-def456", "solo": None, "quien": AUDITOR},
        None,
    )

    estado = json.loads(nube["s3"].objetos["papeles/_estados/20261016T160000000Z-def456.json"])
    assert estado["estado"] == "fallida"
    assert "Rastro no respondio" in estado["motivo"]


def test_en_local_la_ejecucion_sigue_dentro_de_la_peticion(nube, monkeypatch):
    monkeypatch.setattr(nube["main"], "LANZADOR", None)
    monkeypatch.setattr(nube["main"], "completar_ejecucion", lambda *a: {"ejecucion_id": "x", "metadatos": {}})

    with TestClient(nube["main"].app) as cliente:
        respuesta = cliente.post("/ejecuciones", json={})

    assert respuesta.status_code == 201
    assert nube["lambda"].invocaciones == []
