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
NOMBRE_API_SITIO="${PREFIJO}-sitio"
NOMBRE_RASTRO_CLOUDTRAIL="${PREFIJO}-actividad"
GRUPO_USUARIOS="${PREFIJO}-usuarios"

RAIZ_PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCHIVO_CONFIG="${RAIZ_PROYECTO}/config/deployment.json"
DIR_EVIDENCIAS="${RAIZ_PROYECTO}/evidencias-despliegue"

# Los ocho microservicios. El nombre de la funcion se deriva del prefijo.
SERVICIOS=(auth shipments tracking evidence public audit masters dashboard)

# En Windows (Git Bash) la CLI de AWS es un ejecutable nativo: no entiende las
# rutas POSIX que van dentro de un argumento como fileb:///tmp/..., porque Git
# Bash solo convierte los argumentos que empiezan por "/". En Linux y macOS la
# ruta se devuelve tal cual.
ruta_nativa() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}

# Primer interprete capaz de importar boto3. En Windows, "python3" suele ser el
# de la Microsoft Store, sin dependencias, aunque haya otro correcto en el PATH.
# RASTRO_PYTHON permite fijarlo a mano.
elegir_python() {
  local candidato
  for candidato in "${RASTRO_PYTHON:-}" python3 python; do
    [[ -n "${candidato}" ]] || continue
    if "${candidato}" -c "import boto3" >/dev/null 2>&1; then
      command -v "${candidato}"
      return 0
    fi
  done
  return 1
}

# Primer resultado de una busqueda sobre una operacion paginada, o "None".
# Con --output text la CLI aplica --query a cada pagina por separado: pasadas
# las 25 rutas, una busqueda sin coincidencias devuelve "None" una vez por
# pagina, y compararlo con "None" daba por existente lo que no existia. Con
# json la CLI une las paginas antes de aplicar la consulta.
primer_resultado() {
  local salida
  salida="$(aws "$@" --output json)" || return 1
  salida="$(printf '%s' "${salida}" | tr -d '\r"')"
  [[ "${salida}" == "null" || -z "${salida}" ]] && salida="None"
  printf '%s' "${salida}"
}

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

# Origenes desde los que el sitio puede subir evidencias: el sitio de S3 por
# HTTP y, si ya existe, su entrada por HTTPS (etapa 65-sitio-https). La entrada
# se busca por nombre y no se lee de un archivo, de modo que la etapa de datos
# y la del sitio dejan la misma regla en cualquier orden. RASTRO_ORIGENES_WEB,
# separados por comas, sustituye la lista entera.
origenes_web() {
  if [[ -n "${RASTRO_ORIGENES_WEB:-}" ]]; then
    printf '%s' "${RASTRO_ORIGENES_WEB}"
    return
  fi
  local origenes="http://${BUCKET_WEB}.s3-website-${REGION}.amazonaws.com"
  local id_sitio
  id_sitio="$(primer_resultado apigatewayv2 get-apis --region "${REGION}" \
    --query "Items[?Name=='${NOMBRE_API_SITIO}'].ApiId | [0]")" || id_sitio="None"
  if [[ "${id_sitio}" != "None" && -n "${id_sitio}" ]]; then
    origenes+=",https://${id_sitio}.execute-api.${REGION}.amazonaws.com"
  fi
  printf '%s' "${origenes}"
}

# El dispositivo del mensajero sube la evidencia directamente al contenedor con
# un enlace prefirmado, desde el origen del sitio web. Sin CORS el navegador
# bloquea esa carga aunque la firma sea valida. En local no se nota porque
# MinIO acepta cualquier origen. Solo se admiten los origenes del sitio de
# Rastro: la firma autoriza la peticion, y el origen acota desde donde puede
# hacerse.
aplicar_cors_evidencias() {
  local origenes origenes_json
  origenes="$(origenes_web)"
  origenes_json="\"${origenes//,/\",\"}\""
  aws s3api put-bucket-cors --bucket "${BUCKET_EVIDENCIAS}" --cors-configuration "{
    \"CORSRules\": [{
      \"AllowedOrigins\": [${origenes_json}],
      \"AllowedMethods\": [\"PUT\", \"GET\"],
      \"AllowedHeaders\": [\"content-type\", \"x-amz-server-side-encryption\", \"x-amz-server-side-encryption-aws-kms-key-id\"],
      \"ExposeHeaders\": [\"ETag\", \"x-amz-version-id\"],
      \"MaxAgeSeconds\": 3600
    }]
  }"
  ok "CORS de carga directa en ${BUCKET_EVIDENCIAS} para ${origenes}"
}
