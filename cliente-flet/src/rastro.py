"""Rastro en Flet: escritorio, web y Android desde el mismo código.

    flet run src/rastro.py            # ventana de escritorio
    flet run --web src/rastro.py      # en el navegador
    flet build apk --module-name rastro ...   # ver documentacion/modulos/cliente-flet
"""

import flet as ft

from rastro_app.aplicacion import principal

if __name__ == "__main__":
    ft.run(principal)
