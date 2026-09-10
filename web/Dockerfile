# Construcción del sitio estático de Rastro.
#
# Dos etapas: la primera compila con Node, la segunda solo sirve archivos. La
# imagen final no lleva Node ni node_modules, que es lo que corresponde a un
# sitio estático: en AWS estos mismos archivos se copian al almacenamiento de
# objetos y no hay servidor de aplicaciones en ninguna parte.

FROM node:22-alpine AS construccion

WORKDIR /app

# Las dependencias se instalan antes de copiar el código para que un cambio en
# una pantalla no invalide la capa de dependencias.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY public/ ./public/
COPY src/ ./src/

RUN npm run build

# --------------------------------------------------------------------------- #

FROM nginx:1.27-alpine

COPY --from=construccion /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
