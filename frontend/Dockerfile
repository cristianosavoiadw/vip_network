# VIP Network frontend: Vite build served by nginx, which also proxies /api (and the WebSocket)
# to the API container. The app calls the API by relative path, so one domain covers both.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# API_UPSTREAM is the compose service name and port of the backend
ENV API_UPSTREAM=api:3399
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=60s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
