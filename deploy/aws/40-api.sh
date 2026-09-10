#!/usr/bin/env bash
# Interfaz HTTP con validador de tokens de Cognito.
#
# Esta etapa es la que confirma o descarta el supuesto SU-01 del documento: que
# el laboratorio permite crear una interfaz HTTP con validador de tokens. Si el
# validador no puede crearse, el sistema sigue funcionando, porque cada servicio
# valida el token por su cuenta; lo que se pierde es la capa adicional. El guion
# lo detecta y lo informa en lugar de detenerse.
#
# Se usa API Gateway y no una URL de funcion porque la prueba preliminar de la
# Tabla 4 mostro que la invocacion anonima de URL de funcion esta impedida por
# un control ajeno a la configuracion del recurso (restriccion RE-02).

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.identidad.env"

paso "Interfaz HTTP"

ID_API="$(aws apigatewayv2 get-apis --region "${REGION}" \
  --query "Items[?Name=='${NOMBRE_API}'].ApiId | [0]" --output text)"

if [[ "${ID_API}" == "None" || -z "${ID_API}" ]]; then
  ID_API="$(aws apigatewayv2 create-api --region "${REGION}" \
    --name "${NOMBRE_API}" --protocol-type HTTP \
    --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=authorization,content-type' \
    --query ApiId --output text)"
  ok "interfaz creada: ${ID_API}"
else
  ok "interfaz ya existente: ${ID_API}"
fi

paso "Validador de tokens (supuesto SU-01)"

ID_AUTORIZADOR="$(aws apigatewayv2 get-authorizers --api-id "${ID_API}" --region "${REGION}" \
  --query "Items[?Name=='${PREFIJO}-cognito'].AuthorizerId | [0]" --output text)"

if [[ "${ID_AUTORIZADOR}" == "None" || -z "${ID_AUTORIZADOR}" ]]; then
  if ID_AUTORIZADOR="$(aws apigatewayv2 create-authorizer --api-id "${ID_API}" --region "${REGION}" \
      --name "${PREFIJO}-cognito" \
      --authorizer-type JWT \
      --identity-source '$request.header.Authorization' \
      --jwt-configuration "Audience=${ID_CLIENTE},Issuer=${EMISOR}" \
      --query AuthorizerId --output text 2>/dev/null)"; then
    ok "SU-01 CONFIRMADO: validador de tokens creado (${ID_AUTORIZADOR})"
    SU01="confirmado"
  else
    aviso "SU-01 NO CONFIRMADO: el laboratorio no permite crear el validador."
    aviso "El sistema sigue operando: cada servicio valida el token por su cuenta."
    ID_AUTORIZADOR=""
    SU01="descartado"
  fi
else
  ok "validador ya existente: ${ID_AUTORIZADOR}"
  SU01="confirmado"
fi

paso "Rutas"

# Ruta -> funcion. El reparto es el mismo que aplica nginx en el entorno local,
# de modo que la interfaz web funciona igual contra cualquiera de los dos.
declare -a RUTAS=(
  "POST /envios|shipments|auth"
  "GET /envios|shipments|auth"
  "GET /envios/{envio_id}|shipments|auth"
  "POST /envios/{envio_id}/asignacion|shipments|auth"
  "GET /envios/{envio_id}/transiciones|tracking|auth"
  "POST /envios/{envio_id}/eventos|tracking|auth"
  "POST /envios/{envio_id}/evidencias|evidence|auth"
  "GET /envios/{envio_id}/evidencias|evidence|auth"
  "POST /envios/{envio_id}/evidencias/{evidencia_id}/confirmacion|evidence|auth"
  "GET /bitacora|audit|auth"
  "GET /bitacora/verificacion|audit|auth"
  "GET /publico/envios/{envio_id}|public|abierta"
)

crear_integracion() {
  local servicio="$1"
  local arn="arn:aws:lambda:${REGION}:${CUENTA}:function:${PREFIJO}-${servicio}"

  local existente
  existente="$(aws apigatewayv2 get-integrations --api-id "${ID_API}" --region "${REGION}" \
    --query "Items[?IntegrationUri=='${arn}'].IntegrationId | [0]" --output text)"

  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    echo "${existente}"
    return
  fi

  aws apigatewayv2 create-integration --api-id "${ID_API}" --region "${REGION}" \
    --integration-type AWS_PROXY \
    --integration-uri "${arn}" \
    --payload-format-version 2.0 \
    --query IntegrationId --output text
}

declare -A INTEGRACIONES=()

for entrada in "${RUTAS[@]}"; do
  IFS='|' read -r clave servicio proteccion <<< "${entrada}"

  if [[ -z "${INTEGRACIONES[$servicio]:-}" ]]; then
    INTEGRACIONES[$servicio]="$(crear_integracion "${servicio}")"
    # Permite que la interfaz invoque la funcion. Sin este permiso, la ruta
    # responde 500 sin explicacion aparente.
    aws lambda add-permission --region "${REGION}" \
      --function-name "${PREFIJO}-${servicio}" \
      --statement-id "apigw-${PREFIJO}" \
      --action lambda:InvokeFunction \
      --principal apigateway.amazonaws.com \
      --source-arn "arn:aws:execute-api:${REGION}:${CUENTA}:${ID_API}/*/*" >/dev/null 2>&1 || true
  fi

  existente="$(aws apigatewayv2 get-routes --api-id "${ID_API}" --region "${REGION}" \
    --query "Items[?RouteKey=='${clave}'].RouteId | [0]" --output text)"
  if [[ "${existente}" != "None" && -n "${existente}" ]]; then
    ok "ruta ya existente: ${clave}"
    continue
  fi

  argumentos=(--api-id "${ID_API}" --region "${REGION}" --route-key "${clave}"
              --target "integrations/${INTEGRACIONES[$servicio]}")

  # La consulta publica no lleva validador: es el unico punto sin autenticacion
  # y su proteccion es el identificador aleatorio, no el token (REQ-04).
  if [[ "${proteccion}" == "auth" && -n "${ID_AUTORIZADOR}" ]]; then
    argumentos+=(--authorization-type JWT --authorizer-id "${ID_AUTORIZADOR}")
  fi

  aws apigatewayv2 create-route "${argumentos[@]}" >/dev/null
  ok "ruta creada: ${clave} -> ${PREFIJO}-${servicio} (${proteccion})"
done

paso "Etapa de despliegue"

if ! aws apigatewayv2 get-stage --api-id "${ID_API}" --stage-name '$default' \
     --region "${REGION}" >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "${ID_API}" --region "${REGION}" \
    --stage-name '$default' --auto-deploy >/dev/null
  ok "etapa por omision creada con despliegue automatico"
else
  ok "etapa por omision ya existente"
fi

URL_API="https://${ID_API}.execute-api.${REGION}.amazonaws.com"

cat > "${RAIZ_PROYECTO}/config/.api.env" <<ENV
ID_API=${ID_API}
URL_API=${URL_API}
SU01=${SU01}
ENV

paso "Interfaz disponible en ${URL_API}"
