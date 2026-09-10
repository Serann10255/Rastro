# Imagen unica para los seis microservicios.
#
# El servicio concreto se elige con la variable SERVICIO en tiempo de ejecucion.
# Una sola imagen mantiene identica la capa comun en todos los procesos, que es
# lo que permite afirmar que el control de aislamiento se implementa una sola
# vez y corre igual en todos ellos.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY libs/ ./libs/
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir "uvicorn[standard]>=0.30"

COPY services/ ./services/
COPY seed/ ./seed/

ENV SERVICIO=shipments \
    PUERTO=8000

EXPOSE 8000

# Sin recarga automatica y con un solo proceso: en AWS cada servicio es una
# funcion Lambda de un unico manejador, y el contenedor reproduce esa forma.
CMD ["sh", "-c", "uvicorn --app-dir /app/services/${SERVICIO} main:app --host 0.0.0.0 --port ${PUERTO}"]
