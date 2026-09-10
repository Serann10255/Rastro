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


#: Cada conclusion en una palabra que no haya que aprenderse. El termino tecnico
#: no se sustituye —es el que espera un tercero que lea el informe— pero deja de
#: ser la unica forma de saber que paso. Las tres siguen siendo tres: llamar
#: "sin revisar" a lo no ejecutado lo distingue de "bien" tanto como CONFORME lo
#: distingue de NO_EJECUTADA.
PALABRA_LLANA: dict[str, str] = {
    Conclusion.CONFORME: "BIEN",
    Conclusion.DESVIADO: "MAL",
    Conclusion.NO_EJECUTADA: "SIN REVISAR",
}

#: Que significa cada conclusion, para quien la lee por primera vez.
LLANO_EXPLICADO: dict[str, str] = {
    Conclusion.CONFORME: "Se probo y cumplio la regla escrita de antemano.",
    Conclusion.DESVIADO: "Se probo y no cumplio. Se convierte en un hallazgo.",
    Conclusion.NO_EJECUTADA: (
        "Ni bien ni mal: no se pudo probar aqui. Queda pendiente, no aprobado."
    ),
}


def en_palabras(conclusion: "Conclusion | str") -> str:
    """La conclusion en una palabra llana. Nunca sustituye al termino tecnico."""
    return PALABRA_LLANA.get(str(conclusion), str(conclusion))


class Severidad(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


@dataclass(frozen=True)
class Control:
    """Una fila de la matriz de controles.

    Lleva dos registros del mismo control: el tecnico, que es el que un tercero
    espera leer en un informe de auditoria, y el llano —`pregunta`, `en_simple`,
    `si_falla`—, que es el que permite discutirlo con quien decide. Ninguno
    sustituye al otro y los dos salen del catalogo, no de la interfaz: si cada
    pantalla escribiera su propia version, la consola y la web acabarian
    diciendo cosas distintas del mismo control.
    """

    id: str
    control: str
    marco: str
    tipo: TipoPrueba
    prueba: str
    procedimiento: str
    criterio: str
    evidencia_esperada: str
    severidad_si_desviado: Severidad
    pregunta: str = ""
    en_simple: str = ""
    si_falla: str = ""

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
            pregunta=" ".join(str(datos.get("pregunta", "")).split()),
            en_simple=" ".join(str(datos.get("en_simple", "")).split()),
            si_falla=" ".join(str(datos.get("si_falla", "")).split()),
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
    #: El mismo control en lenguaje llano, copiado del catalogo. Se conserva en
    #: el papel y no se resuelve al mostrarlo: un papel de trabajo debe poder
    #: leerse solo, anos despues, sin el catalogo de su epoca al lado.
    pregunta: str = ""
    en_simple: str = ""
    si_falla: str = ""

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["tipo"] = str(self.tipo)
        datos["conclusion"] = str(self.conclusion)
        #: Derivados, no almacenados: si manana cambia la palabra llana de una
        #: conclusion, cambia en un sitio y no en cada papel ya escrito.
        datos["conclusion_llana"] = en_palabras(self.conclusion)
        datos["conclusion_explicada"] = LLANO_EXPLICADO.get(str(self.conclusion), "")
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
    #: El mismo hallazgo contado sin vocabulario tecnico. Un hallazgo que solo
    #: entiende quien lo escribio no se corrige.
    en_simple: str = ""

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["severidad"] = str(self.severidad)
        return datos
