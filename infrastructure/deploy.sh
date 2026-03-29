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

# Load .env if it exists
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from .env"
    set -a
    source "$ENV_FILE"
    set +a
fi

# Build env vars string for Cloud Run from known keys
ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_REGION=$REGION"
ENV_VARS="$ENV_VARS,EE_PROJECT=${EE_PROJECT:-dmjone}"
[ -n "${GOOGLE_MAPS_API_KEY:-}" ] && ENV_VARS="$ENV_VARS,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY"
[ -n "${GEMINI_API_KEY:-}" ] && ENV_VARS="$ENV_VARS,GEMINI_API_KEY=$GEMINI_API_KEY"
[ -n "${AGMARKNET_API_KEY:-}" ] && ENV_VARS="$ENV_VARS,AGMARKNET_API_KEY=$AGMARKNET_API_KEY"
[ -n "${TWILIO_ACCOUNT_SID:-}" ] && ENV_VARS="$ENV_VARS,TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID"
[ -n "${TWILIO_AUTH_TOKEN:-}" ] && ENV_VARS="$ENV_VARS,TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN"
[ -n "${TWILIO_PHONE_NUMBER:-}" ] && ENV_VARS="$ENV_VARS,TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER"
[ -n "${BASE_URL:-}" ] && ENV_VARS="$ENV_VARS,BASE_URL=$BASE_URL"

echo ""
echo "--- Building Docker image ---"
gcloud builds submit --tag "$IMAGE" --quiet --timeout=1200

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
    --min-instances 1 \
    --set-env-vars "$ENV_VARS" \
    --quiet

echo ""
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')

# Update BASE_URL for Twilio webhooks
gcloud run services update "$SERVICE_NAME" \
    --region "$REGION" \
    --update-env-vars "BASE_URL=$SERVICE_URL" \
    --quiet 2>/dev/null || true

echo "============================================"
echo " Deployed Successfully!"
echo " URL: $SERVICE_URL"
echo ""
echo " Dashboard:  $SERVICE_URL/"
echo " Voice Call: $SERVICE_URL/talk"
echo " Demo:       $SERVICE_URL/demo"
echo " API Health: $SERVICE_URL/api/health"
echo "============================================"
