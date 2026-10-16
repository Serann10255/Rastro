# ADR-015 · Cotejo también se despliega en AWS, a pedido, y se declara lo que cuesta

Fecha: 2026-10-16 · Estado: aceptada · Afecta a `cotejo/api/` (`aws.py`, ejecución
diferida en `main.py`), `cotejo/Dockerfile.lambda`, `cotejo/web` (espera de la
ejecución) y a la secuencia de despliegue (`55-cotejo-api.sh`, `60-sitios.sh`,
`67-cotejo-sitio-https.sh`)

## Contexto

Hasta ahora Cotejo se ejecutaba **desde la máquina del auditor**, a propósito: un
programa de auditoría que corre dentro del sistema auditado, con sus mismas
credenciales, depende de lo que audita. La interfaz web de Cotejo no se publicaba
(`RASTRO_PUBLICAR_COTEJO=no`) y, si se publicaba, apuntaba a una API en
`localhost:8007` que solo existía en ese equipo.

Para la sustentación, las diapositivas muestran la interfaz de Cotejo, y el
equipo decidió (2026-10-16) que tiene que funcionar **desde cualquier equipo**,
no solo desde el portátil de quien presenta. Se consideraron dos caminos:

| Camino | Qué cuesta |
|---|---|
| Interfaz en AWS, API en el equipo del auditor | Conserva la independencia, pero desde otro equipo la interfaz carga y no ejecuta nada |
| **Interfaz y API en AWS** | Funciona desde cualquier equipo; Cotejo pasa a correr dentro de la cuenta auditada |

Se eligió el segundo.

## Decisión

Cotejo se despliega en AWS **solo cuando se pide** (`RASTRO_PUBLICAR_COTEJO=si`),
con tres piezas:

1. **La función `rastro-cotejo`**, con el mismo código que corre en local, como
   imagen de contenedor con git (ver más abajo). Su punto de entrada
   (`cotejo/api/aws.py`) resuelve lo único que Lambda cambia.
2. **El contenedor `rastro-cotejo-papeles-<cuenta>`**, privado, cifrado y con
   versionado. El disco de una función no dura ni se comparte entre
   contenedores: antes de cada petición se trae lo que falte y después se sube
   lo que la petición escribió. Los papeles viajan byte a byte, de modo que su
   huella SHA-256 se recalcula igual en la nube que en local; el versionado,
   además, permite recuperar un papel si alguien lo sobrescribe.
3. **Dos interfaces HTTP**: `rastro-cotejo-api` (la API) y `rastro-cotejo-sitio`
   (la interfaz por HTTPS, con el mismo arreglo que el ADR-012).

### La ejecución se encarga y se espera

API Gateway corta toda petición a los **30 segundos**, y una revisión completa
tardó 34 en local. En AWS, `POST /ejecuciones` **encarga** la revisión: anota su
estado «en curso», invoca la misma función de forma asíncrona y responde `202`.
La invocación asíncrona corre sin ese límite (hasta cinco minutos), escribe los
papeles y anota «lista» o «fallida» con su motivo. La interfaz pregunta
`GET /ejecuciones/{id}/estado` cada tres segundos.

- La invocación asíncrona se configura **sin reintentos**: una revisión repetida
  que nadie pidió produciría papeles que nadie encargó.
- En local nada cambia: sin lanzador, la petición ejecuta y responde `201` con el
  resultado, como antes. Es una sola implementación del recorrido.
- Medido el 2026-10-16: la revisión en AWS terminó en unos 15 segundos.

### Los controles de secretos revisan el repositorio publicado

Los tres controles de secretos (C-09a, C-09b, C-09c) revisan el repositorio con
git: el árbol de la rama, todo el historial y si lo hallado sigue abriendo el
sistema. La primera versión de la función era un paquete .zip, sin git ni
repositorio, y los tres quedaban **no ejecutados** (8 de 11 conformes). Se
corrigió el mismo día:

- **La función es una imagen de contenedor** (`cotejo/Dockerfile.lambda`, en el
  repositorio `rastro-cotejo` de ECR) que añade `git-core` a la imagen base de
  Lambda para Python 3.12. Así C-09 ejecuta exactamente los mismos comandos que
  en el equipo del auditor; se descartó reimplementarlos con una biblioteca de
  git en Python, que sería una segunda implementación de la prueba que podría
  dar otro resultado.
- **Antes de cada revisión se clona el repositorio publicado** (GitHub, el remoto
  `origin` de quien despliega, fijado en `COTEJO_REPOSITORIO_REMOTO`), desnudo y
  con todas sus ramas, de cero cada vez. Es justo lo que C-09 pregunta: qué
  puede descargar cualquiera hoy. Tarda unos 7 segundos.
- **El papel dice de dónde salió la copia**: C-09a y C-09b anotan el `remoto` y el
  commit revisado.
- Se descartó meter el repositorio en la imagen: revisaría la copia de quien
  despliega, con lo que tuviera sin publicar, y envejecería con la imagen.

Resultado en AWS el 2026-10-16: **11 de 11 ejecutados, 10 conformes y 1
desviado**. El desviado es C-09b y es el hallazgo conocido H-01: el secreto de
firma que se versionó por error en el commit `be75812` sigue en el historial
publicado. C-09c confirma que ya no abre el sistema (se rotó). Sacarlo del
historial exigiría reescribirlo y forzar la publicación, que es una decisión del
equipo, no del despliegue.

La diferencia que queda con la línea de comandos: en local, C-09 revisa la copia
local (con lo que aún no se haya publicado); en AWS, lo publicado.

## Lo que cuesta, declarado

- **Pérdida de independencia.** Cotejo corre en la cuenta auditada, con `LabRole`,
  el mismo rol que los servicios de Rastro. Quien administra la cuenta puede
  modificar la función de auditoría o su almacén de papeles. Agrava el hallazgo
  permanente **H-PERM-02** (el programa tiene permisos de escritura sobre lo que
  audita) y debe leerse junto a él. La huella de cada papel hace detectable una
  edición; no la impide.
- **Credenciales en la configuración de la función.** Para ejecutar las pruebas
  sustantivas como cada rol, la función recibe las claves de los usuarios de
  prueba (`COTEJO_CLAVES`) y el secreto de firma de los tokens. Son las claves de
  desarrollo de la semilla, ya públicas en el repositorio; con datos reales
  tendrían que llegar desde un almacén de secretos, que el laboratorio no
  ofrece a este rol.
- **La interfaz es pública; los papeles no.** Cualquiera puede abrir la página de
  entrada, pero todo lo demás exige el token del rol `auditor`, igual que en
  local.

## Consecuencias

- La sustentación puede mostrar Cotejo desde cualquier equipo.
- La línea de comandos desde la máquina del auditor **sigue siendo la referencia
  independiente**: es la que un evaluador externo debería usar. La función
  también ejecuta los once controles, pero desde dentro de la cuenta auditada.
- El despliegue de Cotejo necesita Docker para construir la imagen.
- Si el laboratorio se cierra, Cotejo cae con el resto (la SCP de RE-06 afecta a
  todas las funciones con `LabRole`).
