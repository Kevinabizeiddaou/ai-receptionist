#!/bin/bash

# Setup script for Mounir Cutzz AI Receptionist
# This script helps configure the environment and dependencies

set -e

echo "🏪 Setting up Mounir Cutzz AI Receptionist..."

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python version: $python_version"
}

# Install dependencies
install_dependencies() {
    echo "📦 Installing Python dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        pip3 install -r requirements.txt
        echo "✅ Dependencies installed successfully"
    else
        echo "❌ requirements.txt not found"
        exit 1
    fi
}

# Setup environment variables
setup_environment() {
    echo "🔧 Setting up environment variables..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            echo "📝 Created .env file from .env.example"
            echo "⚠️  Please edit .env file with your actual credentials"
        else
            echo "❌ .env.example not found"
            exit 1
        fi
    else
        echo "✅ .env file already exists"
    fi
}

# Setup Redis (for local development)
setup_redis() {
    echo "🔴 Setting up Redis..."
    
    if command -v redis-server &> /dev/null; then
        echo "✅ Redis is already installed"
        
        # Start Redis if not running
        if ! pgrep redis-server > /dev/null; then
            echo "🚀 Starting Redis server..."
            redis-server --daemonize yes
        else
            echo "✅ Redis server is already running"
        fi
    else
        echo "⚠️  Redis is not installed. Installing via package manager..."
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if command -v brew &> /dev/null; then
                brew install redis
                brew services start redis
            else
                echo "❌ Homebrew not found. Please install Redis manually."
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y redis-server
                sudo systemctl start redis-server
                sudo systemctl enable redis-server
            elif command -v yum &> /dev/null; then
                sudo yum install -y redis
                sudo systemctl start redis
                sudo systemctl enable redis
            else
                echo "❌ Package manager not supported. Please install Redis manually."
            fi
        else
            echo "❌ OS not supported. Please install Redis manually."
        fi
    fi
}

# Test configuration
test_configuration() {
    echo "🧪 Testing configuration..."
    
    # Test Redis connection
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis connection successful"
    else
        echo "❌ Redis connection failed"
    fi
    
    # Test Python imports
    python3 -c "
import sys
try:
    import fastapi, twilio, openai, redis, boto3
    print('✅ All Python packages imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
}

# Create systemd service (Linux only)
create_service() {
    if [[ "$OSTYPE" == "linux-gnu"* ]] && [[ "$1" == "--service" ]]; then
        echo "🔧 Creating systemd service..."
        
        SERVICE_FILE="/etc/systemd/system/mounir-cutzz-receptionist.service"
        CURRENT_DIR=$(pwd)
        
        sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Mounir Cutzz AI Receptionist
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment=PATH=$CURRENT_DIR/venv/bin
ExecStart=$CURRENT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable mounir-cutzz-receptionist
        
        echo "✅ Systemd service created. Start with: sudo systemctl start mounir-cutzz-receptionist"
    fi
}

# Main setup
main() {
    check_python
    install_dependencies
    setup_environment
    setup_redis
    test_configuration
    create_service "$1"
    
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Edit .env file with your API credentials"
    echo "2. Run: python3 main.py (or uvicorn main:app --reload)"
    echo "3. Configure Twilio webhook to point to your server"
    echo ""
    echo "🔗 Local server will run at: http://localhost:8000"
    echo "📞 Webhook endpoint: http://your-domain.com/webhook/voice"
}

# Run main function with arguments
main "$@"
