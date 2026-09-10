#!/usr/bin/env bash
# Empaqueta y despliega los seis microservicios como funciones de AWS Lambda.
#
# Cada microservicio es una funcion independiente con el mismo paquete: la capa
# comun y el codigo del servicio. Comparten el rol de ejecucion LabRole porque
# el laboratorio no permite crear roles (restriccion RE-01). Esto incumple el
# principio de minimo privilegio y se declara como limitacion conocida en el
# informe final: la recomendacion para un despliegue productivo es un rol por
# funcion con politicas acotadas.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

DIR_TRABAJO="$(mktemp -d)"
trap 'rm -rf "${DIR_TRABAJO}"' EXIT

paso "Empaquetado de las funciones"

# Las dependencias se instalan para la plataforma de destino y no para la del
# equipo de desarrollo: el paquete se ejecuta en Linux, no en la maquina local.
python -m pip install --quiet \
  --target "${DIR_TRABAJO}/paquete" \
  --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.12 --only-binary=:all: --upgrade \
  fastapi pydantic mangum pyjwt cryptography >/dev/null
ok "dependencias instaladas para linux/x86_64 y python 3.12"

cp -r "${RAIZ_PROYECTO}/libs/rastro_core" "${DIR_TRABAJO}/paquete/"
ok "capa comun incluida en el paquete"

desplegar_funcion() {
  local servicio="$1"
  local nombre="${PREFIJO}-${servicio}"
  local destino="${DIR_TRABAJO}/${servicio}"

  cp -r "${DIR_TRABAJO}/paquete" "${destino}"
  cp "${RAIZ_PROYECTO}/services/${servicio}/main.py" "${destino}/main.py"

  # El manejador que Lambda invoca. Es la unica diferencia entre correr como
  # contenedor y correr como funcion: la aplicacion es exactamente la misma.
  cat > "${destino}/manejador.py" <<'PY'
"""Punto de entrada de la funcion. Adapta la aplicacion HTTP a Lambda."""
from mangum import Mangum

from main import app

manejador = Mangum(app, lifespan="off")
PY

  (cd "${destino}" && zip -qr "${DIR_TRABAJO}/${servicio}.zip" .)

  local variables="Variables={RASTRO_ENTORNO=aws,RASTRO_TABLA_ENVIOS=${TABLA_ENVIOS},RASTRO_TABLA_BITACORA=${TABLA_BITACORA},RASTRO_TABLA_MAESTROS=${TABLA_MAESTROS},RASTRO_BUCKET_EVIDENCIAS=${BUCKET_EVIDENCIAS},RASTRO_ALIAS_LLAVE=${ALIAS_LLAVE},RASTRO_ACCOUNT_ID=${CUENTA},RASTRO_JWT_EMISOR=${EMISOR},RASTRO_JWT_AUDIENCIA=${AUDIENCIA},RASTRO_JWT_SECRETO=${SECRETO_JWT},RASTRO_VIGENCIA_ENLACE=300,RASTRO_VIGENCIA_TOKEN=3600,RASTRO_VIGENCIA_REFRESCO=43200}"

  if existe_funcion "${nombre}"; then
    aws lambda update-function-code --region "${REGION}" \
      --function-name "${nombre}" --zip-file "fileb://${DIR_TRABAJO}/${servicio}.zip" >/dev/null
    aws lambda wait function-updated --region "${REGION}" --function-name "${nombre}"
    aws lambda update-function-configuration --region "${REGION}" \
      --function-name "${nombre}" --environment "${variables}" >/dev/null
    ok "funcion actualizada: ${nombre}"
  else
    aws lambda create-function --region "${REGION}" \
      --function-name "${nombre}" \
      --runtime python3.12 \
      --role "${ROL_EJECUCION}" \
      --handler manejador.manejador \
      --timeout 15 \
      --memory-size 512 \
      --zip-file "fileb://${DIR_TRABAJO}/${servicio}.zip" \
      --environment "${variables}" \
      --tags proyecto="${PREFIJO}" >/dev/null
    aws lambda wait function-active --region "${REGION}" --function-name "${nombre}"
    ok "funcion creada: ${nombre}"
  fi
}

paso "Despliegue de las funciones"

# Las variables de identidad las produjo la etapa anterior.
if [[ -f "${RAIZ_PROYECTO}/config/.identidad.env" ]]; then
  # shellcheck source=/dev/null
  source "${RAIZ_PROYECTO}/config/.identidad.env"
else
  aviso "no hay datos de identidad; ejecute antes 20-identidad.sh"
  exit 1
fi

# Secreto de firma del token. Si no se fija, se usa el valor de desarrollo, que
# esta en el repositorio y por lo tanto no protege nada: cualquiera que lo lea
# puede firmar un token de administrador de cualquier organizacion.
SECRETO_JWT="${RASTRO_JWT_SECRETO:-}"
if [[ -z "${SECRETO_JWT}" ]]; then
  aviso "RASTRO_JWT_SECRETO no esta definido."
  aviso "Genere uno y expórtelo antes de desplegar:"
  aviso "    export RASTRO_JWT_SECRETO=\$(openssl rand -base64 48)"
  aviso "Guardelo: si cambia, todas las sesiones abiertas dejan de valer."
  exit 1
fi
if [[ "${#SECRETO_JWT}" -lt 32 ]]; then
  aviso "El secreto debe tener al menos 32 caracteres."
  exit 1
fi
ok "secreto de firma configurado (${#SECRETO_JWT} caracteres)"

# El servicio de identidad si se despliega: el sistema tiene su propio
# directorio de usuarios y administra las cuentas desde la aplicacion.
for servicio in "${SERVICIOS[@]}"; do
  desplegar_funcion "${servicio}"
done

paso "Funciones desplegadas"
