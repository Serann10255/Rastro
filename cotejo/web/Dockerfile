# Interfaz del programa de auditoria. Dos etapas: compilar y servir.

FROM node:22-alpine AS construccion

WORKDIR /app

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
