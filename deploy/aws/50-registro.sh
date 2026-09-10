#!/usr/bin/env bash
# Registro de actividad sobre la infraestructura (CloudTrail).
#
# Es la segunda capa del esquema de trazabilidad. Su valor esta en que es
# independiente de la aplicacion: una modificacion hecha directamente sobre la
# tabla, sin pasar por los microservicios, quedaria registrada aqui aunque el
# atacante recalculara la cadena de la bitacora. La independencia entre ambas
# capas es lo que sostiene el esquema.
#
# No se envia a CloudWatch Logs porque esa integracion exige un rol nuevo y el
# laboratorio no permite crearlos (restriccion RE-01).

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

paso "Politica del contenedor de registro"

# CloudTrail necesita permiso explicito para escribir en el contenedor.
aws s3api put-bucket-policy --bucket "${BUCKET_REGISTRO}" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Sid\": \"PermitirComprobacionDeAcl\",
      \"Effect\": \"Allow\",
      \"Principal\": {\"Service\": \"cloudtrail.amazonaws.com\"},
      \"Action\": \"s3:GetBucketAcl\",
      \"Resource\": \"arn:aws:s3:::${BUCKET_REGISTRO}\"
    },
    {
      \"Sid\": \"PermitirEscrituraDeRegistros\",
      \"Effect\": \"Allow\",
      \"Principal\": {\"Service\": \"cloudtrail.amazonaws.com\"},
      \"Action\": \"s3:PutObject\",
      \"Resource\": \"arn:aws:s3:::${BUCKET_REGISTRO}/AWSLogs/${CUENTA}/*\",
      \"Condition\": {\"StringEquals\": {\"s3:x-amz-acl\": \"bucket-owner-full-control\"}}
    }
  ]
}"
ok "politica aplicada a ${BUCKET_REGISTRO}"

paso "Registro de actividad"

if aws cloudtrail describe-trails --region "${REGION}" \
    --trail-name-list "${NOMBRE_RASTRO_CLOUDTRAIL}" \
    --query 'trailList[0].Name' --output text 2>/dev/null | grep -q "${NOMBRE_RASTRO_CLOUDTRAIL}"; then
  ok "registro ya existente: ${NOMBRE_RASTRO_CLOUDTRAIL}"
else
  # La validacion de integridad de los archivos de registro es el criterio del
  # control C-01 del programa de auditoria: sin ella, el propio registro seria
  # alterable sin dejar rastro.
  aws cloudtrail create-trail --region "${REGION}" \
    --name "${NOMBRE_RASTRO_CLOUDTRAIL}" \
    --s3-bucket-name "${BUCKET_REGISTRO}" \
    --enable-log-file-validation \
    --is-multi-region-trail >/dev/null
  ok "registro creado con validacion de integridad habilitada"
fi

aws cloudtrail start-logging --region "${REGION}" --name "${NOMBRE_RASTRO_CLOUDTRAIL}"
ok "registro activo"

paso "Eventos de datos (componente condicionado)"

# El apartado 8 del documento clasifica el registro de eventos de datos como
# condicionado: es el componente de costo variable de mayor incertidumbre y solo
# se habilita despues de cuantificarlo. El registro de eventos de gestion se
# mantiene en todos los casos.
if [[ "${RASTRO_EVENTOS_DE_DATOS:-no}" == "si" ]]; then
  aws cloudtrail put-event-selectors --region "${REGION}" \
    --trail-name "${NOMBRE_RASTRO_CLOUDTRAIL}" \
    --advanced-event-selectors "[
      {\"Name\":\"Eventos de datos sobre evidencias y bitacora\",
       \"FieldSelectors\":[
         {\"Field\":\"eventCategory\",\"Equals\":[\"Data\"]},
         {\"Field\":\"resources.type\",\"Equals\":[\"AWS::S3::Object\",\"AWS::DynamoDB::Table\"]}
       ]}
    ]" >/dev/null
  ok "eventos de datos habilitados (verifique el consumo del presupuesto)"
else
  ok "eventos de datos NO habilitados; exporte RASTRO_EVENTOS_DE_DATOS=si para activarlos"
fi

paso "Registro de actividad listo"
