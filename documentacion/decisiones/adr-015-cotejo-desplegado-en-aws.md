# ADR-015 · Cotejo también se despliega en AWS, a pedido, y se declara lo que cuesta

Fecha: 2026-10-16 · Estado: aceptada · Afecta a `cotejo/api/` (`aws.py`, ejecución
diferida en `main.py`), `cotejo/web` (espera de la ejecución) y a la secuencia de
despliegue (`55-cotejo-api.sh`, `60-sitios.sh`, `67-cotejo-sitio-https.sh`)

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

1. **La función `rastro-cotejo`**, con el mismo código que corre en local. Su
   punto de entrada (`cotejo/api/aws.py`) resuelve lo único que Lambda cambia.
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

### Qué no se puede ejecutar en la función

Los tres controles de secretos (C-09a, C-09b, C-09c) revisan el repositorio git y
su historial. En la función no hay repositorio, y quedan **no ejecutados con ese
motivo**, que es la conducta correcta: concluir sin mirar sería peor. Para
ejecutarlos, la línea de comandos desde una copia del repositorio sigue siendo el
camino (`cd cotejo && python -m cotejo ejecutar`). Resultado en AWS: **8 de 11
conformes, 3 no ejecutados**.

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
  independiente**: es la que ejecuta los once controles y la que un evaluador
  externo debería usar.
- Si el laboratorio se cierra, Cotejo cae con el resto (la SCP de RE-06 afecta a
  todas las funciones con `LabRole`).
