# Multi-stage Dockerfile for Kaspa Solo Mining Console
# 1. Build frontend bundle
FROM node:24-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Build backend TypeScript
FROM node:24-alpine AS backend-build
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm ci
COPY backend/ ./
RUN npm run build

# 3. Production Runtime
FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=8080

# Install production dependencies only
COPY backend/package*.json ./
RUN npm ci --omit=dev

# Copy compiled backend
COPY --from=backend-build /app/backend/dist ./dist

# Copy compiled frontend static assets to serve
COPY --from=frontend-build /app/frontend/dist ./public

EXPOSE 8080
CMD ["node", "dist/server.js"]
