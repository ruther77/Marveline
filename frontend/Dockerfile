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
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
