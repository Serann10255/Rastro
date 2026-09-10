#!/usr/bin/env bash
# Identidad: aprovisiona las organizaciones, sus usuarios y sus datos maestros.
#
# El sistema tiene su propio directorio de usuarios, con las contrasenas
# derivadas con PBKDF2 y almacenadas en la tabla de maestros. Esta etapa lo
# puebla ejecutando el mismo guion que prepara el entorno local, apuntado a la
# cuenta desplegada: no hay una segunda implementacion del aprovisionamiento
# que pudiera divergir.
#
# Sobre Amazon Cognito. La version anterior delegaba la identidad en un grupo de
# usuarios de Cognito. Se cambio porque el sistema necesita administrar cuentas
# desde la propia aplicacion -crear usuarios, cambiar roles, desactivar- y
# Cognito no lo permite sin permisos que el laboratorio no concede. El contrato
# del token es el mismo, de modo que delegar en Cognito sigue siendo posible sin
# tocar el resto del sistema: lo unico que los demas servicios conocen es la
# forma del token.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

paso "Aprovisionamiento de organizaciones y usuarios"

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  aviso "Se necesita Python para derivar las contrasenas y sembrar los maestros."
  exit 1
fi

PYTHON="$(command -v python3 || command -v python)"

# Las claves de la semilla son de desarrollo. Antes de un despliegue con datos
# reales deben sustituirse: se pasan por variable de entorno para no dejarlas
# escritas en el repositorio.
export RASTRO_ENTORNO=aws
export AWS_REGION="${REGION}"
export RASTRO_TABLA_ENVIOS="${TABLA_ENVIOS}"
export RASTRO_TABLA_BITACORA="${TABLA_BITACORA}"
export RASTRO_TABLA_MAESTROS="${TABLA_MAESTROS}"
export RASTRO_BUCKET_EVIDENCIAS="${BUCKET_EVIDENCIAS}"
export RASTRO_ACCOUNT_ID="${CUENTA}"

# Sin endpoint: en AWS se habla con el servicio real y no con el equivalente
# local. Las variables se limpian por si quedaron de una sesion de desarrollo.
unset RASTRO_ENDPOINT_DYNAMODB RASTRO_ENDPOINT_S3 RASTRO_ENDPOINT_S3_PUBLICO

if [[ -n "${RASTRO_SIN_DATOS_SINTETICOS:-}" ]]; then
  ok "siembra omitida por RASTRO_SIN_DATOS_SINTETICOS"
else
  echo "  Derivando contrasenas con PBKDF2. Tarda unos segundos por usuario: es"
  echo "  el proposito del algoritmo, no una lentitud del guion."
  registrar_evidencia "aprovisionamiento" \
    "${PYTHON}" "${RAIZ_PROYECTO}/deploy/local/preparar_entorno.py"
fi

paso "Comprobacion del directorio"

TOTAL_MAESTROS="$(aws dynamodb scan --table-name "${TABLA_MAESTROS}" --region "${REGION}" \
  --select COUNT --query Count --output text 2>/dev/null || echo 0)"
ok "registros en la tabla de maestros: ${TOTAL_MAESTROS}"

if [[ "${TOTAL_MAESTROS}" == "0" ]]; then
  aviso "El directorio esta vacio: nadie podra iniciar sesion."
  aviso "Ejecute la siembra o cree al menos una organizacion con un administrador."
fi

# El emisor y la audiencia del token los fija el propio sistema. Se escriben
# aqui para que la etapa de funciones los pase como variables de entorno, igual
# que antes hacia con los identificadores de Cognito.
mkdir -p "${RAIZ_PROYECTO}/config"
cat > "${RAIZ_PROYECTO}/config/.identidad.env" <<ENV
EMISOR=${RASTRO_JWT_EMISOR:-https://${NOMBRE_API}.${CUENTA}.rastro}
AUDIENCIA=${RASTRO_JWT_AUDIENCIA:-rastro-web}
PROVEEDOR=propio
ENV

paso "Identidad lista"
echo "  Proveedor: directorio propio en ${TABLA_MAESTROS}"
echo "  Las contrasenas se almacenan derivadas con PBKDF2-HMAC-SHA256."
echo
echo "  IMPORTANTE: el secreto de firma del token debe fijarse con"
echo "  RASTRO_JWT_SECRETO antes de desplegar las funciones. Sin el, se usa el"
echo "  valor de desarrollo, que esta en el repositorio y no protege nada."
