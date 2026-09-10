#!/usr/bin/env bash
# Variables y utilidades compartidas por la secuencia de despliegue.
#
# REQ-09 (portabilidad): ningun identificador propio de la cuenta se escribe a
# mano. El numero de cuenta se consulta a la propia sesion, el nombre del
# contenedor se deriva de el, el rol de ejecucion se referencia por nombre y la
# llave de cifrado por alias. Trasladar el sistema a otra cuenta del laboratorio
# se reduce entonces a volver a ejecutar esta secuencia.

set -euo pipefail

PREFIJO="${RASTRO_PREFIJO:-rastro}"
REGION="${AWS_REGION:-us-east-1}"

# La cuenta se consulta, no se declara. Si las credenciales de la sesion
# caducaron (ocurre cada cuatro horas en el laboratorio), esto falla aqui y no
# a mitad del despliegue, con recursos creados a medias.
if ! CUENTA="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"; then
  echo "ERROR: no hay sesion valida de AWS. Recargue las credenciales del laboratorio." >&2
  exit 1
fi

# El rol se referencia por nombre y no por ruta completa: su ARN cambia con la
# cuenta, su nombre no. Es el rol unico y de permisos amplios que impone el
# laboratorio (restriccion RE-01), documentado como limitacion conocida.
NOMBRE_ROL="${RASTRO_ROL:-LabRole}"
ROL_EJECUCION="arn:aws:iam::${CUENTA}:role/${NOMBRE_ROL}"

TABLA_ENVIOS="${PREFIJO}-envios"
TABLA_BITACORA="${PREFIJO}-bitacora"
TABLA_MAESTROS="${PREFIJO}-maestros"
BUCKET_EVIDENCIAS="${PREFIJO}-evidencias-${CUENTA}"
BUCKET_REGISTRO="${PREFIJO}-registro-${CUENTA}"
BUCKET_WEB="${PREFIJO}-web-${CUENTA}"
ALIAS_LLAVE="alias/${PREFIJO}"
NOMBRE_API="${PREFIJO}-api"
NOMBRE_RASTRO_CLOUDTRAIL="${PREFIJO}-actividad"
GRUPO_USUARIOS="${PREFIJO}-usuarios"

RAIZ_PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCHIVO_CONFIG="${RAIZ_PROYECTO}/config/deployment.json"
DIR_EVIDENCIAS="${RAIZ_PROYECTO}/evidencias-despliegue"

# Los ocho microservicios. El nombre de la funcion se deriva del prefijo.
SERVICIOS=(auth shipments tracking evidence public audit masters dashboard)

paso()  { printf '\n=== %s ===\n' "$*"; }
ok()    { printf '  [ok] %s\n' "$*"; }
aviso() { printf '  [!!] %s\n' "$*" >&2; }

# Guarda la salida literal de un comando con su marca de tiempo. Es la evidencia
# que exige el plan de trabajo: comando ejecutado, salida completa y fecha, de
# modo que un tercero pueda repetir la verificacion.
registrar_evidencia() {
  local nombre="$1"; shift
  mkdir -p "${DIR_EVIDENCIAS}"
  local destino="${DIR_EVIDENCIAS}/$(date -u +%Y%m%dT%H%M%SZ)-${nombre}.txt"
  {
    echo "# comando: $*"
    echo "# cuenta: ${CUENTA}  region: ${REGION}"
    echo "# fecha: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "---"
    "$@" 2>&1 || true
  } | tee "${destino}"
}

existe_tabla() { aws dynamodb describe-table --table-name "$1" --region "${REGION}" >/dev/null 2>&1; }
existe_bucket() { aws s3api head-bucket --bucket "$1" >/dev/null 2>&1; }
existe_funcion() { aws lambda get-function --function-name "$1" --region "${REGION}" >/dev/null 2>&1; }
