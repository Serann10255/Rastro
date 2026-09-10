#!/usr/bin/env bash
# Escribe config/deployment.json con los identificadores que genero el proveedor.
#
# Este archivo es la pieza que hace portable el sistema (REQ-09). Los servicios y
# la interfaz web lo leen en tiempo de ejecucion, de modo que ningun
# identificador de la cuenta queda escrito en el codigo. Al trasladar el sistema
# a otra cuenta, este archivo se regenera y nada mas cambia.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.identidad.env"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.api.env"

paso "Archivo de configuracion"

mkdir -p "${RAIZ_PROYECTO}/config"

cat > "${ARCHIVO_CONFIG}" <<JSON
{
  "_nota": "Generado por deploy/aws/90-configuracion.sh. No editar a mano: se regenera en cada despliegue.",
  "generado_en": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "entorno": "aws",
  "region": "${REGION}",
  "account_id": "${CUENTA}",
  "tabla_envios": "${TABLA_ENVIOS}",
  "tabla_bitacora": "${TABLA_BITACORA}",
  "bucket_evidencias": "${BUCKET_EVIDENCIAS}",
  "bucket_registro": "${BUCKET_REGISTRO}",
  "alias_llave": "${ALIAS_LLAVE}",
  "rol_ejecucion": "${NOMBRE_ROL}",
  "grupo_usuarios": "${ID_GRUPO}",
  "cliente_aplicacion": "${ID_CLIENTE}",
  "jwt_emisor": "${EMISOR}",
  "jwt_audiencia": "${ID_CLIENTE}",
  "jwt_jwks_url": "${JWKS}",
  "url_publica_api": "${URL_API}",
  "registro_actividad": "${NOMBRE_RASTRO_CLOUDTRAIL}",
  "supuesto_su01": "${SU01}",
  "vigencia_enlace_segundos": 300
}
JSON
ok "escrito ${ARCHIVO_CONFIG}"

# La interfaz web lee el mismo archivo, servido junto al sitio estatico.
cp "${ARCHIVO_CONFIG}" "${RAIZ_PROYECTO}/web/configuracion.json"
ok "copia disponible para la interfaz web"

paso "Verificacion de que no quedan identificadores escritos a mano"

# Comprobacion del riesgo R-07: si el numero de cuenta aparece literal en el
# codigo, la migracion a otra cuenta fallara. Se busca antes de necesitarlo.
if grep -rIn --exclude-dir=config --exclude-dir=.git --exclude-dir=evidencias-despliegue \
     --exclude="*.json" -e "${CUENTA}" "${RAIZ_PROYECTO}/libs" "${RAIZ_PROYECTO}/services" \
     "${RAIZ_PROYECTO}/web" 2>/dev/null; then
  aviso "el numero de cuenta aparece literal en el codigo: corrijalo antes de migrar (R-07)"
  exit 1
fi
ok "ningun identificador de cuenta escrito a mano en el codigo"

paso "Configuracion lista"
