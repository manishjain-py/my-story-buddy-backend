#!/bin/bash

# Local Development Script using Docker Compose
# Alternative to dev-local.sh that uses docker-compose

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 My Story Buddy - Docker Compose Local Development${NC}"
echo "=================================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "${RED}❌ docker-compose is not installed. Please install it and try again.${NC}"
    exit 1
fi

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY environment variable is not set.${NC}"
    echo "Please set it with: export OPENAI_API_KEY=\"your-api-key\""
    exit 1
fi

# Check for AWS credentials
AWS_CREDENTIALS_AVAILABLE=false
if [ -f "$HOME/.aws/credentials" ] || [ -f "$HOME/.aws/config" ]; then
    echo -e "${GREEN}✅ AWS credentials found in ~/.aws/ directory${NC}"
    AWS_CREDENTIALS_AVAILABLE=true
elif [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${GREEN}✅ AWS credentials found in environment variables${NC}"
    AWS_CREDENTIALS_AVAILABLE=true
else
    echo -e "${YELLOW}⚠️  AWS credentials not found. Images will not be uploaded to S3.${NC}"
    echo "For full functionality, either:"
    echo "  1. Configure AWS CLI: aws configure"
    echo "  2. Or set environment variables:"
    echo "     export AWS_ACCESS_KEY_ID=\"your-access-key\""
    echo "     export AWS_SECRET_ACCESS_KEY=\"your-secret-key\""
    echo ""
    echo "Continuing without S3 functionality..."
fi

# Action parameter (default: up)
ACTION=${1:-up}

case $ACTION in
    "up"|"start")
        echo -e "${YELLOW}🐳 Starting services with Docker Compose...${NC}"
        docker-compose -f docker-compose.local.yml up -d --build
        echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
        sleep 10
        
        # Test health endpoint
        echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
        if curl -s http://localhost:8003/health >/dev/null; then
            echo -e "${GREEN}✅ Health check passed!${NC}"
            echo ""
            echo -e "${GREEN}🎉 Backend is ready for development!${NC}"
            echo ""
            echo "📍 Available endpoints:"
            echo "   Health: http://localhost:8003/health"
            echo "   Ping:   http://localhost:8003/ping"
            echo "   Story:  http://localhost:8003/generateStory"
            echo ""
            echo "🔑 Environment status:"
            echo "   OpenAI API: ✅ Configured"
            if [ "$AWS_CREDENTIALS_AVAILABLE" = true ]; then
                echo "   AWS S3:     ✅ Configured (images will upload)"
            else
                echo "   AWS S3:     ⚠️  Not configured (placeholder images only)"
            fi
        else
            echo -e "${RED}❌ Health check failed. Check container logs:${NC}"
            echo "   docker-compose -f docker-compose.local.yml logs"
        fi
        ;;
    "stop"|"down")
        echo -e "${YELLOW}🛑 Stopping services...${NC}"
        docker-compose -f docker-compose.local.yml down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    "logs")
        echo -e "${BLUE}📋 Showing logs...${NC}"
        docker-compose -f docker-compose.local.yml logs -f
        ;;
    "restart")
        echo -e "${YELLOW}🔄 Restarting services...${NC}"
        docker-compose -f docker-compose.local.yml restart
        ;;
    "rebuild")
        echo -e "${YELLOW}🔨 Rebuilding and restarting services...${NC}"
        docker-compose -f docker-compose.local.yml down
        docker-compose -f docker-compose.local.yml up -d --build
        ;;
    *)
        echo -e "${BLUE}Usage: $0 [action]${NC}"
        echo ""
        echo "Available actions:"
        echo "  up|start   - Start the development environment (default)"
        echo "  stop|down  - Stop the development environment"
        echo "  logs       - Show container logs"
        echo "  restart    - Restart services"
        echo "  rebuild    - Rebuild and restart services"
        echo ""
        echo "Examples:"
        echo "  $0           # Start development environment"
        echo "  $0 up        # Start development environment"
        echo "  $0 logs      # Show logs"
        echo "  $0 stop      # Stop environment"
        ;;
esac