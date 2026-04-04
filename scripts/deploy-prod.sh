#!/bin/bash
set -e

PROJECT="whati8-prod"
SERVICE="whati8"
REGION="us-west3"
GCLOUD="$HOME/google-cloud-sdk/bin/gcloud"

echo "⚠️  You are about to deploy to PRODUCTION (whati8.app)"
echo ""
read -p "Are you sure? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

cd "$(dirname "$0")/.."

echo "🚀 Deploying to PRODUCTION (Cloud Run)..."
$GCLOUD run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated

echo "✅ Production deployed: https://whati8.app/"
