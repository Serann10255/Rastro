#!/usr/bin/env bash
# Capa de datos: tablas, llave de cifrado y contenedores.
#
# El unico componente con cargo fijo mensual del proyecto es la llave
# administrada por el cliente. No se crean motores de base de datos
# administrados, balanceadores ni pasarelas de traduccion de direcciones:
# son los tres recursos que siguen facturando entre sesiones y su exclusion es
# la principal medida de control del gasto (apartado 12.3 del documento).

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

paso "Tablas de DynamoDB"

crear_tabla_envios() {
  aws dynamodb create-table \
    --region "${REGION}" \
    --table-name "${TABLA_ENVIOS}" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions \
      AttributeName=pk,AttributeType=S \
      AttributeName=sk,AttributeType=S \
      AttributeName=gsi_org_pk,AttributeType=S \
      AttributeName=gsi_org_sk,AttributeType=S \
      AttributeName=gsi_pub_pk,AttributeType=S \
      AttributeName=gsi_pub_sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --global-secondary-indexes \
      '[{"IndexName":"gsi_org","KeySchema":[{"AttributeName":"gsi_org_pk","KeyType":"HASH"},{"AttributeName":"gsi_org_sk","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}},
        {"IndexName":"gsi_publico","KeySchema":[{"AttributeName":"gsi_pub_pk","KeyType":"HASH"},{"AttributeName":"gsi_pub_sk","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
    --tags Key=proyecto,Value="${PREFIJO}" \
    >/dev/null
  aws dynamodb wait table-exists --table-name "${TABLA_ENVIOS}" --region "${REGION}"
}

if existe_tabla "${TABLA_ENVIOS}"; then
  ok "tabla ya existente: ${TABLA_ENVIOS}"
else
  crear_tabla_envios
  ok "tabla creada: ${TABLA_ENVIOS} (indices gsi_org y gsi_publico)"
fi

if existe_tabla "${TABLA_BITACORA}"; then
  ok "tabla ya existente: ${TABLA_BITACORA}"
else
  aws dynamodb create-table \
    --region "${REGION}" \
    --table-name "${TABLA_BITACORA}" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --tags Key=proyecto,Value="${PREFIJO}" \
    >/dev/null
  aws dynamodb wait table-exists --table-name "${TABLA_BITACORA}" --region "${REGION}"
  ok "tabla creada: ${TABLA_BITACORA}"
fi

if existe_tabla "${TABLA_MAESTROS}"; then
  ok "tabla ya existente: ${TABLA_MAESTROS}"
else
  # Empresas, usuarios, tiendas, clientes y transportistas. Tabla aparte de la
  # de envios porque no crece con el volumen de operacion: mezclarlas haria que
  # un listado de tiendas compitiera por capacidad con el trafico de eventos.
  #
  # El indice gsi_email resuelve el inicio de sesion: el usuario escribe su
  # correo y no su organizacion, de modo que hay que encontrarlo sin saber en
  # que particion esta. Es la unica consulta que no filtra por organizacion, y
  # esta acotada a ese uso.
  aws dynamodb create-table \
    --region "${REGION}" \
    --table-name "${TABLA_MAESTROS}" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions \
      AttributeName=pk,AttributeType=S \
      AttributeName=sk,AttributeType=S \
      AttributeName=gsi_email_pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --global-secondary-indexes \
      '[{"IndexName":"gsi_email","KeySchema":[{"AttributeName":"gsi_email_pk","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
    --tags Key=proyecto,Value="${PREFIJO}" \
    >/dev/null
  aws dynamodb wait table-exists --table-name "${TABLA_MAESTROS}" --region "${REGION}"
  ok "tabla creada: ${TABLA_MAESTROS} (indice gsi_email)"
fi

paso "Llave de cifrado administrada por el cliente"

# La llave se invoca por alias en todo el codigo. Su identificador cambia entre
# cuentas; el alias, no.
if aws kms describe-key --key-id "${ALIAS_LLAVE}" --region "${REGION}" >/dev/null 2>&1; then
  ok "llave ya existente: ${ALIAS_LLAVE}"
else
  ID_LLAVE="$(aws kms create-key \
    --region "${REGION}" \
    --description "Cifrado de evidencias de entrega de ${PREFIJO}" \
    --tags TagKey=proyecto,TagValue="${PREFIJO}" \
    --query KeyMetadata.KeyId --output text)"
  aws kms create-alias --region "${REGION}" --alias-name "${ALIAS_LLAVE}" --target-key-id "${ID_LLAVE}"
  # Rotacion anual: es el criterio del control C-02 del programa de auditoria.
  aws kms enable-key-rotation --region "${REGION}" --key-id "${ID_LLAVE}"
  ok "llave creada con rotacion habilitada: ${ALIAS_LLAVE}"
fi

paso "Contenedores de objetos"

crear_bucket() {
  local nombre="$1"
  if existe_bucket "${nombre}"; then
    ok "contenedor ya existente: ${nombre}"
    return
  fi
  # us-east-1 no admite LocationConstraint; el laboratorio solo habilita esa region.
  aws s3api create-bucket --bucket "${nombre}" --region "${REGION}" >/dev/null
  ok "contenedor creado: ${nombre}"
}

crear_bucket "${BUCKET_EVIDENCIAS}"
crear_bucket "${BUCKET_REGISTRO}"

# Controles sobre el contenedor de evidencias. Son exactamente los que verifica
# Cotejo en los controles C-02, C-03 y C-04, y por eso se aplican aqui de forma
# explicita y versionada, no por consola.
aws s3api put-public-access-block --bucket "${BUCKET_EVIDENCIAS}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
ok "bloqueo de acceso publico activo en ${BUCKET_EVIDENCIAS}"

aws s3api put-bucket-versioning --bucket "${BUCKET_EVIDENCIAS}" \
  --versioning-configuration Status=Enabled
ok "versionado activo en ${BUCKET_EVIDENCIAS}"

aws s3api put-bucket-encryption --bucket "${BUCKET_EVIDENCIAS}" \
  --server-side-encryption-configuration "{
    \"Rules\": [{
      \"ApplyServerSideEncryptionByDefault\": {
        \"SSEAlgorithm\": \"aws:kms\",
        \"KMSMasterKeyID\": \"${ALIAS_LLAVE}\"
      },
      \"BucketKeyEnabled\": true
    }]
  }"
ok "cifrado por omision con ${ALIAS_LLAVE} en ${BUCKET_EVIDENCIAS}"

# Una peticion sin cifrado no debe poder escribir: el cifrado por omision cubre
# al cliente distraido, esta politica cubre al cliente deliberado.
aws s3api put-bucket-policy --bucket "${BUCKET_EVIDENCIAS}" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"RechazarCargaSinCifrado\",
    \"Effect\": \"Deny\",
    \"Principal\": \"*\",
    \"Action\": \"s3:PutObject\",
    \"Resource\": \"arn:aws:s3:::${BUCKET_EVIDENCIAS}/*\",
    \"Condition\": {\"StringNotEquals\": {\"s3:x-amz-server-side-encryption\": \"aws:kms\"}}
  }]
}"
ok "politica que rechaza cargas sin cifrado en ${BUCKET_EVIDENCIAS}"

aws s3api put-public-access-block --bucket "${BUCKET_REGISTRO}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
ok "bloqueo de acceso publico activo en ${BUCKET_REGISTRO}"

paso "Capa de datos lista"
