# ADR-005 · React con configuración en tiempo de ejecución

Fecha: 2026-09-10 · Estado: aceptada · Sustituye a la interfaz sin compilación

## Contexto

La primera interfaz era JavaScript sin dependencias ni paso de compilación. Se
eligió así para que el sitio se publicara copiando archivos y sobreviviera al
cierre de la sesión del laboratorio.

Esa decisión se sostuvo mientras la interfaz tenía dos pantallas. Al crecer el
alcance —panel por rol, listados con filtros, detalle con máquina de estados,
carga de evidencia en tres pasos, bitácora con verificación— aparecieron tres
problemas que no se resuelven con más disciplina:

- **Estado del servidor duplicado.** Cada pantalla mantenía su propia copia de
  los datos y su propia lógica de recarga. Tras una escritura había que acordarse
  de refrescar las vistas afectadas, y olvidarlo producía pantallas
  desactualizadas sin error visible.
- **Manipulación manual del documento.** Construir HTML con plantillas de texto
  obliga a escapar cada valor a mano. Un olvido es una inyección.
- **Sin comprobación de tipos.** El contrato con el backend solo se verificaba
  al ejecutar, y un cambio de nombre de campo aparecía como `undefined` en
  pantalla.

## Decisión

React 18 con TypeScript, compilado con Vite. Enrutamiento con React Router y
estado del servidor con TanStack Query.

**Sin biblioteca de componentes de terceros.** El sistema de diseño es propio,
con fichas de color, espacio y tipografía. La razón no es purismo: el proyecto se
audita a sí mismo, y conviene que todo lo que se sirve sea código revisable sin
arrastrar una cadena de suministro ajena.

### La condición que hace compatible esta decisión con REQ-09

El patrón habitual de Vite es `import.meta.env.VITE_API_URL`, que **hornea la
dirección de la API dentro del bundle al compilar**. Aplicado aquí, trasladar el
sistema a otra cuenta del laboratorio obligaría a recompilar la interfaz, que es
exactamente lo que el requisito de portabilidad prohíbe.

Por eso la configuración se lee en tiempo de ejecución de `configuracion.json`,
un archivo que la etapa `60-sitios.sh` escribe con los identificadores del
despliegue y publica junto al sitio. El bundle no contiene ninguna dirección.

Esta condición no es negociable: si alguien introduce una variable de entorno de
compilación con la URL, REQ-09 deja de cumplirse aunque el resto siga igual.

## Consecuencias

**A favor.** El contrato con el backend está tipado y un cambio de campo falla al
compilar, no en producción. React Query centraliza reintento, invalidación tras
escritura y el estado de «recargando sin borrar lo que ya se ve», que importa
porque el conductor trabaja con conectividad intermitente. React escapa el
contenido por omisión.

**En contra.** Aparece un paso de compilación y un directorio `node_modules` que
antes no existían. Se acota así:

- La imagen de contenedor es de dos etapas y la final **solo sirve archivos**: no
  lleva Node ni dependencias, igual que el despliegue en el almacenamiento de
  objetos, donde tampoco hay servidor de aplicaciones.
- La secuencia de despliegue compila y sincroniza; no hay pasos manuales.
- El resultado sigue siendo un sitio estático: se publica copiando archivos y
  responde entre sesiones del laboratorio, que era la propiedad que motivó la
  decisión original.

**Coste.** Unos 71 kB comprimidos de biblioteca, cargados una vez y cacheados un
año por llevar huella en el nombre. Es asumible para una interfaz que se abre
varias veces al día en el mismo dispositivo.

**Lo que no cambia.** El sitio sigue sin necesitar servidor de aplicaciones, la
dirección de la API sigue leyéndose en ejecución, y la autorización la sigue
decidiendo el servidor: la interfaz oculta lo que un rol no puede hacer, pero eso
es comodidad y no control.
