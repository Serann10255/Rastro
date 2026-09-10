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

from .modelos import Conclusion, Hallazgo, PapelDeTrabajo, Severidad, marca_tiempo

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

    titulo("1. Alcance y cobertura")
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

    titulo("2. Resultado por control")
    for papel in papeles:
        lineas.append(f"[{papel.conclusion}] {papel.control_id} ({papel.tipo})")
        lineas.append(f"    Control:   {_envolver(papel.control, 68)}")
        lineas.append(f"    Marco:     {papel.marco}")
        lineas.append(f"    Criterio:  {_envolver(papel.criterio, 68)}")
        lineas.append(f"    Resultado: {_envolver(papel.resumen, 68)}")
        lineas.append(f"    Papel:     {papel.archivo_evidencia}")
        lineas.append(f"    Huella:    {papel.huella_evidencia}")
        lineas.append("")

    titulo("3. Hallazgos")
    if not hallazgos:
        lineas.append("No se identificaron desviaciones en los controles ejecutados.")
    for hallazgo in hallazgos:
        marca = " (permanente)" if hallazgo.permanente else ""
        lineas.append(f"{hallazgo.id} | severidad {hallazgo.severidad}{marca} | {hallazgo.control_id}")
        lineas.append(f"    Condicion:      {_envolver(hallazgo.condicion, 64)}")
        lineas.append(f"    Criterio:       {_envolver(hallazgo.criterio, 64)}")
        lineas.append(f"    Causa:          {_envolver(hallazgo.causa, 64)}")
        lineas.append(f"    Efecto:         {_envolver(hallazgo.efecto, 64)}")
        lineas.append(f"    Recomendacion:  {_envolver(hallazgo.recomendacion, 64)}")
        lineas.append(f"    Papel:          {hallazgo.papel_de_trabajo}")
        if hallazgo.huella_evidencia:
            lineas.append(f"    Huella:         {hallazgo.huella_evidencia}")
        lineas.append("")

    titulo("4. Limitaciones declaradas")
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
    import textwrap

    lineas = textwrap.wrap(texto, ancho) or [""]
    return ("\n" + " " * 20).join(lineas)


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
