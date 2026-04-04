#!/bin/bash
set -e

PROJECT="whati8-prod"
SERVICE="whati8-staging"
REGION="us-west3"
GCLOUD="$HOME/google-cloud-sdk/bin/gcloud"

echo "🚀 Deploying to STAGING (Cloud Run)..."
cd "$(dirname "$0")/.."

$GCLOUD run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated

echo "✅ Staging deployed: https://whati8-staging-309983882304.us-west3.run.app/"
