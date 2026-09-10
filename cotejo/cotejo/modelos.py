"""Estructuras del programa de auditoria.

Un papel de trabajo conserva cuatro cosas: el procedimiento exacto que se
ejecuto, su salida literal sin editar, la marca de tiempo y la huella
criptografica del archivo de evidencia. Con menos que eso, la prueba no puede
repetirse y el informe vale lo que valga la confianza en quien lo firma.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


def marca_tiempo() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class TipoPrueba(StrEnum):
    CUMPLIMIENTO = "cumplimiento"
    SUSTANTIVA = "sustantiva"
    INTEGRIDAD = "integridad"


class Conclusion(StrEnum):
    CONFORME = "CONFORME"
    DESVIADO = "DESVIADO"
    #: La prueba no llego a ejecutarse. No es lo mismo que una desviacion y
    #: nunca debe confundirse con ella: un resultado ausente no es un hallazgo.
    NO_EJECUTADA = "NO_EJECUTADA"


class Severidad(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


@dataclass(frozen=True)
class Control:
    """Una fila de la matriz de controles."""

    id: str
    control: str
    marco: str
    tipo: TipoPrueba
    prueba: str
    procedimiento: str
    criterio: str
    evidencia_esperada: str
    severidad_si_desviado: Severidad

    @classmethod
    def desde_dict(cls, datos: dict) -> "Control":
        return cls(
            id=datos["id"],
            control=" ".join(datos["control"].split()),
            marco=datos["marco"],
            tipo=TipoPrueba(datos["tipo"]),
            prueba=datos["prueba"],
            procedimiento=" ".join(datos["procedimiento"].split()),
            criterio=" ".join(datos["criterio"].split()),
            evidencia_esperada=" ".join(datos["evidencia_esperada"].split()),
            severidad_si_desviado=Severidad(datos["severidad_si_desviado"]),
        )


@dataclass
class Observacion:
    """Un paso ejecutado dentro de una prueba, con su salida literal.

    Una prueba puede requerir varios pasos: consultar una configuracion,
    invocar una operacion, leer la bitacora. Cada paso se conserva por separado
    para que la evidencia muestre el razonamiento y no solo la conclusion.
    """

    procedimiento: str
    salida: Any
    ts: str = field(default_factory=marca_tiempo)
    error: str | None = None

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoPrueba:
    """Lo que devuelve una prueba antes de convertirse en papel de trabajo."""

    conclusion: Conclusion
    observaciones: list[Observacion]
    resumen: str
    detalle: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def no_ejecutada(cls, motivo: str, procedimiento: str = "") -> "ResultadoPrueba":
        return cls(
            conclusion=Conclusion.NO_EJECUTADA,
            observaciones=[Observacion(procedimiento=procedimiento, salida=None, error=motivo)],
            resumen=motivo,
        )


@dataclass
class PapelDeTrabajo:
    """Registro conservado de una prueba ejecutada."""

    ejecucion_id: str
    control_id: str
    control: str
    marco: str
    tipo: TipoPrueba
    procedimiento: str
    criterio: str
    evidencia_esperada: str
    conclusion: Conclusion
    resumen: str
    observaciones: list[dict]
    detalle: dict
    identidad_ejecucion: str
    iniciado_en: str
    terminado_en: str
    archivo_evidencia: str = ""
    huella_evidencia: str = ""

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["tipo"] = str(self.tipo)
        datos["conclusion"] = str(self.conclusion)
        return datos


@dataclass
class Hallazgo:
    """Una desviacion elevada a hallazgo.

    Enuncia condicion, criterio, causa y efecto, y remite al papel de trabajo
    que lo sustenta. Sin esa referencia el hallazgo es una afirmacion.
    """

    id: str
    control_id: str
    condicion: str
    criterio: str
    causa: str
    efecto: str
    severidad: Severidad
    recomendacion: str
    papel_de_trabajo: str
    huella_evidencia: str = ""
    permanente: bool = False

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["severidad"] = str(self.severidad)
        return datos
