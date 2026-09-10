# ADR-003 · Identificador de rastreo aleatorio y no consecutivo

Fecha: 2026-09-10 · Estado: aceptada

## Contexto

El requisito REQ-04 exige que el destinatario consulte el histórico de su envío
**sin autenticarse**, usando solo el identificador que le entregaron. Ese punto
de consulta es el único del sistema que responde sin token.

Un identificador consecutivo (ENV-001, ENV-002) es cómodo de comunicar por
teléfono y trivial de recorrer: cualquiera obtendría los envíos de toda la
empresa incrementando un número. Es la *referencia directa insegura a objetos*
que OWASP incluye en A01:2021, control de acceso deficiente, primer lugar de su
listado de riesgos en aplicaciones web.

## Decisión

El identificador de rastreo es un UUID versión 4. Se documenta como **control de
seguridad** y no como convención de nombres, para que nadie lo cambie después
por comodidad sin entender qué se pierde.

Se añaden dos refuerzos:

1. El servicio público valida el formato antes de consultar el almacenamiento.
   Un identificador que no sea un UUID canónico responde 422 y no llega a
   producir una lectura: el sondeo no cuesta ni una operación.
2. La respuesta pública es una vista reducida. Ni siquiera con un identificador
   válido se obtiene la organización, la identidad del mensajero, la dirección
   de origen o las coordenadas.

## Consecuencias

**A favor.** La enumeración deja de ser viable. El punto público no necesita
autenticación para ser defendible.

**En contra.** Un UUID es incómodo de dictar por teléfono. Se mitiga con un
enlace directo compartible (`rastreo.html?envio=<id>`) y con el campo de consulta
en monoespaciada, que reduce los errores de transcripción. Si en el futuro se
quisiera un código corto, tendría que ser un alias con vigencia limitada, nunca
un consecutivo.

**Verificable.** La prueba
`test_el_punto_publico_no_admite_identificadores_que_no_sean_aleatorios`
comprueba el rechazo del formato, y
`test_req04_la_vista_publica_no_expone_la_operacion_de_la_empresa` comprueba que
la respuesta no filtra datos internos.
