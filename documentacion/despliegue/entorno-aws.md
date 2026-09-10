# Despliegue en AWS

Fecha: 2026-09-10 · Versión: 0.1

## Estado de verificación

> **La secuencia de despliegue está escrita y versionada, pero no se ha
> ejecutado contra la cuenta del laboratorio.** No hay credenciales de AWS en el
> entorno donde se construyó el repositorio, de modo que estos guiones no están
> verificados contra el servicio real. Lo que sí está verificado de extremo a
> extremo es la pila local equivalente.
>
> Esto es lo que queda por comprobar, y es también la primera actividad de la
> fase 1 del plan de trabajo:
>
> - **SU-01** — que el laboratorio permita crear una interfaz HTTP con validador
>   de tokens de Cognito. `40-api.sh` lo detecta y continúa si no se puede: cada
>   servicio valida el token por su cuenta, de modo que el sistema funciona igual
>   y solo se pierde una capa.
> - **REQ-09** — que el despliegue se reproduzca en una cuenta vacía sin editar
>   código.

---

## Ejecutar el despliegue

```bash
./deploy/aws/desplegar.sh
```

Es **idempotente**: puede ejecutarse tantas veces como haga falta. No es
comodidad sino requisito, porque las credenciales del laboratorio caducan cada
cuatro horas y un despliegue interrumpido debe poder reanudarse sin dejar
recursos a medias ni duplicados.

Cada etapa deja su salida en `evidencias-despliegue/` con marca de tiempo, de
modo que un tercero pueda repetir la verificación.

### Etapas

| Etapa | Qué crea |
|---|---|
| `10-datos.sh` | Tablas con sus índices, llave de cifrado con rotación, contenedores con cifrado, versionado, bloqueo público y política que rechaza cargas sin cifrar |
| `20-identidad.sh` | Grupo de usuarios de Cognito, los cuatro grupos de autorización, cliente de aplicación y usuarios sintéticos de dos organizaciones |
| `30-funciones.sh` | Empaqueta y despliega los cinco microservicios como funciones Lambda |
| `40-api.sh` | Interfaz HTTP, validador de tokens (SU-01), rutas e integraciones |
| `50-registro.sh` | CloudTrail con validación de integridad de sus archivos |
| `90-configuracion.sh` | Escribe `config/deployment.json` y comprueba que no queden identificadores literales |
| `95-verificar.sh` | Confirma que cada componente existe y que el punto público responde |

`auth` no se despliega en AWS: allí lo sustituye Amazon Cognito.

---

## Qué impone el entorno

| Restricción | Efecto en el despliegue |
|---|---|
| RE-01: no se pueden crear roles | Todas las funciones comparten `LabRole`. Se declara como hallazgo permanente ([ADR-004](../decisiones/adr-004-rol-compartido.md)) |
| RE-02: la invocación anónima de URL de función está impedida | Se usa API Gateway y no URL de función |
| RE-03: solo `us-east-1`, 50 dólares | Ningún diseño multirregión; se excluye todo recurso que facture entre sesiones |
| RE-04: el entorno se pierde al terminar el curso | Toda la configuración es reproducible por comandos versionados |

### Coste

El **único componente con cargo fijo mensual** es la llave de cifrado
administrada por el cliente. El resto opera bajo pago por uso y, con el volumen
de un entorno de pruebas, es marginal.

El riesgo presupuestal no viene del volumen de uso sino de dejar activo un
recurso que factura de forma continua. El proyecto **no emplea** motores de base
de datos administrados, balanceadores ni pasarelas de traducción de direcciones,
y esa exclusión es la principal medida de control del gasto.

Los eventos de datos de CloudTrail son el componente variable de mayor
incertidumbre y por eso están **desactivados por omisión**:

```bash
RASTRO_EVENTOS_DE_DATOS=si ./deploy/aws/50-registro.sh
```

Actívelos solo después de cuantificar su coste con la calculadora oficial.

---

## Portabilidad (REQ-09)

Si el presupuesto se agota, el docente habilita una cuenta nueva. La consecuencia
no es perder el proyecto sino el coste de reconstruirlo, y eso es lo que la
portabilidad reduce.

**Ningún identificador propio de la cuenta se escribe a mano:**

| Elemento | Cómo se referencia |
|---|---|
| Contenedor de objetos | Se deriva del número de cuenta, consultado a la propia sesión |
| Rol de ejecución | Por nombre (`LabRole`), no por ruta completa |
| Llave de cifrado | Por alias (`alias/rastro`) |
| Identificadores generados por el proveedor | En `config/deployment.json`, leído en ejecución |

`90-configuracion.sh` **busca el número de cuenta en el código y falla si lo
encuentra**. Es la mitigación del riesgo R-07, aplicada antes de necesitarla.

### Migrar a otra cuenta

```bash
./deploy/aws/migrar.sh exportar    # en la cuenta que se abandona
# cambiar de credenciales
./deploy/aws/desplegar.sh          # en la cuenta nueva
./deploy/aws/migrar.sh importar    # en la cuenta nueva
```

La bitácora se exporta tal cual, con sus hashes. **Si al importar la cadena no
verifica, la migración alteró los datos y hay que repetirla**: el propio control
de integridad sirve como control de la migración.

El simulacro completo está previsto en la fase 3 del plan, cuando todavía hay
margen para corregir, y no cuando ya sea necesario.

---

## Comprobar el despliegue

```bash
./deploy/aws/95-verificar.sh
```

Confirma tablas, llave, contenedores, funciones, interfaz y registro, y hace una
prueba de extremo a extremo del punto público: un identificador inexistente debe
responder **404**. Si responde 403, la ruta existe pero falta el permiso de
invocación de Lambda.

Esto comprueba que el despliegue quedó completo, **no** que los controles
funcionen. Eso lo evalúa Cotejo contra un criterio trazado a un marco de
referencia. La separación es deliberada: quien despliega no debería ser quien
concluye que el control está bien.

---

## Después de desplegar

1. Copiar `config/deployment.json` junto a la interfaz web (`90-configuracion.sh`
   ya lo hace).
2. Publicar el sitio estático en su contenedor.
3. Ejecutar el programa de auditoría:

```bash
cd cotejo && python -m cotejo ejecutar
```

Contra AWS, los ocho controles del catálogo son ejecutables. En local solo cinco
lo son, y los otros tres quedan como *no ejecutados*.
