"""Evidencia de entrega: elegir la foto y cargarla en tres pasos.

Los tres pasos son operaciones distintas contra servicios distintos —pedir el
enlace prefirmado, subir el archivo directo al almacenamiento, confirmar que
quedó guardado—, y la pantalla los muestra por separado para que un fallo diga
dónde ocurrió en lugar de un «no se pudo cargar» que no dice nada.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import Any, Callable

import flet as ft

from comun import diseno as d
from comun import ui
from rastro_app.api import ClienteRastro

TIPOS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

PASOS = (
    ("solicitando", "Solicitar enlace prefirmado"),
    ("cargando", "Cargar el archivo al almacenamiento"),
    ("confirmando", "Confirmar que quedó almacenado"),
)


async def elegir_foto() -> ft.FilePickerFile | None:
    """Abre el selector de imágenes. En el teléfono ofrece la galería y la
    cámara; la foto se recomprime al 75 % para no gastar los datos del
    mensajero en una imagen de doce megapíxeles."""
    archivos = await ft.FilePicker().pick_files(
        dialog_title="Foto de la entrega",
        file_type=ft.FilePickerFileType.IMAGE,
        with_data=True,
        compression_quality=75,
    )
    return archivos[0] if archivos else None


def tipo_de(nombre: str) -> str:
    return TIPOS.get(PurePath(nombre).suffix.lower(), "image/jpeg")


async def cargar(
    api: ClienteRastro,
    envio_id: str,
    archivo: ft.FilePickerFile,
    al_cambiar_fase: Callable[[str], Any],
) -> dict[str, Any]:
    tipo = tipo_de(archivo.name)

    al_cambiar_fase("solicitando")
    enlace = await api.solicitar_enlace(envio_id, archivo.name, tipo)

    # El archivo va directo al almacenamiento: no atraviesa los servicios.
    al_cambiar_fase("cargando")
    await api.cargar_evidencia(enlace, archivo.bytes or b"")

    # El servicio no cree al cliente: comprueba el objeto antes de asociarlo.
    al_cambiar_fase("confirmando")
    confirmacion = await api.confirmar_evidencia(envio_id, enlace["evidencia_id"], tipo)

    al_cambiar_fase("lista")
    return confirmacion


@ft.component
def PasosCarga(fase: str) -> ft.Control:
    p = ui.paleta()
    indice_fase = next((i for i, (clave, _t) in enumerate(PASOS) if clave == fase), -1)
    filas = []
    for indice, (_clave, texto) in enumerate(PASOS):
        hecho = indice < indice_fase
        activo = indice == indice_fase
        filas.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.ProgressRing(width=14, height=14, stroke_width=2)
                        if activo
                        else ft.Text("✓" if hecho else str(indice + 1), size=d.T_XS, weight=ft.FontWeight.W_700),
                        width=24,
                        height=24,
                        border_radius=12,
                        bgcolor=p["exito-suave"] if hecho else p["acento-suave"] if activo else p["fondo-sutil"],
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(
                        texto,
                        size=d.T_SM,
                        color=p["texto"] if (hecho or activo) else p["texto-tenue"],
                        weight=ft.FontWeight.W_600 if activo else None,
                    ),
                ],
                spacing=d.E2,
            )
        )
    return ft.Column(filas, spacing=d.E2)


@ft.component
def VistaPrevia(archivo: ft.FilePickerFile | None) -> ft.Control:
    if archivo is None:
        return ft.Container()
    if archivo.bytes and tipo_de(archivo.name).startswith("image/"):
        return ft.Image(src=archivo.bytes, height=180, fit=ft.BoxFit.CONTAIN, border_radius=d.R_MD)
    return ui.Texto(f"{archivo.name} · {archivo.size} bytes", tono="texto-suave")
