# Construcción del sitio estático de Rastro.
#
# Dos etapas: la primera compila con Node, la segunda solo sirve archivos. La
# imagen final no lleva Node ni node_modules, que es lo que corresponde a un
# sitio estático: en AWS estos mismos archivos se copian al almacenamiento de
# objetos y no hay servidor de aplicaciones en ninguna parte.

# El contexto de construcción es la raíz del repositorio y no `web/`, porque el
# sistema de diseño vive en `design/` y lo comparten las dos interfaces. La ruta
# dentro de la imagen reproduce la del repositorio para que los alias `@design`
# resuelvan igual aquí y en desarrollo.
FROM node:22-alpine AS construccion

WORKDIR /repo/web

# Las dependencias se instalan antes de copiar el código para que un cambio en
# una pantalla no invalide la capa de dependencias.
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY design/ /repo/design/
COPY web/tsconfig.json web/tsconfig.node.json web/vite.config.ts web/index.html ./
COPY web/public/ ./public/
COPY web/src/ ./src/

RUN npm run build

# --------------------------------------------------------------------------- #

FROM nginx:1.27-alpine

COPY --from=construccion /repo/web/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
