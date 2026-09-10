# Programa de auditoria Cotejo: interfaz HTTP sobre el mismo ejecutor que usa la
# linea de comandos. No hay una segunda implementacion que pudiera divergir.
#
# El contexto de construccion es la raiz del repositorio porque el programa
# reutiliza `rastro_core.audit`: el verificador de la cadena es el mismo codigo
# que la escribe. Esa reutilizacion se declara como limitacion en la
# documentacion: lo independiente es el recalculo sobre una copia descargada,
# no la implementacion del algoritmo.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY libs/ ./libs/
RUN pip install --no-cache-dir -e . \
 && pip install --no-cache-dir "uvicorn[standard]>=0.30" pyyaml httpx

COPY cotejo/ ./cotejo/

ENV COTEJO_DIR_PAPELES=/papeles
VOLUME ["/papeles"]

EXPOSE 8000

CMD ["sh", "-c", "uvicorn --app-dir /app/cotejo/api main:app --host 0.0.0.0 --port 8000"]
