FROM node:22-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./

RUN npm ci

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

RUN npm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK \
    --interval=10s \
    --timeout=3s \
    --start-period=5s \
    --retries=5 \
    CMD wget -q -O - http://127.0.0.1:8080/healthz >/dev/null || exit 1
