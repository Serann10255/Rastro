#!/usr/bin/env bash
# Publica las dos interfaces como sitios estáticos.
#
# Las dos se compilan aquí y se copian al almacenamiento de objetos. No hay
# servidor de aplicaciones para el frontend en ninguna parte: es lo que las
# mantiene disponibles entre sesiones del laboratorio, cuando las instancias de
# cómputo están detenidas.
#
# La compilación NO hornea la dirección de la API. Cada sitio la lee de su
# configuracion.json en tiempo de ejecución, que esta etapa escribe con los
# identificadores del despliegue. Por eso un traslado a otra cuenta no obliga a
# recompilar: basta con volver a ejecutar la secuencia (REQ-09).

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
# shellcheck source=/dev/null
source "${RAIZ_PROYECTO}/config/.api.env"

BUCKET_COTEJO="${PREFIJO}-cotejo-${CUENTA}"

paso "Comprobación de herramientas"

if ! command -v npm >/dev/null 2>&1; then
  aviso "npm no está disponible; no se pueden compilar las interfaces."
  aviso "Instale Node 20 o superior, o compile en otra máquina y copie el directorio dist/."
  exit 1
fi
ok "npm $(npm --version)"

# --------------------------------------------------------------------------- #

publicar_sitio() {
  local nombre="$1" origen="$2" bucket="$3"

  paso "Sitio ${nombre}"

  crear_bucket_web "${bucket}"

  (cd "${origen}" && npm ci --no-audit --no-fund >/dev/null 2>&1 && npm run build >/dev/null)
  ok "compilado ${nombre}"

  # Los archivos con huella en el nombre no cambian nunca: se cachean un año.
  aws s3 sync "${origen}/dist/assets" "s3://${bucket}/assets" \
    --delete --cache-control "public, max-age=31536000, immutable" --only-show-errors
  ok "recursos publicados con caché larga"

  # El índice y la configuración cambian en cada despliegue: no se cachean.
  # Si se cachearan, un traslado a otra cuenta no surtiría efecto hasta que el
  # navegador venciera la caché, y el diagnóstico sería confuso.
  aws s3 sync "${origen}/dist" "s3://${bucket}" \
    --exclude "assets/*" --delete --cache-control "no-cache" --only-show-errors
  ok "índice y configuración publicados sin caché"

  echo "  URL: http://${bucket}.s3-website-${REGION}.amazonaws.com"
}

crear_bucket_web() {
  local bucket="$1"

  if ! existe_bucket "${bucket}"; then
    aws s3api create-bucket --bucket "${bucket}" --region "${REGION}" >/dev/null
    ok "contenedor creado: ${bucket}"
  else
    ok "contenedor ya existente: ${bucket}"
  fi

  # Un sitio estático necesita lectura pública, al contrario que el contenedor
  # de evidencias, que la tiene bloqueada. Son dos contenedores distintos
  # precisamente para que esa diferencia sea explícita y no un descuido.
  aws s3api put-public-access-block --bucket "${bucket}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false

  aws s3api put-bucket-policy --bucket "${bucket}" --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"LecturaPublicaDelSitio\",
      \"Effect\": \"Allow\",
      \"Principal\": \"*\",
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::${bucket}/*\"
    }]
  }"

  # Aplicación de una sola página: cualquier ruta desconocida devuelve el
  # índice. Sin esto, recargar en /envios/<id> o abrir un enlace compartido de
  # /rastreo daría un error del almacenamiento.
  aws s3 website "s3://${bucket}" --index-document index.html --error-document index.html
  ok "sitio estático habilitado con reescritura a index.html"
}

# --------------------------------------------------------------------------- #

paso "Configuración en tiempo de ejecución"

cat > "${RAIZ_PROYECTO}/web/public/configuracion.json" <<JSON
{
  "_nota": "Generado por deploy/aws/60-sitios.sh. No editar a mano.",
  "entorno": "aws",
  "region": "${REGION}",
  "account_id": "${CUENTA}",
  "url_publica_api": "${URL_API}",
  "supuesto_su01": "${SU01}",
  "generado_en": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
ok "configuración de Rastro escrita"

cat > "${RAIZ_PROYECTO}/cotejo/web/public/configuracion.json" <<JSON
{
  "_nota": "Generado por deploy/aws/60-sitios.sh. No editar a mano.",
  "entorno": "aws",
  "url_cotejo": "${COTEJO_URL_API:-}",
  "url_rastro": "${URL_API}",
  "generado_en": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
ok "configuración de Cotejo escrita"

if [[ -z "${COTEJO_URL_API:-}" ]]; then
  aviso "COTEJO_URL_API está vacía: la interfaz de auditoría no encontrará su programa."
  aviso "Cotejo no se despliega como función en AWS; se ejecuta desde la máquina del auditor."
  aviso "Exporte COTEJO_URL_API con la dirección donde lo publique, o use la línea de comandos."
fi

publicar_sitio "Rastro" "${RAIZ_PROYECTO}/web" "${BUCKET_WEB}"

if [[ "${RASTRO_PUBLICAR_COTEJO:-no}" == "si" ]]; then
  # El almacén de papeles de trabajo concentra información sobre las debilidades
  # del sistema auditado. Publicar su interfaz en un sitio de lectura pública
  # amplía la superficie sin necesidad: por omisión no se publica, y la interfaz
  # se sirve en la máquina del auditor.
  publicar_sitio "Cotejo" "${RAIZ_PROYECTO}/cotejo/web" "${BUCKET_COTEJO}"
else
  paso "Sitio Cotejo"
  ok "no publicado (exporte RASTRO_PUBLICAR_COTEJO=si para hacerlo)"
  echo "  La interfaz de auditoría se sirve en la máquina del auditor:"
  echo "    cd cotejo/web && npm run dev"
fi

paso "Sitios publicados"
echo "  Rastro: http://${BUCKET_WEB}.s3-website-${REGION}.amazonaws.com"
