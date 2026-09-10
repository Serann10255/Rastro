#!/usr/bin/env bash
# Migracion de datos a otra cuenta del laboratorio (REQ-09, riesgos R-01 y R-06).
#
# El presupuesto asignado puede agotarse, y en ese caso el docente habilita una
# cuenta nueva. La consecuencia no es perder el proyecto sino el costo de
# reconstruirlo, y este guion es lo que reduce ese costo: exportar en la cuenta
# vieja, ejecutar la secuencia de despliegue en la nueva e importar.
#
#   ./deploy/aws/migrar.sh exportar   # en la cuenta que se abandona
#   ./deploy/aws/desplegar.sh         # en la cuenta nueva
#   ./deploy/aws/migrar.sh importar   # en la cuenta nueva
#
# El simulacro completo esta previsto en la fase 3 del plan, cuando todavia hay
# margen para corregir, y no cuando ya sea necesario.

source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

DIR_MIGRACION="${RASTRO_DIR_MIGRACION:-${RAIZ_PROYECTO}/migracion}"
ACCION="${1:-}"

exportar() {
  mkdir -p "${DIR_MIGRACION}"
  paso "Exportacion desde la cuenta ${CUENTA}"

  for tabla in "${TABLA_ENVIOS}" "${TABLA_BITACORA}"; do
    local destino="${DIR_MIGRACION}/${tabla}.json"
    # La exploracion completa es aceptable por el volumen previsto; para un
    # volumen mayor corresponderia una exportacion al almacenamiento de objetos.
    aws dynamodb scan --table-name "${tabla}" --region "${REGION}" \
      --query 'Items' --output json > "${destino}"
    ok "$(python -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "${destino}") registros de ${tabla}"
  done

  aws s3 sync "s3://${BUCKET_EVIDENCIAS}" "${DIR_MIGRACION}/evidencias" --quiet
  ok "evidencias copiadas a ${DIR_MIGRACION}/evidencias"

  # La bitacora se exporta tal cual, con sus hashes. Si al importar la cadena no
  # verifica, la migracion altero los datos y hay que repetirla: la propia
  # verificacion sirve como control de la migracion.
  cat > "${DIR_MIGRACION}/manifiesto.json" <<JSON
{
  "cuenta_origen": "${CUENTA}",
  "region": "${REGION}",
  "exportado_en": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tablas": ["${TABLA_ENVIOS}", "${TABLA_BITACORA}"]
}
JSON
  ok "manifiesto escrito"

  paso "Exportacion completa en ${DIR_MIGRACION}"
  echo "  Siguiente paso: en la cuenta nueva, ./deploy/aws/desplegar.sh y luego ./deploy/aws/migrar.sh importar"
}

importar() {
  [[ -d "${DIR_MIGRACION}" ]] || { aviso "no hay datos exportados en ${DIR_MIGRACION}"; exit 1; }

  paso "Importacion hacia la cuenta ${CUENTA}"

  for tabla in "${TABLA_ENVIOS}" "${TABLA_BITACORA}"; do
    local origen="${DIR_MIGRACION}/${tabla}.json"
    [[ -f "${origen}" ]] || { aviso "falta ${origen}"; continue; }
    python "${RAIZ_PROYECTO}/deploy/aws/importar_tabla.py" "${tabla}" "${origen}" "${REGION}"
  done

  if [[ -d "${DIR_MIGRACION}/evidencias" ]]; then
    aws s3 sync "${DIR_MIGRACION}/evidencias" "s3://${BUCKET_EVIDENCIAS}" \
      --sse aws:kms --sse-kms-key-id "${ALIAS_LLAVE}" --quiet
    ok "evidencias restauradas con cifrado bajo ${ALIAS_LLAVE}"
  fi

  paso "Verificacion de la cadena tras la migracion"
  echo "  Ejecute el verificador de bitacora como auditor. Si la cadena no verifica,"
  echo "  la migracion altero los datos: el propio control detecta el problema."
}

case "${ACCION}" in
  exportar) exportar ;;
  importar) importar ;;
  *) echo "Uso: $0 {exportar|importar}" >&2; exit 1 ;;
esac
