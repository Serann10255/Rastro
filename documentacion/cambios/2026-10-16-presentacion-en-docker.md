# Cambios · 2026-10-16 · Diapositivas en Docker

Las diapositivas solo se podían abrir con Node instalado (`npm install` y
`npm run dev`). Para sustentar desde cualquier equipo con Docker, ahora son un
servicio más del compose:

```bash
docker compose up -d --build presentacion   # http://localhost:5177
```

También se levantan con la pila completa (`docker compose up -d`).

## Qué se añadió

| Archivo | Qué hace |
|---|---|
| `presentacion/Dockerfile` | Compila el sitio con Node 22 y lo sirve con nginx 1.27. Mismo patrón que `web/` y `cotejo/web/` |
| `presentacion/Dockerfile.dockerignore` | Contexto propio, por lista de lo permitido: el `.dockerignore` de la raíz excluye la documentación y este módulo necesita `documentacion/sustentacion/` |
| `presentacion/nginx.conf` | Sirve las tres páginas; `/rastro` → `/rastro/` con redirección relativa, para que no cambie el puerto |
| `docker-compose.yml` | Servicio `presentacion` en el puerto 5177, sin dependencias |

Documentación actualizada: [módulo presentacion](../modulos/presentacion/README.md),
[instalación y uso](../guias/instalacion-y-uso.md#presentar-la-sustentación) y
el `README.md` de la raíz.

## Comprobado

- La imagen construye y el compilador lee los dos guiones: 9 diapositivas
  Rastro y 10 Cotejo, sin avisos.
- `/`, `/rastro/` y `/cotejo/` responden 200; `/rastro` y `/rastro?guion`
  redirigen a `http://localhost:5177/rastro/…`, con el puerto publicado.
- `/rastro#2` abre la diapositiva 2 con su figura, sin errores en consola.
- Reconstruir sin cambios envía un contexto de 3,5 KB.

## A tener en cuenta

- El guion queda dentro de la imagen. Tras editar el Markdown hay que
  reconstruir (`--build`); recargar el navegador no basta.
- El contenedor y `npm run dev` usan el mismo puerto 5177: uno a la vez.
