# Production Dockerfile for Kaspa Solo Mining Console
FROM node:20-alpine

WORKDIR /app
ENV NODE_ENV=production PORT=8080

# Install production dependencies only
COPY web/package*.json ./
RUN npm install --omit=dev

# Copy application source and static frontend assets
COPY web/ ./

EXPOSE 8080
CMD ["node", "server.js"]
