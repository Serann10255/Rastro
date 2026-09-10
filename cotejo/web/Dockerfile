# Interfaz del programa de auditoria. Dos etapas: compilar y servir.
#
# El contexto de construccion es la raiz del repositorio y no `cotejo/web/`,
# porque el sistema de diseno vive en `design/` y lo comparten las dos
# interfaces. La ruta dentro de la imagen reproduce la del repositorio para que
# el alias `@design` resuelva igual aqui y en desarrollo.

FROM node:22-alpine AS construccion

WORKDIR /repo/cotejo/web

COPY cotejo/web/package.json cotejo/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY design/ /repo/design/
COPY cotejo/web/tsconfig.json cotejo/web/tsconfig.node.json ./
COPY cotejo/web/vite.config.ts cotejo/web/index.html ./
COPY cotejo/web/public/ ./public/
COPY cotejo/web/src/ ./src/

RUN npm run build

# --------------------------------------------------------------------------- #

FROM nginx:1.27-alpine

COPY --from=construccion /repo/cotejo/web/dist /usr/share/nginx/html
COPY cotejo/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
