#!/usr/bin/env bash
# Entrada HTTPS al sitio de Rastro.
#
# El sitio estatico de S3 solo se sirve por HTTP, y el arreglo habitual,
# CloudFront delante del contenedor, no esta disponible: el laboratorio niega a
# la sesion incluso listar distribuciones (restriccion RE-05). Se usa entonces
# una segunda interfaz HTTP de API Gateway, el mismo servicio que ya publica la
# API, que termina TLS con el certificado que el proveedor emite para
# *.execute-api.<region>.amazonaws.com. Los archivos se leen del punto REST del
# contenedor, tambien por HTTPS, de modo que ningun tramo viaja en claro.
#
# Resuelve de paso la otra limitacion del sitio de S3: un enlace directo
# (/rastreo, /envios/<id>) responde 200 con el indice, no 404 con el indice.
#
# Es una interfaz aparte y no rutas en la de la API porque las rutas de la
# aplicacion y las de la API coinciden: /envios/<id> existe en las dos.
#
# No sustituye al sitio de S3, que sigue respondiendo por HTTP en su direccion.
# Ver ADR-012.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

DIST="${RAIZ_PROYECTO}/web/dist"

# Punto REST del contenedor y no el de sitio web, que solo habla HTTP. El
# nombre del contenedor no lleva puntos, de modo que lo cubre el certificado
# comodin de S3.
ORIGEN="https://${BUCKET_WEB}.s3.${REGION}.amazonaws.com"

if [[ ! -f "${DIST}/index.html" ]]; then
  aviso "falta ${DIST}/index.html; ejecute antes 60-sitios.sh"
  exit 1
fi

paso "Interfaz del sitio"

ID_SITIO="$(primer_resultado apigatewayv2 get-apis --region "${REGION}" \
  --query "Items[?Name=='${NOMBRE_API_SITIO}'].ApiId | [0]")"

if [[ "${ID_SITIO}" == "None" || -z "${ID_SITIO}" ]]; then
  ID_SITIO="$(aws apigatewayv2 create-api --region "${REGION}" \
    --name "${NOMBRE_API_SITIO}" --protocol-type HTTP \
    --description "Entrada HTTPS al sitio estatico de Rastro" \
    --query ApiId --output text)"
  ok "interfaz creada: ${ID_SITIO}"
else
  ok "interfaz ya existente: ${ID_SITIO}"
fi

# Integracion de paso hacia un objeto del contenedor. S3 responde 403 a un
# objeto que no existe, porque la politica concede leer y no listar; se traduce
# a 404 para que un recurso que falta se vea como lo que es.
integracion() {
  local uri="$1"
  local existente
  existente="$(primer_resultado apigatewayv2 get-integrations --api-id "${ID_SITIO}" --region "${REGION}" \
    --query "Items[?IntegrationUri=='${uri}'].IntegrationId | [0]")"

  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    echo "${existente}"
    return
  fi

  aws apigatewayv2 create-integration --api-id "${ID_SITIO}" --region "${REGION}" \
    --integration-type HTTP_PROXY --integration-method GET \
    --integration-uri "${uri}" \
    --payload-format-version 1.0 \
    --response-parameters '{"403":{"overwrite:statuscode":"404"}}' \
    --query IntegrationId --output text
}

# Crea la ruta o, si ya existe, la apunta a la integracion indicada: asi un
# cambio de destino llega tambien a una interfaz ya creada.
ruta() {
  local clave="$1" destino="$2"
  local existente
  existente="$(primer_resultado apigatewayv2 get-routes --api-id "${ID_SITIO}" --region "${REGION}" \
    --query "Items[?RouteKey=='${clave}'].RouteId | [0]")"

  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    aws apigatewayv2 update-route --api-id "${ID_SITIO}" --region "${REGION}" \
      --route-id "${existente}" --target "integrations/${destino}" >/dev/null
    ok "ruta ya existente: ${clave}"
  else
    aws apigatewayv2 create-route --api-id "${ID_SITIO}" --region "${REGION}" \
      --route-key "${clave}" --target "integrations/${destino}" >/dev/null
    ok "ruta creada: ${clave}"
  fi
}

paso "Rutas"

# Toda ruta que no sea un archivo es de la aplicacion y la resuelve el
# enrutador del navegador: recibe el indice, con estado 200.
INDICE="$(integracion "${ORIGEN}/index.html")"
ruta "GET /" "${INDICE}"
ruta "GET /{proxy+}" "${INDICE}"

ruta "GET /assets/{proxy+}" "$(integracion "${ORIGEN}/assets/{proxy}")"

# Los archivos sueltos de la raiz (configuracion.json, icono.svg) se leen del
# compilado y no se enumeran a mano: uno nuevo que faltara aqui recibiria el
# indice en su lugar, con estado 200, y el fallo pasaria desapercibido.
for archivo in "${DIST}"/*; do
  [[ -f "${archivo}" ]] || continue
  nombre="$(basename "${archivo}")"
  [[ "${nombre}" == "index.html" ]] && continue
  ruta "GET /${nombre}" "$(integracion "${ORIGEN}/${nombre}")"
done

paso "Etapa de despliegue"

if ! aws apigatewayv2 get-stage --api-id "${ID_SITIO}" --stage-name '$default' \
     --region "${REGION}" >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "${ID_SITIO}" --region "${REGION}" \
    --stage-name '$default' --auto-deploy >/dev/null
  ok "etapa por omision creada con despliegue automatico"
else
  ok "etapa por omision ya existente"
fi

URL_SITIO="https://${ID_SITIO}.execute-api.${REGION}.amazonaws.com"

cat > "${RAIZ_PROYECTO}/config/.sitio.env" <<ENV
ID_SITIO=${ID_SITIO}
URL_SITIO=${URL_SITIO}
ENV

paso "CORS de la carga de evidencias"

# El sitio por HTTPS es un origen nuevo: sin esto, la consulta funcionaria y la
# carga de evidencias fallaria en el navegador del mensajero.
aplicar_cors_evidencias

paso "Comprobacion"

# El despliegue automatico de la etapa tarda unos segundos en surtir efecto.
CODIGO="000"
for _ in 1 2 3 4 5 6; do
  CODIGO="$(curl -s -o /dev/null -w '%{http_code}' "${URL_SITIO}/rastreo" || echo "000")"
  [[ "${CODIGO}" == "200" ]] && break
  sleep 5
done

if [[ "${CODIGO}" == "200" ]]; then
  ok "un enlace directo responde 200 por HTTPS"
else
  aviso "el sitio por HTTPS respondio ${CODIGO}; ejecute 95-verificar.sh para el detalle"
fi

paso "Sitio disponible por HTTPS en ${URL_SITIO}"
