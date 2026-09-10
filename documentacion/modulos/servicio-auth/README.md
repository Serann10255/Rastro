# Servicio `auth` — emisor de tokens

Ubicación: `services/auth/` · Puerto local: 8001

## Qué hace

Emite tokens de sesión con el sujeto, el correo, los grupos y el identificador
de organización. **En AWS este servicio no se despliega**: lo sustituye Amazon
Cognito.

| Operación | Para qué |
|---|---|
| `POST /auth/token` | Autentica contra el directorio sintético y emite el token |
| `GET /auth/yo` | Devuelve la identidad que transporta el token en uso |
| `GET /auth/organizaciones` | Organizaciones aprovisionadas |

## Por qué existe

El laboratorio da sesiones de cuatro horas y 50 dólares. Depender de Cognito para
desarrollar y probar significaría no poder trabajar sin sesión abierta y gastar
presupuesto en cada iteración.

El contrato que ambos emisores respetan es idéntico —token firmado con `sub`,
`email`, `cognito:groups` y `custom:org_id`, validado por la misma función— y esa
es la razón de que sea sustituible sin tocar el resto del sistema.

## Dependencias y relaciones

- **Depende de**: `rastro_core.security` (emisión y validación) y de
  `seed/usuarios.json`.
- **Depende de él**: la interfaz web y las pruebas sustantivas de Cotejo, que
  necesitan autenticarse como distintos roles y organizaciones.
- **No** accede a las tablas ni al almacenamiento.

## Decisiones

**Credenciales inválidas responden lo mismo tanto si el usuario no existe como
si la clave es incorrecta.** Distinguirlas permitiría enumerar las cuentas.
Cubierto por `test_las_credenciales_invalidas_no_distinguen_usuario_de_clave`.

**Comparación en tiempo constante** de la clave, para no filtrarla por
temporización.

**Descartado: registro autónomo de organizaciones.** Está excluido del alcance
del proyecto: las organizaciones se aprovisionan con el despliegue. La
autogestión pertenece a un modelo comercial que no forma parte del problema.

**Riesgo asumido.** El directorio guarda las claves en texto plano en un archivo
de datos sintéticos. Es aceptable porque solo existe en el entorno local y nunca
se despliega; en AWS las gestiona Cognito.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
