# ADR-001 · Arquitectura sin servidor sobre servicios gestionados

Fecha: 2026-09-10 · Estado: aceptada

## Contexto

El proyecto se desarrolla en AWS Academy Learner Lab, con un presupuesto de 50
dólares, sesiones de cuatro horas y una única región habilitada. El laboratorio
distingue dos comportamientos al cerrar la sesión:

- Las instancias de cómputo **se detienen**: no facturan, pero tampoco prestan
  servicio entre jornadas.
- Los motores de base de datos administrados, los balanceadores y las pasarelas
  de traducción de direcciones **siguen facturando** de forma continua.

## Alternativas consideradas

| Criterio (peso) | A. Sin servidor | B. Monolito en instancia | C. Plataforma comercial |
|---|---|---|---|
| Disponibilidad continua (0,25) | 5 | 1 | 5 |
| Portabilidad a otra cuenta (0,20) | 5 | 2 | 3 |
| Trazabilidad nativa (0,15) | 5 | 3 | 2 |
| Control del riesgo presupuestal (0,15) | 5 | 3 | 1 |
| Tiempo de implementación (0,15) | 4 | 2 | 5 |
| Aporte al aprendizaje (0,10) | 5 | 4 | 1 |
| **Total ponderado** | **4,85** | 2,25 | 3,15 |

La alternativa B **es técnicamente ejecutable**: el equipo verificó que dispone
de permisos sobre instancias de cómputo. No se descartó por falta de acceso,
sino por su comportamiento frente a los dos criterios de mayor peso.

## Decisión

Alternativa A: microservicios sobre cómputo bajo demanda, almacenamiento no
relacional y almacenamiento de objetos, todos gestionados.

## Consecuencias

**A favor.** El punto de consulta público responde entre sesiones. El despliegue
se recrea ejecutando una secuencia de comandos. El registro de actividad se
obtiene sin desarrollo adicional. Ningún recurso factura de forma continua salvo
la llave de cifrado.

**En contra.** Dependencia de un proveedor único, aceptada por tratarse de un
proyecto académico con entorno predefinido. Depurar una aplicación distribuida
en varias funciones es más difícil que depurar un proceso; se mitiga
concentrando la lógica común en una capa compartida.

**Verificable.** El cumplimiento se comprueba con `deploy/aws/95-verificar.sh`,
que confirma que cada componente del diagrama existe y responde.
