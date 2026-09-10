# ADR-004 · Rol de ejecución compartido: limitación conocida, no decisión de diseño

Fecha: 2026-09-10 · Estado: aceptada con reservas

## Contexto

El principio de mínimo privilegio, uno de los principios de diseño del pilar de
seguridad del marco de buenas prácticas del proveedor, exige que cada función
disponga de un rol restringido a lo que necesita.

El laboratorio **no permite crear roles de identidad y acceso** (restricción
RE-01). El único rol de ejecución disponible es LabRole, cuya política de
confianza admite Lambda, Cognito, DynamoDB, S3, KMS, CloudTrail y API Gateway, y
que tiene permisos amplios.

## Decisión

Las funciones comparten LabRole. La limitación **se declara** en la
documentación, en el código de despliegue y en todo informe de auditoría, en
lugar de omitirse.

Se registra como hallazgo permanente H-PERM-01 en el catálogo de Cotejo, con su
condición, criterio, causa, efecto y recomendación.

## Por qué no se automatiza como prueba

Una prueba que siempre da el mismo resultado no aporta información. El entorno
impide corregir la desviación, de modo que evaluarla en cada ejecución solo
añadiría ruido. Omitir el hallazgo, en cambio, transmitiría una cobertura mayor
que la real, que es el riesgo R-04 del programa de auditoría.

## Consecuencias

**Riesgo aceptado.** El compromiso de cualquier función otorgaría al atacante
permisos muy superiores a los que esa función requiere.

**Riesgo derivado.** El propio programa de auditoría se ejecuta con ese rol y
dispone de permisos de escritura sobre lo que audita, lo que debilita el valor
probatorio de sus papeles de trabajo. Se registra como H-PERM-02.

**Recomendación para un despliegue productivo.** Un rol por función con
políticas acotadas a la tabla, el prefijo del contenedor y la llave que cada una
utiliza. Para el programa de auditoría, credenciales de solo lectura y un
almacén de papeles de trabajo en una cuenta distinta de la auditada.

**Origen.** La limitación proviene del entorno educativo y no del diseño.
