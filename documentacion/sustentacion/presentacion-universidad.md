# Presentación a la universidad — Rastro

```yaml
proyecto: Rastro
subtitulo: Saber dónde está cada paquete y poder demostrar qué pasó con él
asignatura: Presentación a la comunidad CUN · público general
grupo: 30112 · Periodo 2026B
docente: Daniel Alejandro García Rodríguez
equipo: [Sergio Alejandro Montoya Granados, Nicolás Torres Perdomo, Oscar Julián Rincón Bejarano]
marca: rastro
portadillas: no
```

> **Para quién es.** Para toda la universidad: estudiantes de cualquier
> carrera, docentes y directivos. Nadie tiene por qué saber qué es una función
> Lambda. Cada idea se cuenta con algo que el público ya conoce —esperar un
> paquete, un recibo, una cadena, un cofre— y lo técnico queda en «Si
> preguntan», para quien lo pida.

> **Ninguna cifra es decorativa**, igual que en las sustentaciones: todas salen
> de la verificación del despliegue, de la ejecución de Cotejo en AWS del
> 16/10/2026 o de la suite de pruebas ejecutada el 23/10/2026.

---

## 1 · Portada

**RASTRO**
¿Dónde está mi paquete?

Sergio Montoya · Nicolás Torres · Oscar Rincón
Cloud Computing y Auditoría de Sistemas · Grupo 30112

![Seguimiento: la empresa ve a sus mensajeros en el mapa](captura:rastro-seguimiento)
![Consulta pública: «Su envío va en camino»](captura:rastro-rastreo-en-camino)
![Panel de la empresa](captura:rastro-panel)
![Bitácora: la historia que nadie puede borrar](captura:rastro-bitacora)

> Guion: Sergio. Buenas tardes a todos. Somos Sergio Montoya, Nicolás Torres y
> Oscar Rincón. Este semestre construimos Rastro, un sistema que le permite a
> una empresa de mensajería saber dónde está cada paquete y, sobre todo, poder
> demostrar qué pasó con él.

> Indicación: Cinco segundos. Mirar al público, no a la pantalla. A la derecha
> pasan solas cuatro pantallas de la aplicación; no hay que comentarlas.

---

## 2 · Un problema que todos conocemos

**«Su pedido va en camino.»**
¿Dónde? ¿Con quién? ¿Desde cuándo?

En una mensajería pequeña, la respuesta está repartida en cuatro sitios, y ninguno manda.

**Cuando un paquete se pierde, nadie puede probar qué pasó.**

![Lo que se sabe de un paquete, repartido en cuatro sitios](figura:informacion-repartida)

> Guion: Sergio. Todos hemos esperado un paquete que «ya va en camino». Pero
> ¿dónde va, con quién, desde cuándo? En una mensajería pequeña de Bogotá, esa
> respuesta está regada entre la memoria del mensajero, un chat, una hoja de
> cálculo y el teléfono del despachador. Y cuando un paquete se pierde, nadie
> puede probar qué pasó: se arregla de palabra y la empresa paga.

> Indicación: Hacer la pregunta al público con la mano levantada: «¿quién ha
> esperado un paquete que nunca llegó?». Esperar dos segundos.

> Si preguntan: ¿De dónde sale el problema? De la experiencia laboral del
> equipo en mensajería urbana. Es observación, no un estudio con encuestas, y
> así lo declaramos en el documento del proyecto.

---

## 3 · Qué es Rastro

Una aplicación en internet donde **cada paquete tiene su historia completa**: quién lo movió, cuándo y con qué prueba.

| Quién | Qué hace |
|---|---|
| **La empresa** | Crea las guías, asigna mensajeros y ve toda la operación |
| **El mensajero** | Desde su celular recoge, sale a ruta y entrega con foto |
| **El cliente** | Consulta su envío con un código, **sin crear cuenta** |

Varias empresas pueden usarla a la vez, y **ninguna ve los datos de otra**.

![Panel de la empresa](captura:rastro-panel)
![Un envío y toda su historia](captura:rastro-envio)

> Guion: Sergio. Rastro es una aplicación en internet donde cada paquete tiene
> su historia completa: quién lo movió, cuándo y con qué prueba. La usan tres
> personas: la empresa, que crea las guías y asigna mensajeros; el mensajero,
> desde su celular; y el cliente, que consulta su envío con un código, sin
> crear cuenta. Y varias empresas pueden usarla a la vez sin ver los datos de
> las otras. Nicolás les cuenta el viaje de un paquete.

> Indicación: A la derecha pasa primero el panel de la empresa y luego el
> detalle de un envío con su historia.

> Si preguntan: ¿Es una aplicación del celular? Es una página web que funciona
> en el celular, el computador o la tableta, sin instalar nada. ¿Para quién es?
> Para mensajerías pequeñas y medianas que hoy trabajan con chats y hojas de
> cálculo.

---

## 4 · El viaje de un paquete

Cada paquete avanza **paso a paso**, y cada paso queda con nombre, fecha y hora.

**No se puede saltar un paso:** no se puede marcar como entregado algo que nunca salió.

Si algo sale mal, se registra la **novedad** y la empresa decide qué sigue.

![Los pasos de un envío](figura:viaje-del-paquete)

> Guion: Nicolás. Gracias, Sergio. Un paquete hace este viaje: la empresa lo
> registra, se le asigna un mensajero, él lo recoge, lo transporta, sale a
> repartirlo y lo entrega con una foto. Cada paso queda con nombre, fecha y
> hora. Y el sistema no deja saltarse ninguno: no se puede marcar como
> entregado algo que nunca salió de la bodega. Si algo pasa en el camino, se
> registra la novedad.

> Indicación: Recorrer la figura de arriba abajo con la mano, sin leer cada
> caja.

> Si preguntan: Los estados llevan un número (10 creado, 20 asignado… 60
> entregado) porque es lo que viaja en los archivos que se intercambian con
> clientes y transportadoras: un número no cambia con la ortografía. Además de
> los seis del camino normal están incidencia, devuelto y cancelado. Cualquier
> salto no permitido se rechaza y el intento queda registrado.

---

## 5 · En vivo: el mensajero en el mapa

El mensajero elige qué paquetes lleva y **sale a ruta**.

- **La empresa** lo ve moverse en el mapa.
- **El cliente** ve que su paquete se acerca.
- La entrega se cierra con **foto y ubicación**.

**Privacidad primero:** solo mientras la ruta está abierta. El cliente ve una ubicación aproximada, sin el nombre del mensajero ni sus otras entregas.

![Seguimiento: la empresa ve sus rutas en el mapa](captura:rastro-seguimiento)
![Modo ruta: lo que ve el mensajero](captura:rastro-modo-ruta)
![El cliente: «Su envío va en camino»](captura:rastro-rastreo-en-camino)

> Guion: Nicolás. Esto nos lo pidió el profesor después de la segunda entrega,
> y lo construimos. El mensajero elige qué paquetes lleva y sale a ruta. Desde
> ese momento la empresa lo ve moverse en el mapa y el cliente ve que su
> paquete se acerca. Pero cuidamos algo: es la ubicación de una persona. Solo
> se comparte mientras la ruta está abierta, y el cliente ve un punto
> aproximado, sin el nombre del mensajero ni sus otras entregas.

> Indicación: Las tres pantallas pasan solas: la empresa, el mensajero y el
> cliente. Si alguien pide verlas de cerca, `z` amplía la que se está viendo.

> Si preguntan: El celular envía su posición cada quince segundos, o cada cinco
> si se está moviendo; si se queda sin señal, las guarda y las manda juntas cuando vuelve. El recorrido se
> conserva treinta días. Funciona en el navegador del celular, sin instalar
> nada, porque el sitio va por HTTPS: sin eso, el teléfono no entrega el GPS.

---

## 6 · Demostración

**Ahora, en vivo.**

Sergio es el mensajero.
Oscar es el cliente.
Esta pantalla es la empresa.

![La demostración, paso a paso](figura:demo-en-vivo)

> Guion: Nicolás. Y ahora no se lo contamos: se lo mostramos. Sergio es el
> mensajero. Va a salir a ruta desde su celular, y aquí, en la pantalla de la
> empresa, lo vamos a ver aparecer en el mapa. Oscar es el cliente: desde su
> propio celular, con el código de la guía, va a ver que su paquete viene en
> camino. Al final, Sergio lo entrega con una foto.

> Indicación: Dos minutos, fuera del tiempo del guion. **Diez minutos antes:**
> abrir el laboratorio (con la sesión cerrada la API responde con error),
> entrar en el celular de Sergio con la cuenta de conductor reservada para la
> demostración y dejar una guía recogida; tener abierta en el portátil la
> pantalla Seguimiento con la cuenta de administración; tener en el celular de
> Oscar la consulta pública con el código de esa guía. Dentro de un salón el
> GPS puede tardar o quedarse quieto: si pasa, decirlo con calma y volver a la
> diapositiva 5, que muestra lo mismo en capturas.

> Si preguntan: ¿Y si no hay internet en el celular? Las posiciones se guardan
> y se envían juntas cuando vuelve la señal. ¿Y si cierra el navegador a mitad
> de la ruta? Al volver, la ruta aparece tal como quedó: vive en el servidor,
> no en el teléfono.

---

## 7 · ¿Por qué en la nube?

Rastro no vive en un computador de la universidad: vive en **Amazon Web Services**.

| | Servidor propio | En la nube |
|---|---|---|
| Costo | Comprarlo y mantenerlo | Se paga por uso, **como la luz** |
| Disponibilidad | Si se apaga, se cae | Responde a cualquier hora |
| Crecimiento | Comprar más equipos | Crece con la demanda |

Todo el semestre con un presupuesto de **50 dólares**.

![Pago por uso, como la luz](figura:pago-por-uso)

> Guion: Oscar. Gracias, Nicolás. Lo que acaban de ver no corre en un
> computador nuestro: corre en la nube de Amazon. ¿Por qué? Porque un servidor
> propio hay que comprarlo, mantenerlo y, si se apaga, se cae el servicio. En
> la nube se paga por uso, como la luz: si nadie consulta un paquete, casi no
> se paga nada, y si llegan mil consultas, crece solo. Así trabajamos todo el
> semestre con un presupuesto de cincuenta dólares.

> Indicación: La comparación con el recibo de la luz es la idea que se tiene
> que quedar. No nombrar servicios de AWS si nadie pregunta.

> Si preguntan: Por dentro son funciones que solo se ejecutan cuando alguien
> hace una petición (AWS Lambda), tablas DynamoDB, un almacén cifrado para las
> fotos (S3 con llave KMS) y el registro de actividad de la cuenta
> (CloudTrail). El único cargo fijo es la llave de cifrado. El despliegue
> completo se recrea en una cuenta vacía con un solo comando, en unos ocho
> minutos.

---

## 8 · Seguro por diseño

- **Cada empresa ve solo lo suyo.** Pedir un paquete ajeno responde como si no existiera.
- **Nadie borra la historia.** Cada registro guarda la huella del anterior: si alguien cambia uno, la cadena se rompe y se nota.
- **Las fotos de entrega van en un cofre cifrado**, con llave propia.
- **Nadie se revisa a sí mismo.** El administrador puede todo, menos leer la bitácora; el auditor la lee, pero no puede cambiar nada.

![Una cadena de registros](figura:cadena-de-registros)
![La bitácora, verificada](captura:rastro-bitacora)

> Guion: Oscar. Que funcione no basta; tiene que ser confiable. Cuatro ideas.
> Cada empresa ve solo lo suyo. Nadie puede borrar la historia: cada registro
> guarda la huella del anterior, como los eslabones de una cadena, y si
> alguien cambia uno, la cadena se rompe y se nota. Las fotos de entrega van
> cifradas, como en un cofre con llave. Y nadie se revisa a sí mismo: el
> administrador puede todo menos leer la bitácora, y el auditor la lee sin
> poder cambiar nada.

> Indicación: En la figura, señalar el eslabón roto. Luego pasa sola la
> pantalla de la bitácora con la cadena verificada.

> Si preguntan: La huella es un resumen criptográfico (SHA-256) de cada
> registro más la del anterior. Hay cinco roles de fábrica —administrador,
> coordinador, despachador, conductor y auditor— y cada empresa puede crear
> los suyos, pero ninguno puede operar y leer la bitácora a la vez. Solo hay
> datos de prueba: ningún dato personal real ha entrado al sistema.

---

## 9 · Un auditor que no somos nosotros

Decir que algo es seguro es fácil. Por eso construimos **Cotejo**: un segundo programa que revisa a Rastro, ya desplegado.

```
11 controles · 10 conformes · 1 desviado
```

**Y encontró un error real.** Una clave secreta quedó publicada 27 minutos. La cambiamos, comprobamos que la vieja ya no sirve y hoy Cotejo la vigila.

> Contar el error también es parte del resultado.

![Cotejo: lo que hay que arreglar](captura:cotejo-hallazgos)

> Guion: Oscar. Decir «es seguro» es fácil; por eso no nos creímos a nosotros
> mismos. En la otra materia, Auditoría de Sistemas, construimos Cotejo: un
> segundo programa que revisa a Rastro en la nube. Revisa once controles: diez
> salen bien y uno no. Ese uno es un error real: una clave secreta quedó
> publicada veintisiete minutos. La cambiamos, comprobamos que la vieja ya no
> sirve y ahora Cotejo la vigila. Contarlo también es parte del resultado.

> Indicación: Decir el error despacio y sin pena: es lo que más confianza da.
> La pantalla es de Cotejo y está en lenguaje llano a propósito: arriba, el
> error de la clave (H-01).

> Si preguntan: El control desviado sigue saliendo así a propósito: la clave
> vieja sigue en el historial del repositorio, aunque ya no sirve para nada.
> Corregirlo exige reescribir el historial, y está en el plan. Las otras dos de
> la pantalla («se sabe y no se puede arreglar aquí») son la llave maestra que
> comparten todas las piezas: el laboratorio no deja crear llaves propias, y es
> lo primero que se arregla con la cuenta de la universidad. Cotejo guarda cada
> revisión con una huella que permite comprobar después que nadie la alteró.
> La captura es de una revisión en un computador del equipo; las cifras de la
> lámina son las de la revisión en la nube del 16/10/2026.

---

## 10 · Cómo lo hicimos

```
3 estudiantes · 12 semanas · 327 pruebas automáticas · 15 decisiones registradas
```

- **Dos materias, un proyecto:** en Cloud Computing lo construimos; en Auditoría de Sistemas lo revisamos.
- **Una regla:** nada se daba por terminado sin una prueba automática que lo comprobara.
- **Las limitaciones del laboratorio** se volvieron parte del diseño.

> Guion: Sergio. ¿Cómo lo hicimos? Tres estudiantes, doce semanas y dos
> materias: en una lo construimos y en la otra lo auditamos. Teníamos una
> regla: nada estaba terminado sin una prueba automática que lo comprobara.
> Hoy son trescientas veintisiete. Y escribimos cada decisión importante con
> sus razones, quince en total. El laboratorio de AWS tenía límites, como
> sesiones de cuatro horas, y en lugar de pelear con ellos, los usamos para
> diseñar.

> Indicación: Las cifras cuentan desde cero al entrar; dejar que terminen
> antes de hablar.

> Si preguntan: 327 pruebas superadas y 5 omitidas, que necesitan condiciones
> que no existen en una ejecución local; incluyen las de Rastro y las de
> Cotejo. Las decisiones están en el repositorio como registros de decisión
> de arquitectura, cada una con las alternativas descartadas.

---

## 11 · Lo que sigue

- **Una cuenta propia en AWS**, asignada por la universidad, sin los límites del laboratorio.
- **Una aplicación para celular y escritorio**, hecha con Flet, en construcción.
- **Probarlo con una mensajería real.**

> Gracias. ¿Preguntas?

`github.com/Serann10255/Rastro`

![Su envío va en camino](captura:rastro-rastreo-en-camino)

> Guion: Sergio. ¿Qué sigue? La universidad nos va a dar una cuenta propia en
> AWS, sin los límites del laboratorio, para dejar el sistema completo.
> Estamos construyendo una aplicación para celular y escritorio. Y lo más importante:
> queremos probarlo con una mensajería de verdad. Muchas gracias. ¿Preguntas?

> Indicación: Después de «¿preguntas?», callarse y esperar. Si no hay, dar las
> gracias otra vez y bajar.

> Si preguntan: Con la cuenta propia se puede dar a cada pieza solo los
> permisos que necesita, publicar el sitio con una dirección propia y guardar
> la bitácora fuera del alcance de quien administra la cuenta: tres cosas que
> el laboratorio no permitía. ¿Se puede vender? Esa es la idea: está hecho
> para que varias empresas lo usen a la vez.
