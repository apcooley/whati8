#!/bin/bash
set -e
echo "🚀 Deploying to STAGING..."
cd "$(dirname "$0")/.."
fly deploy -c fly.staging.toml
echo "✅ Staging deployed: https://whati8-staging.fly.dev/"
