#!/usr/bin/env bash
# Secuencia completa de despliegue.
#
# Es idempotente: puede ejecutarse tantas veces como haga falta. Esa propiedad
# no es comodidad sino requisito, porque las credenciales del laboratorio
# caducan cada cuatro horas y un despliegue interrumpido debe poder reanudarse
# sin dejar recursos a medias ni duplicados.
#
#   ./deploy/aws/desplegar.sh
#
# Cada etapa deja su salida en evidencias-despliegue/ con su marca de tiempo,
# de modo que un tercero pueda repetir la verificacion.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INICIO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Despliegue de Rastro"
echo "Inicio: ${INICIO}"

for etapa in 10-datos 20-identidad 30-funciones 40-api 50-registro 60-sitios 90-configuracion; do
  echo
  echo "########################################"
  echo "# Etapa ${etapa}"
  echo "########################################"
  bash "${DIR}/${etapa}.sh"
done

echo
echo "########################################"
echo "# Verificacion posterior al despliegue"
echo "########################################"
bash "${DIR}/95-verificar.sh"

echo
echo "Despliegue completo. Inicio ${INICIO}, fin $(date -u +%Y-%m-%dT%H:%M:%SZ)."
