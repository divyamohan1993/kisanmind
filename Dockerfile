# KisanMind — Multi-stage Docker build
# Stage 1: Build the Next.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + compiled frontend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY agents/ ./agents/
COPY cloud_functions/ ./cloud_functions/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Copy compiled frontend
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY --from=frontend-builder /app/frontend/package*.json ./frontend/
COPY --from=frontend-builder /app/frontend/node_modules ./frontend/node_modules

# Copy entrypoint
COPY infrastructure/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Copy .env if it exists (for local Docker builds)
COPY .env* ./

# Environment
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["./entrypoint.sh"]
