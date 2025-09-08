#!/bin/bash

# Deployment script for Mounir Cutzz AI Receptionist
# Usage: ./deploy.sh [platform]
# Platforms: render, railway, docker, heroku

set -e

PLATFORM=${1:-render}
APP_NAME="mounir-cutzz-ai-receptionist"

echo "🚀 Deploying $APP_NAME to $PLATFORM..."

# Check if required environment variables are set
check_env_vars() {
    local required_vars=(
        "TWILIO_ACCOUNT_SID"
        "TWILIO_AUTH_TOKEN" 
        "OPENAI_API_KEY"
        "GOOGLE_CALENDAR_ID"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            echo "❌ Error: $var environment variable is not set"
            echo "Please set all required environment variables before deploying"
            exit 1
        fi
    done
    
    echo "✅ All required environment variables are set"
}

# Deploy to Render
deploy_render() {
    echo "📦 Deploying to Render..."
    
    if ! command -v render &> /dev/null; then
        echo "Installing Render CLI..."
        npm install -g @render/cli
    fi
    
    # Deploy using render.yaml
    render deploy
    
    echo "✅ Deployed to Render successfully!"
    echo "🔗 Your app will be available at: https://$APP_NAME.onrender.com"
}

# Deploy to Railway
deploy_railway() {
    echo "🚂 Deploying to Railway..."
    
    if ! command -v railway &> /dev/null; then
        echo "Installing Railway CLI..."
        npm install -g @railway/cli
    fi
    
    # Login and deploy
    railway login
    railway link
    railway up
    
    echo "✅ Deployed to Railway successfully!"
}

# Deploy with Docker
deploy_docker() {
    echo "🐳 Building and running Docker container..."
    
    # Build production image
    docker build -f Dockerfile.prod -t $APP_NAME:latest .
    
    # Run container
    docker run -d \
        --name $APP_NAME \
        --env-file .env \
        -p 8000:8000 \
        $APP_NAME:latest
    
    echo "✅ Docker container is running!"
    echo "🔗 Your app is available at: http://localhost:8000"
}

# Deploy to Heroku
deploy_heroku() {
    echo "🟣 Deploying to Heroku..."
    
    if ! command -v heroku &> /dev/null; then
        echo "Please install Heroku CLI first"
        exit 1
    fi
    
    # Create Heroku app if it doesn't exist
    heroku apps:info $APP_NAME || heroku create $APP_NAME
    
    # Add Redis addon
    heroku addons:create heroku-redis:mini -a $APP_NAME
    
    # Set environment variables
    heroku config:set \
        TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
        TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
        OPENAI_API_KEY="$OPENAI_API_KEY" \
        GOOGLE_CALENDAR_ID="$GOOGLE_CALENDAR_ID" \
        GOOGLE_CREDENTIALS_JSON="$GOOGLE_CREDENTIALS_JSON" \
        AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
        AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
        AWS_REGION="us-east-1" \
        BARBER_SHOP_NAME="Mounir Cutzz" \
        BARBER_SHOP_TIMEZONE="Asia/Beirut" \
        -a $APP_NAME
    
    # Deploy
    git push heroku main
    
    echo "✅ Deployed to Heroku successfully!"
    echo "🔗 Your app is available at: https://$APP_NAME.herokuapp.com"
}

# Main deployment logic
case $PLATFORM in
    render)
        check_env_vars
        deploy_render
        ;;
    railway)
        check_env_vars
        deploy_railway
        ;;
    docker)
        deploy_docker
        ;;
    heroku)
        check_env_vars
        deploy_heroku
        ;;
    *)
        echo "❌ Unknown platform: $PLATFORM"
        echo "Supported platforms: render, railway, docker, heroku"
        exit 1
        ;;
esac

echo ""
echo "🎉 Deployment completed!"
echo ""
echo "📋 Next steps:"
echo "1. Configure your Twilio webhook URL to point to your deployed app"
echo "2. Test the phone number to ensure everything works"
echo "3. Monitor logs for any issues"
echo ""
echo "📞 Webhook URL: https://your-domain.com/webhook/voice"
echo "📊 Health check: https://your-domain.com/"
