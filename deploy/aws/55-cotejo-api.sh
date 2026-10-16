#!/usr/bin/env bash
# Programa de auditoria (Cotejo) como funcion Lambda detras de API Gateway.
#
# Opcional: solo con RASTRO_PUBLICAR_COTEJO=si. Por omision Cotejo se ejecuta
# desde la maquina del auditor, que es lo que su independencia pide. Publicarlo
# aqui lo pone dentro de la cuenta auditada y con su mismo rol (LabRole): es una
# perdida de independencia que se declara en el ADR-015, no un detalle.
#
# Crea tres cosas:
#   - el contenedor de papeles de trabajo, privado, cifrado y con versionado:
#     el disco de una funcion no dura, y los papeles son evidencia;
#   - la funcion rastro-cotejo, con el mismo codigo que corre en local;
#   - la interfaz HTTP rastro-cotejo-api, que la expone.
#
# Escribe config/.cotejo.env con la direccion, que 60-sitios.sh pone en la
# configuracion de la interfaz de Cotejo.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.api.env"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.identidad.env"

if [[ "${RASTRO_PUBLICAR_COTEJO:-no}" != "si" ]]; then
  paso "Cotejo en AWS"
  ok "no desplegado (exporte RASTRO_PUBLICAR_COTEJO=si para hacerlo)"
  exit 0
fi

NOMBRE_FUNCION="${PREFIJO}-cotejo"
NOMBRE_API_COTEJO="${PREFIJO}-cotejo-api"
BUCKET_PAPELES="${PREFIJO}-cotejo-papeles-${CUENTA}"

if [[ -z "${RASTRO_JWT_SECRETO:-}" && -f "${RAIZ_PROYECTO}/config/.jwt.env" ]]; then
  # shellcheck source=/dev/null
  source "${RAIZ_PROYECTO}/config/.jwt.env"
fi
SECRETO_COTEJO="${RASTRO_JWT_SECRETO:-}"
if [[ "${#SECRETO_COTEJO}" -lt 32 ]]; then
  aviso "Cotejo valida el token del auditor con el mismo secreto que Rastro: falta RASTRO_JWT_SECRETO."
  exit 1
fi

if ! PYTHON="$(elegir_python)"; then
  aviso "Se necesita Python para empaquetar la funcion."
  exit 1
fi

DIR_TRABAJO="$(mktemp -d)"
trap 'rm -rf "${DIR_TRABAJO}"' EXIT

# --------------------------------------------------------------------------- #

paso "Contenedor de papeles de trabajo"

if existe_bucket "${BUCKET_PAPELES}"; then
  ok "contenedor ya existente: ${BUCKET_PAPELES}"
else
  aws s3api create-bucket --bucket "${BUCKET_PAPELES}" --region "${REGION}" >/dev/null
  ok "contenedor creado: ${BUCKET_PAPELES}"
fi

# Los papeles concentran informacion sobre las debilidades del sistema
# auditado: nada de acceso publico.
aws s3api put-public-access-block --bucket "${BUCKET_PAPELES}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
# El almacen hace detectable la edicion de un papel por su huella; el
# versionado ademas permite recuperar el original.
aws s3api put-bucket-versioning --bucket "${BUCKET_PAPELES}" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "${BUCKET_PAPELES}" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
ok "privado, versionado y cifrado"

# --------------------------------------------------------------------------- #

paso "Empaquetado de la funcion"

python -m pip install --quiet --no-compile \
  --target "${DIR_TRABAJO}/paquete" \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --implementation cp --python-version 3.12 --only-binary=:all: --upgrade \
  fastapi pydantic mangum pyjwt cryptography httpx pyyaml >/dev/null
ok "dependencias instaladas para linux/x86_64 y python 3.12"

# La misma disposicion que en el repositorio: la capa comun de Rastro en la
# raiz y Cotejo en cotejo/, con su catalogo. Los papeles locales no viajan.
cp -r "${RAIZ_PROYECTO}/libs/rastro_core" "${DIR_TRABAJO}/paquete/"
mkdir -p "${DIR_TRABAJO}/paquete/cotejo"
cp -r "${RAIZ_PROYECTO}/cotejo/cotejo" "${RAIZ_PROYECTO}/cotejo/api" \
  "${RAIZ_PROYECTO}/cotejo/catalogo" "${DIR_TRABAJO}/paquete/cotejo/"
find "${DIR_TRABAJO}/paquete" -name "__pycache__" -type d -prune -exec rm -rf {} +

cat > "${DIR_TRABAJO}/paquete/manejador.py" <<'PY'
"""Punto de entrada de la funcion. La logica esta en cotejo/api/aws.py."""
import sys

sys.path.insert(0, "/var/task/cotejo/api")

from aws import manejador  # noqa: E402,F401
PY

ARCHIVO_ZIP="${DIR_TRABAJO}/cotejo.zip"
"${PYTHON}" - "${DIR_TRABAJO}/paquete" "${ARCHIVO_ZIP}" <<'PY'
import os, sys, zipfile
origen, destino = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as archivo:
    for raiz, _, nombres in os.walk(origen):
        for nombre in nombres:
            ruta = os.path.join(raiz, nombre)
            info = zipfile.ZipInfo(os.path.relpath(ruta, origen).replace(os.sep, "/"))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(ruta, "rb") as fuente:
                archivo.writestr(info, fuente.read())
PY
ok "paquete: $(du -h "${ARCHIVO_ZIP}" | cut -f1)"

# --------------------------------------------------------------------------- #

paso "Funcion ${NOMBRE_FUNCION}"

# Las claves de los usuarios de prueba: Cotejo las necesita para ejecutar las
# pruebas sustantivas como cada rol, y de la base de datos no pueden salir
# porque estan derivadas. Son las de desarrollo de la semilla, publicas en el
# repositorio; con datos reales llegarian por COTEJO_CLAVES desde fuera.
#
# Los valores pasan a Python por el entorno y no interpolados en su codigo: un
# caracter raro en una clave romperia el guion, o algo peor.
ARCHIVO_VARIABLES="${DIR_TRABAJO}/variables.json"
V_URL_API="${URL_API}" V_CUENTA="${CUENTA}" V_BUCKET="${BUCKET_EVIDENCIAS}" V_LLAVE="${ALIAS_LLAVE}" V_REGISTRO="${NOMBRE_RASTRO_CLOUDTRAIL}" V_BITACORA="${TABLA_BITACORA}" V_MAESTROS="${TABLA_MAESTROS}" V_EMISOR="${EMISOR}" V_AUDIENCIA="${AUDIENCIA}" V_PAPELES="${BUCKET_PAPELES}" V_SECRETO="${RASTRO_JWT_SECRETO}" V_SEMILLA="${RAIZ_PROYECTO}/seed/organizaciones.json" "${PYTHON}" - "${ARCHIVO_VARIABLES}" <<'PY'
import json, os, sys
e = os.environ
semilla = json.load(open(e["V_SEMILLA"], encoding="utf-8"))
claves = {u["correo"]: u["clave"] for o in semilla["organizaciones"] for u in o["usuarios"]}
variables = {
    "COTEJO_ENTORNO": "aws",
    "COTEJO_URL_API": e["V_URL_API"],
    "COTEJO_ACCOUNT_ID": e["V_CUENTA"],
    "COTEJO_BUCKET": e["V_BUCKET"],
    "COTEJO_ALIAS_LLAVE": e["V_LLAVE"],
    "COTEJO_REGISTRO": e["V_REGISTRO"],
    "COTEJO_TABLA_BITACORA": e["V_BITACORA"],
    "COTEJO_TABLA_MAESTROS": e["V_MAESTROS"],
    "COTEJO_JWT_EMISOR": e["V_EMISOR"],
    "COTEJO_JWT_AUDIENCIA": e["V_AUDIENCIA"],
    "COTEJO_DIR_PAPELES": "/tmp/papeles",
    "COTEJO_BUCKET_PAPELES": e["V_PAPELES"],
    "COTEJO_CLAVES": json.dumps(claves),
    "RASTRO_ENTORNO": "aws",
    "RASTRO_JWT_EMISOR": e["V_EMISOR"],
    "RASTRO_JWT_AUDIENCIA": e["V_AUDIENCIA"],
    "RASTRO_JWT_SECRETO": e["V_SECRETO"],
}
json.dump({"Variables": variables}, open(sys.argv[1], "w", encoding="utf-8"))
PY
VARIABLES="file://$(ruta_nativa "${ARCHIVO_VARIABLES}")"
ZIP="fileb://$(ruta_nativa "${ARCHIVO_ZIP}")"

# Cinco minutos y 1 GB: la ejecucion completa corre en la invocacion asincrona,
# sin el limite de 30 segundos de API Gateway, y entra varias veces a Rastro
# como distintos usuarios.
if existe_funcion "${NOMBRE_FUNCION}"; then
  aws lambda update-function-code --region "${REGION}" \
    --function-name "${NOMBRE_FUNCION}" --zip-file "${ZIP}" >/dev/null
  aws lambda wait function-updated --region "${REGION}" --function-name "${NOMBRE_FUNCION}"
  aws lambda update-function-configuration --region "${REGION}" \
    --function-name "${NOMBRE_FUNCION}" --environment "${VARIABLES}" \
    --timeout 300 --memory-size 1024 >/dev/null
  aws lambda wait function-updated --region "${REGION}" --function-name "${NOMBRE_FUNCION}"
  ok "funcion actualizada: ${NOMBRE_FUNCION}"
else
  aws lambda create-function --region "${REGION}" \
    --function-name "${NOMBRE_FUNCION}" \
    --runtime python3.12 \
    --role "${ROL_EJECUCION}" \
    --handler manejador.manejador \
    --timeout 300 \
    --memory-size 1024 \
    --zip-file "${ZIP}" \
    --environment "${VARIABLES}" \
    --tags proyecto="${PREFIJO}" >/dev/null
  aws lambda wait function-active --region "${REGION}" --function-name "${NOMBRE_FUNCION}"
  ok "funcion creada: ${NOMBRE_FUNCION}"
fi

# Sin reintentos de la invocacion asincrona: una revision repetida sin que
# nadie la pidiera produciria papeles que nadie encargo.
aws lambda put-function-event-invoke-config --region "${REGION}" \
  --function-name "${NOMBRE_FUNCION}" --maximum-retry-attempts 0 >/dev/null
ok "invocacion asincrona sin reintentos"

# --------------------------------------------------------------------------- #

paso "Interfaz ${NOMBRE_API_COTEJO}"

ID_COTEJO="$(primer_resultado apigatewayv2 get-apis --region "${REGION}" \
  --query "Items[?Name=='${NOMBRE_API_COTEJO}'].ApiId | [0]")"
if [[ "${ID_COTEJO}" == "None" || -z "${ID_COTEJO}" ]]; then
  ID_COTEJO="$(aws apigatewayv2 create-api --region "${REGION}" \
    --name "${NOMBRE_API_COTEJO}" --protocol-type HTTP \
    --description "API del programa de auditoria Cotejo" \
    --query ApiId --output text)"
  ok "interfaz creada: ${ID_COTEJO}"
else
  ok "interfaz ya existente: ${ID_COTEJO}"
fi

ARN_FUNCION="arn:aws:lambda:${REGION}:${CUENTA}:function:${NOMBRE_FUNCION}"
INTEGRACION="$(primer_resultado apigatewayv2 get-integrations --api-id "${ID_COTEJO}" --region "${REGION}" \
  --query "Items[?IntegrationUri=='${ARN_FUNCION}'].IntegrationId | [0]")"
if [[ "${INTEGRACION}" == "None" || -z "${INTEGRACION}" ]]; then
  INTEGRACION="$(aws apigatewayv2 create-integration --api-id "${ID_COTEJO}" --region "${REGION}" \
    --integration-type AWS_PROXY --integration-uri "${ARN_FUNCION}" \
    --payload-format-version 2.0 --query IntegrationId --output text)"
fi
aws lambda add-permission --region "${REGION}" \
  --function-name "${NOMBRE_FUNCION}" --statement-id "apigw-${NOMBRE_API_COTEJO}" \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:${CUENTA}:${ID_COTEJO}/*/*" >/dev/null 2>&1 || true

# Todo va a la funcion, tambien las comprobaciones previas de CORS: las
# responde la propia aplicacion, igual que en local. La autorizacion la decide
# la aplicacion (token del rol auditor), no la puerta.
for clave in "ANY /" "ANY /{proxy+}"; do
  existente="$(primer_resultado apigatewayv2 get-routes --api-id "${ID_COTEJO}" --region "${REGION}" \
    --query "Items[?RouteKey=='${clave}'].RouteId | [0]")"
  if [[ "${existente}" == "None" || -z "${existente}" ]]; then
    aws apigatewayv2 create-route --api-id "${ID_COTEJO}" --region "${REGION}" \
      --route-key "${clave}" --target "integrations/${INTEGRACION}" >/dev/null
    ok "ruta creada: ${clave}"
  else
    ok "ruta ya existente: ${clave}"
  fi
done

if ! aws apigatewayv2 get-stage --api-id "${ID_COTEJO}" --stage-name '$default' \
     --region "${REGION}" >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "${ID_COTEJO}" --region "${REGION}" \
    --stage-name '$default' --auto-deploy >/dev/null
  ok "etapa por omision creada"
fi

URL_COTEJO="https://${ID_COTEJO}.execute-api.${REGION}.amazonaws.com"
cat > "${RAIZ_PROYECTO}/config/.cotejo.env" <<ENV
ID_COTEJO=${ID_COTEJO}
COTEJO_URL_API=${URL_COTEJO}
BUCKET_PAPELES=${BUCKET_PAPELES}
ENV

paso "Comprobacion"
CODIGO="000"
for _ in 1 2 3 4 5 6; do
  CODIGO="$(curl -s -o /dev/null -w '%{http_code}' "${URL_COTEJO}/salud" || echo "000")"
  [[ "${CODIGO}" == "200" ]] && break
  sleep 5
done
if [[ "${CODIGO}" == "200" ]]; then
  ok "Cotejo responde en ${URL_COTEJO}/salud"
else
  aviso "Cotejo respondio ${CODIGO} en /salud"
fi

paso "Cotejo disponible en ${URL_COTEJO}"
