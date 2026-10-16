#!/usr/bin/env bash
# Entrada HTTPS a la interfaz de Cotejo.
#
# Opcional, como el resto de Cotejo en AWS: solo con RASTRO_PUBLICAR_COTEJO=si.
# Es el mismo arreglo que 65-sitio-https.sh hace para Rastro (ADR-012): una
# interfaz HTTP de API Gateway que lee los archivos del punto REST del
# contenedor, porque el sitio estatico de S3 solo habla HTTP y CloudFront esta
# impedido en el laboratorio (RE-05). Sin HTTPS, el auditor entraria con su
# contrasena por un canal en claro.
#
# Va aparte de 65 para no tocar la entrada de Rastro, que ya esta verificada y
# que es la que usa la operacion.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

if [[ "${RASTRO_PUBLICAR_COTEJO:-no}" != "si" ]]; then
  paso "Interfaz de Cotejo por HTTPS"
  ok "no desplegada (exporte RASTRO_PUBLICAR_COTEJO=si para hacerlo)"
  exit 0
fi

BUCKET_COTEJO="${PREFIJO}-cotejo-${CUENTA}"
NOMBRE_SITIO_COTEJO="${PREFIJO}-cotejo-sitio"
DIST="${RAIZ_PROYECTO}/cotejo/web/dist"
ORIGEN="https://${BUCKET_COTEJO}.s3.${REGION}.amazonaws.com"

if [[ ! -f "${DIST}/index.html" ]]; then
  aviso "falta ${DIST}/index.html; ejecute antes 60-sitios.sh con RASTRO_PUBLICAR_COTEJO=si"
  exit 1
fi

paso "Interfaz del sitio de Cotejo"

ID="$(primer_resultado apigatewayv2 get-apis --region "${REGION}" \
  --query "Items[?Name=='${NOMBRE_SITIO_COTEJO}'].ApiId | [0]")"
if [[ "${ID}" == "None" || -z "${ID}" ]]; then
  ID="$(aws apigatewayv2 create-api --region "${REGION}" \
    --name "${NOMBRE_SITIO_COTEJO}" --protocol-type HTTP \
    --description "Entrada HTTPS a la interfaz de Cotejo" \
    --query ApiId --output text)"
  ok "interfaz creada: ${ID}"
else
  ok "interfaz ya existente: ${ID}"
fi

# S3 responde 403 a un objeto que no existe; se traduce a 404.
integracion() {
  local uri="$1" existente
  existente="$(primer_resultado apigatewayv2 get-integrations --api-id "${ID}" --region "${REGION}" \
    --query "Items[?IntegrationUri=='${uri}'].IntegrationId | [0]")"
  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    echo "${existente}"
    return
  fi
  aws apigatewayv2 create-integration --api-id "${ID}" --region "${REGION}" \
    --integration-type HTTP_PROXY --integration-method GET \
    --integration-uri "${uri}" \
    --payload-format-version 1.0 \
    --response-parameters '{"403":{"overwrite:statuscode":"404"}}' \
    --query IntegrationId --output text
}

ruta() {
  local clave="$1" destino="$2" existente
  existente="$(primer_resultado apigatewayv2 get-routes --api-id "${ID}" --region "${REGION}" \
    --query "Items[?RouteKey=='${clave}'].RouteId | [0]")"
  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    aws apigatewayv2 update-route --api-id "${ID}" --region "${REGION}" \
      --route-id "${existente}" --target "integrations/${destino}" >/dev/null
    ok "ruta ya existente: ${clave}"
  else
    aws apigatewayv2 create-route --api-id "${ID}" --region "${REGION}" \
      --route-key "${clave}" --target "integrations/${destino}" >/dev/null
    ok "ruta creada: ${clave}"
  fi
}

paso "Rutas"

INDICE="$(integracion "${ORIGEN}/index.html")"
ruta "GET /" "${INDICE}"
ruta "GET /{proxy+}" "${INDICE}"
ruta "GET /assets/{proxy+}" "$(integracion "${ORIGEN}/assets/{proxy}")"

for archivo in "${DIST}"/*; do
  [[ -f "${archivo}" ]] || continue
  nombre="$(basename "${archivo}")"
  [[ "${nombre}" == "index.html" ]] && continue
  ruta "GET /${nombre}" "$(integracion "${ORIGEN}/${nombre}")"
done

if ! aws apigatewayv2 get-stage --api-id "${ID}" --stage-name '$default' \
     --region "${REGION}" >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "${ID}" --region "${REGION}" \
    --stage-name '$default' --auto-deploy >/dev/null
  ok "etapa por omision creada"
fi

URL_SITIO_COTEJO="https://${ID}.execute-api.${REGION}.amazonaws.com"
sed -i "/^ID_SITIO_COTEJO=/d; /^URL_SITIO_COTEJO=/d" "${RAIZ_PROYECTO}/config/.cotejo.env" 2>/dev/null || true
cat >> "${RAIZ_PROYECTO}/config/.cotejo.env" <<ENV
ID_SITIO_COTEJO=${ID}
URL_SITIO_COTEJO=${URL_SITIO_COTEJO}
ENV

paso "Comprobacion"
CODIGO="000"
for _ in 1 2 3 4 5 6; do
  CODIGO="$(curl -s -o /dev/null -w '%{http_code}' "${URL_SITIO_COTEJO}/" || echo "000")"
  [[ "${CODIGO}" == "200" ]] && break
  sleep 5
done
if [[ "${CODIGO}" == "200" ]]; then
  ok "la interfaz de Cotejo responde 200 por HTTPS"
else
  aviso "la interfaz de Cotejo respondio ${CODIGO}"
fi

paso "Cotejo disponible por HTTPS en ${URL_SITIO_COTEJO}"
