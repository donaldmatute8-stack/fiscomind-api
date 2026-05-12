# FiscoMind Railway Deploy Script
# Run: ./deploy.sh after setting RAILWAY_TOKEN

#!/bin/bash
set -e

echo "🚂 FiscoMind Railway Deployment"
echo "================================"

# Check for token
if [ -z "$RAILWAY_TOKEN" ]; then
    echo "❌ Error: RAILWAY_TOKEN not set"
    echo "Set it with: export RAILWAY_TOKEN='your-token-here'"
    exit 1
fi

echo "✅ Token found"

# Link to project (if not already)
railway link || echo "Already linked or creating new..."

# Set environment variables
echo "📋 Setting environment variables..."
railway variables set VAULT_MASTER_KEY="$(openssl rand -hex 32)"
railway variables set API_VERSION="3.0.0"

# Deploy
echo "🚀 Deploying to Railway..."
railway up

echo "✅ Deploy complete!"
echo ""
echo "Check status with: railway status"
echo "View logs with: railway logs"
echo "Open with: railway open"