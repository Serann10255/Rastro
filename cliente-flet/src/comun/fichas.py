"""Colores del sistema de diseño, traducidos de `design/` a Python.

GENERADO por `cliente-flet/herramientas/generar_fichas.py`. No editar a mano:
cambie el CSS de `design/` o el `identidad.css` de la aplicación y regenere.
"""

# Fichas compartidas por las dos aplicaciones, por tema.
BASE = {
    "claro": {
        "acento": "#1d4f91",
        "acento-borde": "#b9d0ec",
        "acento-fuerte": "#163c70",
        "acento-suave": "#e7effa",
        "alerta": "#8a5a00",
        "alerta-borde": "#e8cf9a",
        "alerta-suave": "#fbf1dc",
        "borde": "#dde2ea",
        "borde-fuerte": "#c3ccd9",
        "exito": "#1a6b46",
        "exito-borde": "#a8d7c1",
        "exito-suave": "#e2f2ea",
        "fondo": "#f4f6f9",
        "fondo-sutil": "#eaeef4",
        "info": "#1d4f91",
        "info-suave": "#e7effa",
        "marca-1": "#1d4f91",
        "marca-2": "#17a2b8",
        "marca-contraste": "#ffffff",
        "peligro": "#9b2226",
        "peligro-borde": "#eeb7b8",
        "peligro-suave": "#fbe8e8",
        "superficie": "#ffffff",
        "superficie-elevada": "#ffffff",
        "superficie-hundida": "#f7f9fc",
        "texto": "#16202c",
        "texto-invertido": "#ffffff",
        "texto-suave": "#55637a",
        "texto-tenue": "#8390a5",
    },
    "oscuro": {
        "acento": "#7cb0f0",
        "acento-borde": "#274a70",
        "acento-fuerte": "#a3c8f7",
        "acento-suave": "#16283d",
        "alerta": "#e0b062",
        "alerta-borde": "#55441f",
        "alerta-suave": "#2b2311",
        "borde": "#2a3644",
        "borde-fuerte": "#3a4756",
        "exito": "#64cea0",
        "exito-borde": "#23503c",
        "exito-suave": "#12291f",
        "fondo": "#0e131a",
        "fondo-sutil": "#131a23",
        "info": "#7cb0f0",
        "info-suave": "#16283d",
        "peligro": "#f0898c",
        "peligro-borde": "#58292c",
        "peligro-suave": "#2e1618",
        "superficie": "#171f29",
        "superficie-elevada": "#1d2732",
        "superficie-hundida": "#121922",
        "texto": "#e9eef5",
        "texto-invertido": "#0e131a",
        "texto-suave": "#a3b0c2",
        "texto-tenue": "#7b8899",
    },
}

# Lo único que cada aplicación cambia: la marca y, en Cotejo, el acento.
MARCAS = {
    "rastro": {
        "claro": {
            "marca-1": "#1d4f91",
            "marca-2": "#17a2b8",
            "marca-contraste": "#ffffff",
        },
        "oscuro": {
            "marca-1": "#4a90e2",
            "marca-2": "#2fc4dd",
        },
    },
    "cotejo": {
        "claro": {
            "acento": "#4c3d9c",
            "acento-borde": "#cdc4f0",
            "acento-fuerte": "#3a2f7a",
            "acento-suave": "#eeebfa",
            "info": "#4c3d9c",
            "info-suave": "#eeebfa",
            "marca-1": "#4c3d9c",
            "marca-2": "#8b5cf6",
            "marca-contraste": "#ffffff",
        },
        "oscuro": {
            "acento": "#a78bfa",
            "acento-borde": "#3f3568",
            "acento-fuerte": "#c4a5fd",
            "acento-suave": "#241f3d",
            "info": "#a78bfa",
            "info-suave": "#241f3d",
            "marca-1": "#a78bfa",
            "marca-2": "#c4a5fd",
        },
    },
}

# Ficha que colorea cada estado del envío.
COLOR_POR_ESTADO = {
    "ASIGNADO": "acento",
    "CANCELADO": "texto-suave",
    "CREADO": "acento",
    "DEVUELTO": "texto-suave",
    "ENTREGADO": "exito",
    "EN_REPARTO": "alerta",
    "EN_TRANSITO": "alerta",
    "INCIDENCIA": "peligro",
    "RECOLECTADO": "alerta",
}
