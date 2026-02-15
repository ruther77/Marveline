FROM node:20-alpine AS builder
WORKDIR /app

# Installation dépendances
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production
FROM nginx:alpine

# Non-root user (fix I5)
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup && \
    chown -R appuser:appgroup /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && chown appuser:appgroup /var/run/nginx.pid

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R appuser:appgroup /usr/share/nginx/html

USER appuser
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
