#!/bin/bash
# KisanMind — One-command project setup
# Usage: ./infrastructure/setup.sh

set -euo pipefail

echo "============================================"
echo " KisanMind — Project Setup"
echo "============================================"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-lmsforshantithakur}"
REGION="${GOOGLE_CLOUD_REGION:-asia-south1}"
EE_PROJECT="${EE_PROJECT:-dmjone}"

# Check prerequisites
command -v gcloud >/dev/null 2>&1 || { echo "ERROR: gcloud CLI not installed. Install from https://cloud.google.com/sdk/docs/install"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not installed"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not installed"; exit 1; }

echo ""
echo "--- Step 1: GCloud Project Configuration ---"
gcloud config set project "$PROJECT_ID"
gcloud config set compute/region "$REGION"

echo ""
echo "--- Step 2: Enable Required APIs ---"
APIS=(
    "aiplatform.googleapis.com"
    "speech.googleapis.com"
    "texttospeech.googleapis.com"
    "translate.googleapis.com"
    "firestore.googleapis.com"
    "bigquery.googleapis.com"
    "storage.googleapis.com"
    "cloudfunctions.googleapis.com"
    "run.googleapis.com"
    "logging.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudscheduler.googleapis.com"
    "pubsub.googleapis.com"
    "geocoding-backend.googleapis.com"
    "distance-matrix-backend.googleapis.com"
    "earthengine.googleapis.com"
    "dialogflow.googleapis.com"
    "generativelanguage.googleapis.com"
)

for api in "${APIS[@]}"; do
    echo "  Enabling $api..."
    gcloud services enable "$api" --quiet || echo "  Warning: Could not enable $api"
done

echo ""
echo "--- Step 3: Python Environment ---"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created virtual environment"
fi
source venv/bin/activate
pip install -r requirements.txt --quiet
echo "  Python dependencies installed"

echo ""
echo "--- Step 4: Earth Engine Authentication ---"
echo "  Earth Engine project: $EE_PROJECT"
python3 -c "import ee; ee.Authenticate(); ee.Initialize(project='$EE_PROJECT')" 2>/dev/null || \
    echo "  Warning: Earth Engine auth failed. Run: earthengine authenticate"

echo ""
echo "--- Step 5: Frontend Setup ---"
cd frontend
npm install --quiet
echo "  Frontend dependencies installed"
cd ..

echo ""
echo "--- Step 6: Environment Variables ---"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Created .env from template — FILL IN YOUR API KEYS"
else
    echo "  .env already exists"
fi

echo ""
echo "--- Step 7: Create BigQuery Dataset ---"
bq mk --dataset --location="$REGION" "${PROJECT_ID}:kisanmind" 2>/dev/null || echo "  Dataset 'kisanmind' already exists"
bq mk --dataset --location="$REGION" "${PROJECT_ID}:kisanmind_reference" 2>/dev/null || echo "  Dataset 'kisanmind_reference' already exists"

echo ""
echo "============================================"
echo " Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Fill in API keys in .env"
echo "  2. Run the backend:  source venv/bin/activate && python -m agents.brain.orchestrator"
echo "  3. Run the frontend: cd frontend && npm run dev"
echo "  4. Open: http://localhost:3000"
echo ""
