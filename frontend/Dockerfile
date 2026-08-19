# Base stage
FROM node:20-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./

# Development stage
FROM base AS development
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Builder stage
FROM base AS builder
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
# Note: In production you would copy a custom nginx.conf here if needed for SPA routing
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
