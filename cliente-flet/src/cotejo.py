"""Cotejo en Flet: escritorio, web y Android desde el mismo código.

    flet run src/cotejo.py            # ventana de escritorio
    flet run --web src/cotejo.py      # en el navegador
    flet build apk --module-name cotejo ...   # ver documentacion/modulos/cliente-flet
"""

import flet as ft

from cotejo_app.aplicacion import principal

if __name__ == "__main__":
    ft.run(principal)
