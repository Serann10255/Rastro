#!/usr/bin/env bash
# Comprobacion de que cada componente del diagrama existe y responde.
#
# No sustituye al programa de auditoria: aqui se comprueba que el despliegue
# quedo completo, mientras que Cotejo evalua si los controles funcionan segun un
# criterio trazado a un marco de referencia. La diferencia es deliberada: quien
# despliega no deberia ser quien concluye que el control esta bien.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

FALLOS=0
comprobar() {
  local descripcion="$1"; shift
  if "$@" >/dev/null 2>&1; then
    ok "${descripcion}"
  else
    aviso "FALTA: ${descripcion}"
    FALLOS=$((FALLOS + 1))
  fi
}

paso "Componentes de datos"
comprobar "tabla de envios ${TABLA_ENVIOS}" aws dynamodb describe-table --table-name "${TABLA_ENVIOS}" --region "${REGION}"
comprobar "tabla de bitacora ${TABLA_BITACORA}" aws dynamodb describe-table --table-name "${TABLA_BITACORA}" --region "${REGION}"
comprobar "llave de cifrado ${ALIAS_LLAVE}" aws kms describe-key --key-id "${ALIAS_LLAVE}" --region "${REGION}"
comprobar "contenedor de evidencias" aws s3api head-bucket --bucket "${BUCKET_EVIDENCIAS}"
comprobar "contenedor de registro" aws s3api head-bucket --bucket "${BUCKET_REGISTRO}"

paso "Funciones"
for servicio in shipments tracking evidence public audit; do
  comprobar "funcion ${PREFIJO}-${servicio}" aws lambda get-function --function-name "${PREFIJO}-${servicio}" --region "${REGION}"
done

paso "Interfaz y registro"
if [[ -f "${RAIZ_PROYECTO}/config/.api.env" ]]; then
  # shellcheck source=/dev/null
  source "${RAIZ_PROYECTO}/config/.api.env"
  comprobar "interfaz HTTP ${ID_API}" aws apigatewayv2 get-api --api-id "${ID_API}" --region "${REGION}"

  paso "Prueba de extremo a extremo del punto publico"
  # Un identificador inexistente debe responder 404 y no 403 ni 500: comprueba
  # que la ruta llega a la funcion y que la funcion ejecuta su logica.
  CODIGO="$(curl -s -o /dev/null -w '%{http_code}' \
    "${URL_API}/publico/envios/00000000-0000-4000-8000-000000000000" || echo "000")"
  case "${CODIGO}" in
    404) ok "el punto publico responde a traves de la interfaz (404 esperado)" ;;
    403) aviso "403: la ruta existe pero la invocacion esta impedida; revise el permiso de Lambda" ; FALLOS=$((FALLOS + 1)) ;;
    000) aviso "sin respuesta de la interfaz" ; FALLOS=$((FALLOS + 1)) ;;
    *)   aviso "respuesta inesperada del punto publico: ${CODIGO}" ; FALLOS=$((FALLOS + 1)) ;;
  esac

  paso "Estado del supuesto SU-01"
  echo "  SU-01 (validador de tokens en API Gateway): ${SU01:-desconocido}"
else
  aviso "no hay datos de la interfaz; ejecute 40-api.sh"
  FALLOS=$((FALLOS + 1))
fi

comprobar "registro de actividad ${NOMBRE_RASTRO_CLOUDTRAIL}" \
  aws cloudtrail get-trail-status --name "${NOMBRE_RASTRO_CLOUDTRAIL}" --region "${REGION}"

paso "Resultado"
if [[ "${FALLOS}" -eq 0 ]]; then
  echo "  Todos los componentes verificados."
else
  echo "  ${FALLOS} componente(s) con problemas. Revise la salida anterior."
  exit 1
fi
