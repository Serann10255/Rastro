# Diapositivas de sustentación. Dos etapas: compilar y servir.
#
# Existe para presentar sin preparar nada: con Docker basta un
# `docker compose up -d presentacion`, sin instalar Node ni dependencias en el
# equipo de la sala.
#
# El contexto de construcción es la raíz del repositorio y no `presentacion/`,
# porque el deck lee al construir el sistema de diseño (`design/`), la identidad
# de cada aplicación y los guiones de `documentacion/sustentacion/`. La ruta
# dentro de la imagen reproduce la del repositorio para que los alias de
# `vite.config.ts` resuelvan igual aquí y en desarrollo.
#
# Qué entra al contexto lo decide `Dockerfile.dockerignore`, no el de la raíz:
# este es el único módulo que necesita documentación para construirse.

FROM node:22-alpine AS construccion

WORKDIR /repo/presentacion

# Las dependencias se instalan antes de copiar el código para que un cambio en
# el guion no invalide la capa de dependencias.
COPY presentacion/package.json presentacion/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY design/ /repo/design/
COPY web/src/estilos/ /repo/web/src/estilos/
COPY web/public/ /repo/web/public/
COPY cotejo/web/src/estilos/ /repo/cotejo/web/src/estilos/
COPY cotejo/web/public/ /repo/cotejo/web/public/
COPY documentacion/sustentacion/ /repo/documentacion/sustentacion/

COPY presentacion/ ./

RUN npm run build

# --------------------------------------------------------------------------- #

FROM nginx:1.27-alpine

COPY --from=construccion /repo/presentacion/dist /usr/share/nginx/html
COPY presentacion/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
