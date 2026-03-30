#!/bin/bash
set -e
echo "⚠️  You are about to deploy to PRODUCTION (whati8.app)"
echo ""
read -p "Are you sure? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi
cd "$(dirname "$0")/.."
echo "🚀 Deploying to PRODUCTION..."
fly deploy -c fly.toml
echo "✅ Production deployed: https://whati8.app/"
