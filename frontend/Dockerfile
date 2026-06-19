FROM node:20-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_MAX_SCORE_MB=250
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_MAX_SCORE_MB=$VITE_MAX_SCORE_MB

RUN npm run build

FROM caddy:2-alpine

COPY --from=build /app/frontend/dist /srv
COPY docker/Caddyfile /etc/caddy/Caddyfile
