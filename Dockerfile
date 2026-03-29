# KisanMind — Multi-stage Docker build
# Stage 1: Build the Next.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + compiled frontend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies + Node.js for Next.js runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
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

# Copy compiled frontend (standalone server + static assets + public)
COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public

# Copy entrypoint
COPY infrastructure/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Copy .env if it exists (for local Docker builds)
COPY .env* ./

# Environment
ENV PORT=8080
ENV HOSTNAME=0.0.0.0
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["./entrypoint.sh"]
