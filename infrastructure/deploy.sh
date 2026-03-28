#!/bin/bash
# KisanMind — One-command deployment to Google Cloud Run
# Usage: ./infrastructure/deploy.sh

set -euo pipefail

echo "============================================"
echo " KisanMind — Deploy to Cloud Run"
echo "============================================"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-lmsforshantithakur}"
REGION="${GOOGLE_CLOUD_REGION:-asia-south1}"
SERVICE_NAME="kisanmind"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo ""
echo "--- Building Docker image ---"
gcloud builds submit --tag "$IMAGE" --quiet

echo ""
echo "--- Deploying to Cloud Run ---"
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_REGION=$REGION" \
    --quiet

echo ""
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')
echo "============================================"
echo " Deployed Successfully!"
echo " URL: $SERVICE_URL"
echo "============================================"
