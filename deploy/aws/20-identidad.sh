#!/usr/bin/env bash
# Identidad: grupo de usuarios de Cognito, grupos de autorizacion y usuarios.
#
# Se usa un grupo de usuarios y no un grupo de identidades: este ultimo exigiria
# crear roles nuevos, y el laboratorio no lo permite (restriccion RE-01).
#
# Los cuatro grupos de autorizacion son los del apartado 3.1 del documento. El
# identificador de organizacion viaja como atributo personalizado del token y es
# el filtro obligatorio de toda consulta (riesgo R-05).

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

paso "Grupo de usuarios de Cognito"

ID_GRUPO="$(aws cognito-idp list-user-pools --max-results 60 --region "${REGION}" \
  --query "UserPools[?Name=='${GRUPO_USUARIOS}'].Id | [0]" --output text)"

if [[ "${ID_GRUPO}" == "None" || -z "${ID_GRUPO}" ]]; then
  ID_GRUPO="$(aws cognito-idp create-user-pool \
    --region "${REGION}" \
    --pool-name "${GRUPO_USUARIOS}" \
    --schema '[{"Name":"org_id","AttributeDataType":"String","Mutable":false,"Required":false,"StringAttributeConstraints":{"MinLength":"2","MaxLength":"64"}}]' \
    --policies '{"PasswordPolicy":{"MinimumLength":12,"RequireUppercase":true,"RequireLowercase":true,"RequireNumbers":true,"RequireSymbols":false}}' \
    --auto-verified-attributes email \
    --username-attributes email \
    --query UserPool.Id --output text)"
  ok "grupo de usuarios creado: ${ID_GRUPO}"
else
  ok "grupo de usuarios ya existente: ${ID_GRUPO}"
fi

paso "Grupos de autorizacion"

for grupo in administrador despachador conductor auditor; do
  if aws cognito-idp get-group --user-pool-id "${ID_GRUPO}" --group-name "${grupo}" \
      --region "${REGION}" >/dev/null 2>&1; then
    ok "grupo ya existente: ${grupo}"
  else
    aws cognito-idp create-group --user-pool-id "${ID_GRUPO}" --group-name "${grupo}" \
      --region "${REGION}" --description "Grupo de autorizacion ${grupo} de ${PREFIJO}" >/dev/null
    ok "grupo creado: ${grupo}"
  fi
done

paso "Cliente de aplicacion"

ID_CLIENTE="$(aws cognito-idp list-user-pool-clients --user-pool-id "${ID_GRUPO}" \
  --max-results 60 --region "${REGION}" \
  --query "UserPoolClients[?ClientName=='${PREFIJO}-web'].ClientId | [0]" --output text)"

if [[ "${ID_CLIENTE}" == "None" || -z "${ID_CLIENTE}" ]]; then
  # Sin secreto de cliente: la interfaz es una aplicacion de pagina unica y no
  # puede guardar un secreto. El flujo es de autenticacion de usuario, no de
  # credenciales de cliente.
  ID_CLIENTE="$(aws cognito-idp create-user-pool-client \
    --user-pool-id "${ID_GRUPO}" \
    --client-name "${PREFIJO}-web" \
    --region "${REGION}" \
    --no-generate-secret \
    --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
    --access-token-validity 1 --id-token-validity 1 --token-validity-units '{"AccessToken":"hours","IdToken":"hours"}' \
    --query UserPoolClient.ClientId --output text)"
  ok "cliente creado: ${ID_CLIENTE}"
else
  ok "cliente ya existente: ${ID_CLIENTE}"
fi

paso "Usuarios sinteticos"

# El sistema se pobla unicamente con datos sinteticos (apartado 3.3). Estos
# usuarios existen para probar la matriz de autorizacion y el aislamiento entre
# organizaciones: dos empresas distintas sobre la misma infraestructura.
crear_usuario() {
  local correo="$1" org="$2" grupo="$3" clave="$4"

  if aws cognito-idp admin-get-user --user-pool-id "${ID_GRUPO}" --username "${correo}" \
      --region "${REGION}" >/dev/null 2>&1; then
    ok "usuario ya existente: ${correo}"
  else
    aws cognito-idp admin-create-user \
      --user-pool-id "${ID_GRUPO}" --username "${correo}" --region "${REGION}" \
      --user-attributes Name=email,Value="${correo}" Name=email_verified,Value=true \
                        Name=custom:org_id,Value="${org}" \
      --message-action SUPPRESS >/dev/null
    aws cognito-idp admin-set-user-password \
      --user-pool-id "${ID_GRUPO}" --username "${correo}" --region "${REGION}" \
      --password "${clave}" --permanent
    ok "usuario creado: ${correo} (${org})"
  fi

  aws cognito-idp admin-add-user-to-group \
    --user-pool-id "${ID_GRUPO}" --username "${correo}" --group-name "${grupo}" --region "${REGION}"
}

CLAVE_ANDES="${RASTRO_CLAVE_ANDES:-Andes.Rastro.2026}"
CLAVE_SABANA="${RASTRO_CLAVE_SABANA:-Sabana.Rastro.2026}"

crear_usuario "admin@andes.test"    org-andes  administrador "${CLAVE_ANDES}"
crear_usuario "despacho@andes.test" org-andes  despachador   "${CLAVE_ANDES}"
crear_usuario "carlos@andes.test"   org-andes  conductor     "${CLAVE_ANDES}"
crear_usuario "auditor@andes.test"  org-andes  auditor       "${CLAVE_ANDES}"
crear_usuario "despacho@sabana.test" org-sabana despachador  "${CLAVE_SABANA}"
crear_usuario "carlos@sabana.test"   org-sabana conductor    "${CLAVE_SABANA}"

EMISOR="https://cognito-idp.${REGION}.amazonaws.com/${ID_GRUPO}"
JWKS="${EMISOR}/.well-known/jwks.json"

# Los identificadores que genera el proveedor no se copian a mano a ningun sitio:
# se dejan aqui para que la etapa final los recoja en el archivo de configuracion.
mkdir -p "${RAIZ_PROYECTO}/config"
cat > "${RAIZ_PROYECTO}/config/.identidad.env" <<ENV
ID_GRUPO=${ID_GRUPO}
ID_CLIENTE=${ID_CLIENTE}
EMISOR=${EMISOR}
JWKS=${JWKS}
ENV

paso "Identidad lista (emisor: ${EMISOR})"
