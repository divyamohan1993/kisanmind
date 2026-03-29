#!/bin/bash
# KisanMind — VM Deployment Script
# Usage: ./infrastructure/deploy.sh

set -euo pipefail

echo "============================================"
echo " KisanMind — Build & Deploy (VM)"
echo "============================================"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from .env"
    set -a; source "$ENV_FILE"; set +a
fi

IMAGE_NAME="kisanmind"
BASE_URL="${BASE_URL:-https://kisanmind.dmj.one}"

echo ""
echo "--- Building Docker image ---"
docker build -t "$IMAGE_NAME" "$PROJECT_DIR"

echo ""
echo "--- Stopping existing container (if any) ---"
docker stop "$IMAGE_NAME" 2>/dev/null || true
docker rm "$IMAGE_NAME" 2>/dev/null || true

echo ""
echo "--- Starting container ---"
docker run -d \
    --name "$IMAGE_NAME" \
    --restart unless-stopped \
    --env-file "$ENV_FILE" \
    -e BASE_URL="$BASE_URL" \
    -p 8080:8080 \
    "$IMAGE_NAME"

echo ""
echo "============================================"
echo " Deployed Successfully!"
echo " URL: http://localhost:8080"
echo ""
echo " Voice Call: http://localhost:8080/talk"
echo " API Health: http://localhost:8080/api/health"
echo "============================================"
