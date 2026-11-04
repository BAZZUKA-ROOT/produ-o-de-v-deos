# contexto de build: raiz do repositório (fontes compartilhadas com o backend)
FROM node:22-alpine AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN rm -rf public/fonts && mkdir -p public/fonts
COPY backend/assets/fonts/ ./public/fonts/
ARG VITE_APP_NAME="Forja Studio"
ENV VITE_APP_NAME=$VITE_APP_NAME
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
