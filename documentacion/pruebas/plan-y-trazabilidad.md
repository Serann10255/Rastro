# Plan de pruebas y trazabilidad de requisitos

Fecha: 2026-09-10 · Versión: 0.2

```bash
python -m pytest -q
```

**234 pruebas en verde y 4 omitidas** (36 s). No requieren Docker ni credenciales de
AWS: usan el repositorio en memoria y un almacén de evidencias simulado, de modo
que se ejecutan sin consumir el presupuesto del laboratorio.

| Conjunto | Ubicación | Pruebas | Qué verifica |
|---|---|---|---|
| Unitarias de Rastro | `tests/unit/` | 82 | Máquina de estados y códigos, cadena de hash, reparto de roles, claves y coherencia entre la semilla de módulos y la interfaz |
| Extremo a extremo de Rastro | `tests/e2e/` | 100 | Los nueve requisitos, la identidad, los maestros, el tablero, el lote, las guías, los módulos y el equipo |
| Cotejo | `cotejo/tests/` | 27 | Catálogo, papeles de trabajo, reproducibilidad, informe y **contrato con el servicio de identidad de Rastro** |

Desglose de extremo a extremo:

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `test_ciclo_de_vida.py` | 10 | REQ-01 a REQ-03 y REQ-05 sobre el flujo completo |
| `test_consulta_publica_y_bitacora.py` | 13 | REQ-04, REQ-07 y REQ-08 |
| `test_control_de_acceso_y_aislamiento.py` | 15 | REQ-06 y la matriz de autorización sobre la pila |
| `test_identidad_y_maestros.py` | 29 | Contraseñas, sesiones, cuentas, maestros, catálogo y tablero |
| `test_lote_y_guias.py` | 15 | Registro masivo, guías y exportación |
| `test_modulos_y_equipo.py` | 14 | Módulos por organización y vista del equipo |
| `test_roles.py` | 19 | Roles configurables y las cuatro barreras que los hacen seguros |

Y una prueba de coherencia entre fuentes, en `tests/unit/test_modulos_declarados.py`:
comprueba que cada módulo de la semilla apunta a una **ruta que el enrutador
define**, pide un icono que el sistema de diseño sabe dibujar y un contador que
la pantalla sabe resolver. Existe por un fallo real —la semilla decía `/guias` y
la ruta es `/envios/guias`, y el menú llevaba a una página inexistente—: al mover
el catálogo a la base de datos aparecieron dos fuentes que podían discrepar en
silencio, cuando antes una ruta mal escrita no compilaba.

**El coste de derivación de contraseñas se baja a 1 000 iteraciones en las
pruebas** (`tests/conftest.py`, variable `RASTRO_PBKDF2_ITERACIONES`). A 600 000
la suite pasaba de segundos a cuatro minutos, y una suite lenta es una suite que
nadie ejecuta. Es seguro porque lo que se verifica es el mecanismo —que la
contraseña no se almacena en claro, que la verificación funciona, que el formato
permite migrar— y no el coste, que es un parámetro.

---

## Trazabilidad de los requisitos de Rastro

Cada criterio de aceptación del documento está expresado como *dado-cuando-
entonces*, y cada uno tiene al menos una prueba que lo comprueba.

| Req. | Criterio de aceptación | Prueba | Estado |
|---|---|---|---|
| REQ-01 | Registrar un envío devuelve un identificador único no predecible y crea el registro maestro en `CREADO` | `test_req01_el_envio_se_crea_con_identificador_unico_y_estado_creado` | ✅ |
| REQ-02 | El punto de control queda con el identificador del usuario y la marca de tiempo del servidor | `test_req02_el_punto_de_control_conserva_autor_y_marca_de_tiempo_del_servidor` | ✅ |
| REQ-03 | De `CREADO` a `ENTREGADO` responde 400 y registra el intento con `DENY` | `test_req03_no_se_puede_saltar_de_creado_a_entregado` | ✅ |
| REQ-04 | Un identificador válido devuelve maestro y eventos en orden cronológico, sin autenticación | `test_req04_el_historico_completo_se_consulta_sin_autenticacion` | ✅ |
| REQ-05 | El conductor recibe un enlace válido por un tiempo definido; el archivo queda asociado y cifrado | `test_req05_ciclo_completo_con_evidencia_cargada_y_confirmada` | ✅ |
| REQ-06 | Un usuario de la organización A pidiendo un envío de la B recibe *no existe* y queda registrado | `test_req06_un_usuario_de_otra_organizacion_recibe_recurso_inexistente` | ✅ |
| REQ-07 | Un conductor creando un envío recibe 403 y existe registro con actor, grupo, acción, recurso y `DENY` | `test_req07_el_conductor_no_puede_crear_envios_y_el_intento_queda_registrado` | ✅ |
| REQ-08 | Tras modificar un registro directamente en el almacén, el verificador señala el punto de ruptura | `test_req08_tras_una_alteracion_controlada_el_verificador_senala_la_ruptura` | ✅ |
| REQ-09 | El despliegue se reproduce sin editar código ni intervenir en la consola | `deploy/aws/90-configuracion.sh` (comprobación automática) | ⚠️ pendiente de ejecución en la cuenta |

REQ-09 es el único que no puede cerrarse con una prueba automatizada en este
entorno: exige desplegar en una cuenta vacía. La secuencia está versionada y
comprueba por su cuenta que no queden identificadores literales en el código,
pero **no se ha ejecutado contra el laboratorio**. Véase
[el estado del despliegue](../despliegue/entorno-aws.md#estado-de-verificacion).

---

## Pruebas que van más allá del criterio literal

El criterio de aceptación fija el mínimo. Estas pruebas cubren lo que un criterio
literal dejaría fuera:

| Prueba | Por qué existe |
|---|---|
| `test_req06_ninguna_ruta_de_lectura_cruza_la_frontera_de_organizacion` | Recorre las tres rutas de lectura. Bastaría una sin filtrar para que el aislamiento falle |
| `test_req06_la_bitacora_de_una_organizacion_no_contiene_registros_de_otra` | El aislamiento también aplica a la evidencia de auditoría |
| `test_recalcular_el_hash_de_un_registro_alterado_rompe_el_enlace_siguiente` | El atacante que repara su propio eslabón no queda cubierto |
| `test_eliminar_un_registro_intermedio_se_detecta_como_salto_de_secuencia` | Borrar es una alteración tanto como modificar |
| `test_el_conductor_reporta_la_incidencia_pero_no_puede_reanudar` | Separación de funciones sobre la operación más sensible |
| `test_una_evidencia_declarada_pero_no_cargada_no_acredita_la_entrega` | El cliente no puede inventar el identificador de una evidencia |
| `test_la_bitacora_no_expone_ninguna_ruta_de_escritura` | Comprueba el contrato del servicio, no solo su comportamiento |
| `test_un_token_firmado_con_otro_secreto_se_rechaza` | La validación en el servicio no depende de la puerta de enlace |
| `test_las_credenciales_invalidas_no_distinguen_usuario_de_clave` | Distinguirlas permitiría enumerar cuentas |
| `test_el_punto_publico_no_admite_identificadores_que_no_sean_aleatorios` | El sondeo no debe costar ni una lectura del almacenamiento |
| `test_la_contrasena_nunca_se_almacena_en_claro` | Lee el registro guardado y comprueba que la clave no aparece por ninguna parte |
| `test_dos_usuarios_con_la_misma_clave_tienen_hashes_distintos` | Sin sal por contraseña, una tabla precalculada rompe todas a la vez |
| `test_un_hash_corrupto_no_lanza_sino_que_falla` | Un registro dañado debe negar el acceso, no tumbar el servicio con un 500 |
| `test_el_token_de_refresco_no_sirve_para_operar` | Si sirviera, la separación entre los dos tokens no significaría nada |
| `test_el_refresco_se_rota_y_el_anterior_deja_de_valer` | Es lo que hace que un robo se note en lugar de convivir en silencio |
| `test_cerrar_sesion_la_revoca_en_el_servidor` | Sin revocación, cerrar sesión solo borra el token del navegador |
| `test_cambiar_la_clave_cierra_las_demas_sesiones` | Quien cambia su clave sospecha que alguien la tiene |
| `test_no_se_puede_dejar_la_organizacion_sin_administrador` | El bloqueo sería irreversible desde la propia aplicación |
| `test_una_cuenta_se_crea_siempre_en_la_organizacion_de_quien_la_crea` | Un administrador no debe poder sembrar cuentas en otra empresa |
| `test_una_tienda_de_otra_organizacion_no_se_puede_referenciar` | El aislamiento aplica también a los datos maestros |
| `test_una_fila_mala_no_tumba_el_lote` | Fija el éxito parcial como comportamiento, no como casualidad |
| `test_el_lote_deja_un_solo_eslabon_en_la_bitacora` | Doscientos eslabones por un despacho enterrarían el histórico |
| `test_pedir_guias_en_lote_no_es_una_via_para_ver_envios_ajenos` | La operación en bloque es el sitio donde se cuela un salto de filtro |
| `test_la_guia_no_lleva_el_valor_declarado` | La etiqueta va pegada a la caja y la ve cualquiera |
| `test_el_tablero_de_una_organizacion_no_cuenta_envios_de_otra` | Un total también es información |
| `test_el_tablero_incluye_los_estados_en_cero` | Un cero es un dato; omitirlo cambia la forma del tablero entre dos cargas |
| `test_la_serie_diaria_incluye_los_dias_sin_movimiento` | Una serie con huecos miente sobre la tendencia |
| `test_nadie_concede_un_permiso_que_no_tiene` | Sin esto, un rol con `rol:administrar` se promociona a sí mismo |
| `test_la_escalada_rechazada_queda_en_la_bitacora` | Un intento de concederse permisos es lo que un auditor busca |
| `test_el_administrador_conserva_todo_aunque_la_tabla_diga_otra_cosa` | La tabla no manda sobre el seguro contra quedarse sin acceso |
| `test_una_cuenta_no_puede_ser_operador_y_auditor` | Ningún rol rompe la regla por separado; la suma sí |
| `test_un_rol_no_puede_conceder_una_operacion_inventada` | El catálogo es cerrado: lo que no está en el código no existe |
| `test_cada_organizacion_ve_sus_modulos` | Si los módulos fueran un catálogo global, apagar uno para una empresa lo apagaría para todas |
| `test_no_se_puede_apagar_un_modulo_sin_decir_por_que` | Un módulo ausente sin motivo parece un olvido, no una decisión |
| `test_un_modulo_disponible_necesita_ruta` | Una tarjeta que no hace nada al pulsarla se lee como un fallo del sistema |
| `test_el_equipo_no_expone_la_ficha_de_la_cuenta` | La vista reducida es lo que permite que un despachador la consulte sin administrar cuentas |
| `test_un_mensajero_desactivado_deja_de_aparecer` | Asignar a una cuenta desactivada produce un envío que nadie puede mover |

---

## Pruebas del programa de auditoría

El riesgo más grave de Cotejo (R-02) es que un defecto del ejecutor clasifique
como conforme un control que no lo está: una conclusión falsa es peor que no
concluir. Las pruebas atacan ese riesgo comprobando cada mecanismo **en los dos
sentidos**.

| Prueba | Qué demuestra |
|---|---|
| `test_las_tres_alteraciones_del_catalogo_modifican_realmente_la_copia` | Que la alteración de prueba altera algo. Sin esta guarda, una alteración vacía haría concluir que el verificador no detecta nada |
| `test_cada_forma_de_alteracion_se_detecta_con_su_tipo` | Que el verificador detecta cada manipulación **y** la clasifica bien |
| `test_la_cadena_sin_alterar_verifica` | Que no inventa rupturas donde no las hay |
| `test_editar_un_papel_de_trabajo_se_detecta` | Que el almacén hace detectable la edición de la evidencia |
| `test_un_control_no_ejecutado_no_cuenta_como_conforme` | Que el informe no transmite más cobertura que la real |
| `test_una_prueba_que_lanza_una_excepcion_no_detiene_la_ejecucion` | Que un fallo produce un control marcado, no papeles truncados |
| `test_una_clasificacion_distinta_rompe_la_reproducibilidad` | Que el comparador detecta divergencias, no solo confirma coincidencias |

### Un defecto encontrado por esta vía

En la primera ejecución real, Cotejo reportó C-08 como **desviado**: *el
verificador NO detectó la alteración con hash recalculado*.

El defecto no estaba en el sistema auditado sino en la propia prueba: alteraba
el campo `resultado` poniéndole `"ALLOW"`, y el registro elegido ya era `ALLOW`.
La copia quedaba idéntica al original, el verificador informaba cadena válida
—correctamente— y la prueba lo interpretaba como un fallo de detección.

Se corrigió usando valores que ningún registro real puede tener y añadiendo una
guarda que comprueba que la copia difiere del original antes de evaluarla. La
guarda está cubierta por
`test_las_tres_alteraciones_del_catalogo_modifican_realmente_la_copia`.

Es exactamente el tipo de defecto que la validación en doble sentido existe para
encontrar, y merece registrarse: sin ella, la prueba habría podido producir el
resultado contrario —un falso conforme— sin que nadie lo notara.

---

## Verificación manual contra la pila desplegada

Además de las pruebas automatizadas, el flujo completo se ejecutó contra los
contenedores reales (DynamoDB Local, MinIO, ocho servicios y la puerta de
enlace):

| Paso | Resultado |
|---|---|
| Autenticación de los cuatro roles en dos organizaciones | ✅ |
| Registro de envío, asignación y recorrido con coordenadas | ✅ |
| Salto `CREADO → ENTREGADO` | 400 ✅ |
| Conductor creando envío | 403 ✅ |
| Organización ajena consultando el envío | 404 ✅ |
| Enlace prefirmado y **carga directa del archivo al almacenamiento** | 200 ✅ |
| Confirmación de la evidencia con versión del objeto | ✅ |
| Entrega sin evidencia / con evidencia | 400 / 201 ✅ |
| Consulta pública sin token, sin filtrar datos internos | ✅ |
| Bitácora restringida al auditor y cadena verificada | ✅ |
| Inicio de sesión de las diez cuentas con contraseñas derivadas | ✅ |
| Usuario inexistente y clave incorrecta responden lo mismo | ✅ |
| Tablero de la empresa con los nueve estados y sus códigos | ✅ |
| Alta de usuario, cambio de rol y desactivación | ✅ |
| Registro masivo desde CSV con una fila inválida | 19 de 20 registrados ✅ |
| Selección múltiple e impresión de guías con código de barras | ✅ |
| Exportación a CSV con código de estado | ✅ |
| Alta y desactivación de tienda, cliente y transportista | ✅ |
| Navegación y menú de operaciones servidos desde la tabla de maestros | ✅ |
| Asignación de mensajero eligiendo del directorio de la empresa | ✅ |
| Cotejo descubriendo sus cuentas de prueba en el directorio auditado | 5/8 conformes ✅ |

### Interfaz web

Comprobada a 360 px de ancho, que es el mínimo exigido por las reglas del
repositorio:

| Comprobación | Resultado |
|---|---|
| Sin scroll horizontal en el documento | ✅ tras corregir un defecto (véase abajo) |
| Tabla de bitácora scrollea dentro de su contenedor | ✅ |
| Áreas táctiles de 44 px | ✅ |
| Navegación colapsada en fila deslizable | ✅ |
| Identificadores UUID sin desbordar | ✅ |
| Las once pantallas, incluidas guías y administración | ✅ |
| Columna lateral a 1280 px y barra deslizable a 360 px, en las dos interfaces | ✅ |
| Ningún área táctil por debajo de 44 px | ✅ tras corregir dos enlaces |
| Tabla de órdenes con selección múltiple a 360 px | ✅ |
| Etiqueta de guía legible en impresión | ✅ |

**Defecto encontrado y corregido.** La tabla de bitácora (ancho mínimo 640 px)
estiraba su contenedor y trasladaba el desbordamiento a la página: el documento
medía 869 px en un viewport de 360. La causa es que un elemento de rejilla no
baja por omisión de su ancho de contenido. Se corrigió con `min-width: 0` en los
contenedores de rejilla y `max-width: 100%` en el contenedor de tabla. Tras la
corrección, el documento mide 360 px y la tabla scrollea dentro de su bloque.

---

## Qué no cubren estas pruebas

Se declara en lugar de omitirse:

- **Los controles de infraestructura.** Cifrado con llave administrada, registro
  de actividad y bloqueo de acceso público no existen en el entorno local.
  Simular un control equivaldría a no verificarlo. Los verifica Cotejo contra la
  cuenta desplegada, y hasta entonces figuran como *no ejecutados*.
- **La adopción real.** El proyecto no contará con usuarios reales en
  producción, de modo que la adopción no puede medirse. Lo que sí puede
  verificarse es la usabilidad de la operación crítica en una prueba controlada.
- **El comportamiento bajo carga.** No hay pruebas de concurrencia sobre el
  encadenamiento de la bitácora más allá de la escritura condicional.
