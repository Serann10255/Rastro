"""Informe de auditoria: eleva las desviaciones a hallazgos.

Cada hallazgo enuncia condicion, criterio, causa y efecto, lleva severidad y
recomendacion, y remite al papel de trabajo que lo sustenta con su huella. Esa
referencia es lo que permite que un tercero siga el hallazgo hasta el comando
que lo produjo, y a la inversa.

El informe distingue tres cosas que no deben confundirse: lo conforme, lo
desviado y lo que no se pudo comprobar. Presentar lo tercero como lo primero
transmitiria una cobertura mayor que la real.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .modelos import (
    LLANO_EXPLICADO,
    Conclusion,
    Hallazgo,
    PapelDeTrabajo,
    Severidad,
    en_palabras,
    marca_tiempo,
)

ORDEN_SEVERIDAD = {Severidad.ALTA: 0, Severidad.MEDIA: 1, Severidad.BAJA: 2}


def construir_hallazgos(
    papeles: list[PapelDeTrabajo], catalogo: dict, ruta_catalogo: Path | None = None
) -> list[Hallazgo]:
    """Convierte cada desviacion en un hallazgo y anade los permanentes."""
    por_id = {c.id: c for c in catalogo["controles"]}
    hallazgos: list[Hallazgo] = []

    for indice, papel in enumerate(
        [p for p in papeles if p.conclusion is Conclusion.DESVIADO], start=1
    ):
        control = por_id[papel.control_id]
        hallazgos.append(
            Hallazgo(
                id=f"H-{indice:02d}",
                control_id=papel.control_id,
                condicion=papel.resumen,
                criterio=f"{papel.criterio} (referencia: {papel.marco})",
                causa=_causa_probable(papel),
                efecto=_efecto(control),
                severidad=control.severidad_si_desviado,
                recomendacion=_recomendacion(control),
                papel_de_trabajo=papel.archivo_evidencia,
                huella_evidencia=papel.huella_evidencia,
                # Lo que este hallazgo significa para quien no lee informes de
                # auditoria: el dano que el control existia para evitar.
                en_simple=control.si_falla,
            )
        )

    hallazgos.extend(_permanentes(catalogo))
    hallazgos.sort(key=lambda h: (ORDEN_SEVERIDAD[h.severidad], h.id))
    return hallazgos


def _permanentes(catalogo: dict) -> list[Hallazgo]:
    """Hallazgos que se reportan siempre, con o sin ejecucion.

    No se automatizan porque el entorno impide corregir la desviacion: una
    prueba que siempre da el mismo resultado no aporta informacion. Omitirlos
    del informe, en cambio, si transmitiria una cobertura falsa.
    """
    salida = []
    for entrada in catalogo.get("hallazgos_permanentes", []):
        salida.append(
            Hallazgo(
                id=entrada["id"],
                control_id="fuera del alcance automatizado",
                condicion=" ".join(entrada["condicion"].split()),
                criterio=" ".join(entrada["criterio"].split()),
                causa=" ".join(entrada["causa"].split()),
                efecto=" ".join(entrada["efecto"].split()),
                severidad=Severidad(entrada["severidad"]),
                recomendacion=" ".join(entrada["recomendacion"].split()),
                papel_de_trabajo=f"catalogo/controles.yaml#{entrada['id']}",
                permanente=True,
                en_simple=" ".join(str(entrada.get("en_simple", "")).split()),
            )
        )
    return salida


def _causa_probable(papel: PapelDeTrabajo) -> str:
    """La causa se deduce de la evidencia; cuando no se deduce, se dice."""
    fallos = papel.detalle.get("fallos") or []
    if any("FUGA" in f for f in fallos):
        return (
            "Alguna consulta de lectura no aplica el filtro por organizacion que "
            "la capa comun de acceso a datos impone."
        )
    if any("no quedo registrado" in f for f in fallos):
        return (
            "La operacion decide el rechazo pero no escribe el eslabon "
            "correspondiente en la bitacora."
        )
    if papel.tipo == "cumplimiento":
        return (
            "El recurso se creo o se modifico sin aplicar el control, o se aplico "
            "manualmente por consola y no mediante la secuencia de despliegue "
            "versionada."
        )
    return (
        "No se determina a partir de la evidencia recogida. Establecerla exige "
        "revisar el componente con su responsable tecnico."
    )


def _efecto(control) -> str:
    efectos = {
        "C-01": "Una modificacion de la infraestructura podria no quedar registrada, o el propio registro podria alterarse sin dejar rastro.",
        "C-02": "Las evidencias de entrega quedarian legibles para quien accediera al almacenamiento, y el sistema no podria acreditar su proteccion.",
        "C-03": "Las evidencias de entrega, que contienen datos de terceros, quedarian expuestas publicamente.",
        "C-04": "La sustitucion o el borrado de una evidencia de entrega seria irreversible e indetectable.",
        "C-05": "Un usuario podria ejecutar operaciones que no le corresponden, sin separacion de funciones ni rastro del intento.",
        "C-06": "Una empresa accederia a los datos de otra sobre la misma infraestructura compartida: es una fuga de informacion, no un defecto funcional.",
        "C-07": "El historico registraria secuencias imposibles y dejaria de servir como cadena de custodia.",
        "C-08": "La alteracion posterior del historico seria indetectable y el registro perderia su valor probatorio.",
    }
    return efectos.get(control.id, "Se pierde la propiedad que el control debia garantizar.")


def _recomendacion(control) -> str:
    recomendaciones = {
        "C-01": "Habilitar el registro con validacion de integridad mediante la secuencia de despliegue versionada (deploy/aws/50-registro.sh).",
        "C-02": "Aplicar cifrado por omision con la llave del proyecto y habilitar su rotacion (deploy/aws/10-datos.sh).",
        "C-03": "Activar los cuatro indicadores de bloqueo de acceso publico del contenedor.",
        "C-04": "Habilitar el versionado del contenedor de evidencias.",
        "C-05": "Revisar la matriz de autorizacion y comprobar que toda operacion registra tanto lo permitido como lo rechazado.",
        "C-06": "Revisar que toda consulta pase por la capa comun de acceso a datos y reciba el identificador de organizacion desde el token.",
        "C-07": "Revisar que la validacion de transiciones se aplique en el servidor y no solo en la interfaz.",
        "C-08": "Revisar el calculo del encadenamiento y el procedimiento de escritura de la bitacora.",
    }
    return recomendaciones.get(control.id, "Corregir la configuracion del control y volver a ejecutar el programa.")


# --------------------------------------------------------------------------- #
# Presentacion
# --------------------------------------------------------------------------- #


def redactar(
    metadatos: dict,
    cobertura: dict,
    papeles: list[PapelDeTrabajo],
    hallazgos: list[Hallazgo],
) -> str:
    """Informe en texto plano, versionable junto al codigo."""
    lineas: list[str] = []
    ancho = 78

    def titulo(texto: str) -> None:
        lineas.extend(["", "=" * ancho, texto.upper(), "=" * ancho, ""])

    lineas.append("INFORME DE AUDITORIA DE SISTEMAS")
    lineas.append(f"Programa: Cotejo | Sistema auditado: {metadatos['sistema_auditado']}")
    lineas.append(f"Ejecucion: {metadatos.get('ejecucion_id', 'sin id')}")
    lineas.append(f"Fecha: {marca_tiempo()}")
    lineas.append(f"Entorno: {metadatos['entorno']} | Region: {metadatos['region']}")
    lineas.append(f"Identidad de ejecucion: {metadatos['identidad_ejecucion']}")
    lineas.append(f"Catalogo: version {metadatos['version_catalogo']}")

    # El informe abre en lenguaje llano y sigue en el tecnico. El orden no es
    # cosmetico: quien decide sobre un hallazgo no suele ser quien lo escribio,
    # y un informe que exige vocabulario para llegar a la primera conclusion se
    # queda sin leer.
    titulo("1. En palabras simples")
    lineas.append("Que es esto")
    lineas.append(
        _parrafo(
            metadatos.get("que_es_esto")
            or "Cotejo comprueba si el sistema auditado cumple de verdad lo que promete.",
            ancho,
        )
    )
    lineas.append("")
    lineas.append("Que salio")
    lineas.append(_parrafo(frase_de_resultado(metadatos, cobertura), ancho))
    lineas.append("")
    lineas.append("Como se leen las tres respuestas")
    for conclusion in (Conclusion.CONFORME, Conclusion.DESVIADO, Conclusion.NO_EJECUTADA):
        etiqueta = f"{en_palabras(conclusion)} ({conclusion})"
        explicacion = _envolver_a(LLANO_EXPLICADO[conclusion], ancho - 30, 30)
        lineas.append(f"  {etiqueta:<28}{explicacion}")
    lineas.append("")
    lineas.append(
        _parrafo(
            "Las tres son distintas a proposito. Lo que no se pudo revisar no "
            "esta aprobado: esta pendiente, y se cuenta aparte para que nadie "
            "lea mas cobertura de la que hubo.",
            ancho,
        )
    )

    titulo("2. Alcance y cobertura")
    lineas.append(f"Controles del catalogo:      {cobertura['controles_del_catalogo']}")
    lineas.append(f"Controles con resultado:     {cobertura['controles_con_resultado']}")
    lineas.append(f"  Conformes:                 {cobertura['conformes']}")
    lineas.append(f"  Desviados:                 {cobertura['desviados']}")
    lineas.append(f"No ejecutados:               {cobertura['no_ejecutados']}")
    if cobertura["no_ejecutados"]:
        lineas.append("")
        lineas.append(
            "Un control no ejecutado no es un control conforme. Los siguientes no"
        )
        lineas.append("pudieron comprobarse y su conclusion queda pendiente:")
        for papel in papeles:
            if papel.conclusion is Conclusion.NO_EJECUTADA:
                lineas.append(f"  - {papel.control_id}: {papel.resumen}")

    titulo("3. Resultado por control")
    for papel in papeles:
        lineas.append(
            f"[{en_palabras(papel.conclusion)}] {papel.control_id} ({papel.tipo}) "
            f"| conclusion: {papel.conclusion}"
        )
        if papel.pregunta:
            lineas.append(_campo("Pregunta", papel.pregunta))
        if papel.en_simple:
            lineas.append(_campo("Que hicimos", papel.en_simple))
        lineas.append(_campo("Que paso", papel.resumen))
        if papel.si_falla and papel.conclusion is not Conclusion.CONFORME:
            lineas.append(_campo("Por que importa", papel.si_falla))
        lineas.append(_campo("Control", papel.control))
        lineas.append(_campo("Marco", papel.marco))
        lineas.append(_campo("Criterio", papel.criterio))
        lineas.append(_campo_crudo("Papel", papel.archivo_evidencia))
        lineas.append(_campo_crudo("Huella", papel.huella_evidencia))
        lineas.append("")

    titulo("4. Hallazgos")
    if not hallazgos:
        lineas.append("No se identificaron desviaciones en los controles ejecutados.")
    for hallazgo in hallazgos:
        marca = " (permanente)" if hallazgo.permanente else ""
        lineas.append(f"{hallazgo.id} | severidad {hallazgo.severidad}{marca} | {hallazgo.control_id}")
        if hallazgo.en_simple:
            lineas.append(_campo("En simple", hallazgo.en_simple))
        lineas.append(_campo("Condicion", hallazgo.condicion))
        lineas.append(_campo("Criterio", hallazgo.criterio))
        lineas.append(_campo("Causa", hallazgo.causa))
        lineas.append(_campo("Efecto", hallazgo.efecto))
        lineas.append(_campo("Recomendacion", hallazgo.recomendacion))
        lineas.append(_campo_crudo("Papel", hallazgo.papel_de_trabajo))
        if hallazgo.huella_evidencia:
            lineas.append(_campo_crudo("Huella", hallazgo.huella_evidencia))
        lineas.append("")

    titulo("5. Limitaciones declaradas")
    lineas.append(
        "Independencia. El equipo audita un sistema que el mismo construyo, lo que"
    )
    lineas.append(
        "constituye una amenaza de autorrevision. Se atiende con rotacion interna,"
    )
    lineas.append(
        "con un programa determinista cuyo resultado no depende del criterio de"
    )
    lineas.append(
        "quien lo ejecuta, y con la reejecucion por un integrante distinto. Aun asi,"
    )
    lineas.append(
        "este trabajo no alcanza el grado de independencia de una revision externa."
    )
    lineas.append("")
    lineas.append(
        "Cobertura. El programa verifica unicamente los controles del catalogo. Un"
    )
    lineas.append(
        "control ausente del catalogo no fue evaluado; el catalogo se deriva de los"
    )
    lineas.append("marcos citados para que su alcance sea una decision y no un olvido.")
    lineas.append("")
    lineas.append(
        "Reproducibilidad. Cada papel de trabajo conserva el procedimiento, la salida"
    )
    lineas.append(
        "literal, la fecha y la huella del archivo. Un tercero puede reejecutar el"
    )
    lineas.append("programa y comparar clasificaciones y huellas.")
    lineas.append("")

    return "\n".join(lineas)


def _envolver(texto: str, ancho: int) -> str:
    return _envolver_a(texto, ancho, _SANGRIA)


def _envolver_a(texto: str, ancho: int, sangria: int) -> str:
    import textwrap

    lineas = textwrap.wrap(texto, ancho) or [""]
    return ("\n" + " " * sangria).join(lineas)


#: Los campos se alinean a esta columna, que es donde continua el texto
#: envuelto. Cuando el termino y su valor no estan alineados, leer el informe
#: exige seguir la linea con el dedo.
_SANGRIA = 21


def _campo(termino: str, valor: str) -> str:
    etiqueta = f"{termino}:"
    return f"    {etiqueta:<{_SANGRIA - 4}}{_envolver(valor, 78 - _SANGRIA)}"


def _campo_crudo(termino: str, valor: str) -> str:
    """Igual que `_campo` pero sin envolver.

    Una ruta o una huella partida en dos lineas deja de poder copiarse, que es
    lo unico para lo que estan en el informe.
    """
    etiqueta = f"{termino}:"
    return f"    {etiqueta:<{_SANGRIA - 4}}{valor}"


def _parrafo(texto: str, ancho: int) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(texto, ancho) or [""])


def frase_de_resultado(metadatos: dict, cobertura: dict) -> str:
    """El resultado en una frase que se pueda leer en voz alta.

    Es la unica linea del informe que alguien va a repetir de memoria, asi que
    dice las tres cifras juntas: sin la tercera, "5 de 5 bien" suena a examen
    perfecto cuando en realidad quedaron tres preguntas sin responder.
    """

    def cosas(cantidad: int) -> str:
        return "1 cosa" if cantidad == 1 else f"{cantidad} cosas"

    total = cobertura["controles_del_catalogo"]
    sin_revisar = cobertura["no_ejecutados"]
    frase = (
        f"Revisamos {cosas(total)} que {metadatos.get('sistema_auditado', 'el sistema')} "
        f"dice cumplir. Salieron bien {cobertura['conformes']}, salieron mal "
        f"{cobertura['desviados']} y quedaron sin revisar {sin_revisar}."
    )
    if sin_revisar:
        frase += (
            f" Lo que quedo sin revisar no esta aprobado: en el entorno "
            f"'{metadatos.get('entorno', 'actual')}' no existen las piezas que "
            "esas pruebas miran, y hace falta ejecutarlas contra la cuenta "
            "desplegada."
        )
    if cobertura["desviados"]:
        frase += " Lo que salio mal esta abajo, con lo que habria que hacer."
    return frase


def escribir(
    destino: Path,
    metadatos: dict,
    cobertura: dict,
    papeles: list[PapelDeTrabajo],
    hallazgos: list[Hallazgo],
) -> dict[str, Path]:
    """Escribe el informe en texto y en JSON, junto a los papeles de trabajo."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    ruta_texto = destino / "informe.txt"
    ruta_texto.write_text(
        redactar(metadatos, cobertura, papeles, hallazgos), encoding="utf-8"
    )

    ruta_json = destino / "informe.json"
    ruta_json.write_text(
        json.dumps(
            {
                "metadatos": metadatos,
                "cobertura": cobertura,
                "controles": [p.como_dict() for p in papeles],
                "hallazgos": [h.como_dict() for h in hallazgos],
                "generado_en": marca_tiempo(),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    return {"texto": ruta_texto, "json": ruta_json}
