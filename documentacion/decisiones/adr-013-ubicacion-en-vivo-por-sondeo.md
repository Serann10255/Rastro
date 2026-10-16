# ADR-013 · Rutas de entrega con ubicación en vivo por sondeo

Fecha: 2026-10-16 · Estado: aceptada · Afecta a `services/tracking`,
`services/public`, `libs/rastro_core/rutas.py`, al catálogo de operaciones
(`authz.py`) y a la interfaz (Entregas, Seguimiento, Rastreo)

## Contexto

Tras la Entrega 2, el profesor pidió una capacidad nueva: que el conductor elija
qué guías va a entregar, abra un «modo ruta» y que ese modo comparta su
ubicación en tiempo real con la empresa y con el cliente.

Es una ampliación de alcance y se registra como tal, con la misma disciplina que
el [ADR-006](adr-006-ampliacion-de-alcance-a-tms.md): qué entra, qué sigue fuera
y por qué. Los nueve requisitos REQ-01..09 no cambian; esto los rodea.

Cuatro condiciones pesan sobre el diseño:

1. **El entorno.** Funciones Lambda detrás de API Gateway, sesiones de cuatro
   horas y 50 USD de presupuesto. Nada que mantenga conexiones abiertas ni que
   facture entre sesiones.
2. **La máquina de estados** (REQ-03) es la que Cotejo verifica en C-07. Abrirle
   un atajo para «salir a ruta» sería cambiar el control auditado.
3. **La ubicación de un trabajador es un dato personal** (Ley 1581 de 2012).
   Compartirla exige finalidad, conocimiento de la persona y temporalidad.
4. **La bitácora encadenada** registra cada operación (REQ-07). Una posición cada
   pocos segundos la convertiría en un registro del pulso del teléfono.

## Decisión

### 1. La ubicación viaja por sondeo, no por una conexión persistente

El teléfono del conductor envía su posición cada **15 s** (antes si se movió más
de 100 m) con `POST /rutas/{id}/posiciones`. El mapa de la empresa pregunta cada
**10 s** y la consulta pública cada **20 s**. Es «casi en tiempo real»: el punto
en el mapa llega con un retraso de entre 10 y 25 segundos.

**Alternativas descartadas:**

| Alternativa | Por qué no |
|---|---|
| API Gateway WebSocket | Exige una tabla de conexiones, una función de difusión y gestionar desconexiones. Tres piezas nuevas para ganar quince segundos, y una más que verificar en un laboratorio que ya niega servicios sin aviso (RE-05, RE-06). |
| AWS IoT Core (MQTT) o AppSync | Mismo problema, con servicios cuyo permiso en el laboratorio no está comprobado. |
| Amazon Location Service (rastreadores) | Resolvería el almacenamiento de posiciones, pero añade un servicio con coste por posición y su disponibilidad en el laboratorio no está verificada. Y sigue haciendo falta el sondeo en el navegador. |

El coste es acotado: un conductor durante ocho horas son unas 1 900 peticiones;
una pantalla de seguimiento abierta el mismo tiempo, unas 2 900. Ambas quedan
lejos de cualquier umbral de cobro de Lambda o DynamoDB.

### 2. Salir a ruta recorre el flujo principal, sin atajos

Solo salen a ruta las guías **que el conductor ya tiene**: `RECOLECTADO`,
`EN_TRANSITO` o `EN_REPARTO`. Al iniciar, cada una avanza hasta `EN_REPARTO`
registrando **cada paso** como un evento propio, validado por la misma máquina de
estados: una recolectada genera `EN_TRANSITO` y `EN_REPARTO`. Salir a ruta afirma
dos hechos —el paquete se mueve y va en última milla— y cada uno queda escrito.

Las marcas de tiempo de esos eventos se separan un milisegundo
(`rutas.posterior_a`): caían en el mismo y el histórico, que se ordena por ellas,
mostraba la mitad de las veces el reparto antes que el tránsito. Se detectó en
las pruebas por su intermitencia.

**Descartado:** permitir `RECOLECTADO → EN_REPARTO` en la máquina de estados (es
el control C-07 de Cotejo y la Figura 2 del documento); y exigir que el conductor
marque a mano cada tránsito antes de salir (cinco toques por paquete: el
conductor volvería al chat).

La selección es **todo o nada**: si una guía no puede salir, no sale ninguna. Una
ruta a medias le diría al destinatario de la guía rechazada que su paquete va en
camino.

### 3. La ubicación se comparte solo con la ruta abierta, y se ve lo mínimo

- **Quién la comparte:** solo el conductor que inicia la ruta, sabiéndolo. La
  pantalla dice antes de salir qué se comparte y con quién, y durante la ruta
  muestra que lo está haciendo.
- **Cuándo:** desde que sale a ruta hasta que la termina. Sin ruta abierta, el
  teléfono no envía nada y el servidor rechaza posiciones (409).
- **La empresa** ve la posición y el recorrido con el permiso **`ruta:seguir`**.
- **El destinatario** ve, en la consulta pública, la posición del vehículo
  **redondeada a unos 11 m**, solo mientras su envío está en reparto en esa ruta
  y la posición tiene menos de 10 minutos. Ni el nombre del conductor ni sus
  otras paradas.
- **Cuánto se guarda:** el recorrido lleva `expira_en` y DynamoDB lo borra a los
  **30 días** (TTL en `10-datos.sh`). La ruta, sus paradas y los eventos de los
  envíos sí se conservan: son el histórico de la operación.

### 4. Dos operaciones nuevas en el catálogo cerrado

`ruta:operar` y `ruta:seguir`, en un área propia, «Rutas y ubicación». No se
reutilizan `evento:registrar` ni `envio:asignar` porque compartir y ver la
ubicación de una persona tiene que poder concederse y negarse por separado de
todo lo demás. El auditor no recibe ninguna: mirar dónde está alguien no es
revisar lo que se operó.

Las empresas ya aprovisionadas tienen sus roles escritos en la tabla, y esos
registros mandan sobre los de fábrica (ADR-010). Sin más, el conductor de una
empresa existente no podría salir a ruta hasta que alguien editara su rol. Para
eso cada rol guardado anota ahora **el catálogo que conocía** (`catalogo_conocido`),
y un rol de fábrica recibe las operaciones que su registro no conocía
(`authz.operaciones_nuevas_para`). Si la empresa vio la operación y la quitó,
sigue quitada. Los registros anteriores a esta anotación se comparan con
`CATALOGO_FUNDACIONAL`, las 19 operaciones originales.

### 5. Mirar el mapa deja constancia, una vez y no en cada refresco

Leer la ubicación de una persona se registra en la bitácora. Pero una pantalla
de seguimiento pregunta cada 10 s: registrar cada vuelta serían 360 eslabones
por hora y por pantalla. El servidor registra la primera consulta y entrega un
**testigo firmado** (JWT con audiencia propia, cinco minutos, ligado a la
persona y al recurso). Mientras la pantalla lo devuelva vigente, los refrescos no
se registran. Un cliente no puede fabricarlo; lo único que puede hacer es no
devolverlo, y entonces la consulta se registra.

Medido en la pila local: una ruta de cinco minutos con 32 posiciones y una
pantalla de seguimiento abierta todo el tiempo dejó **seis eslabones** —inicio,
consultas, cierre— y la cadena siguió válida.

Las posiciones **no** dejan eslabón por petición. Constan el inicio de la ruta
(con las guías), su cierre (con el recuento de posiciones) y cada intento
rechazado.

## Qué sigue fuera del alcance

| Fuera | Por qué |
|---|---|
| Planificación y optimización del orden de paradas | Exige geocodificar direcciones y datos de tráfico. El módulo «Rutas» sigue apagado con ese motivo. |
| Geocodificar las direcciones de destino | Las direcciones son texto libre colombiano («Cra 7 # 32-16, Torre 2»). Geocodificarlas con calidad exige un servicio de pago. «Cómo llegar» abre el navegador de mapas del conductor con la dirección. |
| Hora estimada de llegada al destinatario | Depende de lo anterior. |
| Transmisión con la pantalla apagada | Un sitio web no recibe el GPS en segundo plano. Se pide mantener la pantalla encendida (Wake Lock) y se avisa. Una aplicación instalada podría hacerlo. |
| Cerrar la ruta de otro (supervisor) | Hoy solo la cierra quien la conduce. Una ruta abandonada deja de mostrarse al público a los 10 minutos sin señal. |
| Ampliar Cotejo a las rutas | Cotejo es otro proyecto. Su control C-06 recorre las rutas de lectura de un envío; las de rutas tienen sus propias pruebas de aislamiento en `tests/e2e/test_rutas.py`. |

## Consecuencias

- **Positivas:** ninguna pieza de infraestructura nueva; la ruta se reanuda tras
  cerrar el navegador porque su estado vive en el servidor; el control C-07 no se
  toca; la ubicación tiene permiso, duración y retención propios.
- **Negativas:** el retraso de 10 a 25 s es visible; con la pantalla apagada no
  hay posición; la dirección del destinatario sale hacia el servicio de mapas que
  el conductor elija cuando pulsa «Cómo llegar».
- **Se vigila:** si el retraso del sondeo llega a ser un problema operativo, el
  siguiente paso es API Gateway WebSocket, con la tabla de conexiones en la
  misma tabla de envíos.
