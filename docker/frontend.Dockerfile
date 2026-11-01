# Website image (Prompt 39): the React build served by nginx, which also forwards /api/* to the backend container,
# so the browser talks to ONE address (no CORS, the sign-in cookie stays first-party).
# Built by docker-compose.yml from the project root:  docker compose build
ARG NODE_IMAGE=node:22-bookworm-slim
ARG NGINX_IMAGE=nginx:1.27-alpine

FROM ${NODE_IMAGE} AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# the API address the website calls: the same site, under /api (see docker/nginx.conf)
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM ${NGINX_IMAGE}
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
