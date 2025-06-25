#!/bin/bash

# Local Development Script for My Story Buddy Backend
# This script builds and runs the backend Docker container for local testing

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="my-story-buddy-local"
IMAGE_NAME="my-story-buddy-backend:local"
PORT=8003

echo -e "${BLUE}🚀 My Story Buddy - Local Development Setup${NC}"
echo "=================================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY environment variable is not set.${NC}"
    echo "Please set it with: export OPENAI_API_KEY=\"your-api-key\""
    exit 1
fi

# Check for AWS credentials (needed for S3 image uploads)
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${YELLOW}⚠️  AWS credentials not set. Images will not be uploaded to S3.${NC}"
    echo "For full functionality, set these environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=\"your-access-key\""
    echo "  export AWS_SECRET_ACCESS_KEY=\"your-secret-key\""
    echo ""
    echo "Continuing without S3 functionality..."
    AWS_ACCESS_KEY_ID=""
    AWS_SECRET_ACCESS_KEY=""
fi

# Stop and remove existing container if running
echo -e "${YELLOW}🔄 Stopping existing container (if any)...${NC}"
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Build the Docker image
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
docker build -f Dockerfile.ec2 -t $IMAGE_NAME . --no-cache

# Start the container
echo -e "${YELLOW}🐳 Starting container...${NC}"
docker run -d \
    -p $PORT:$PORT \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -e AWS_REGION="us-east-1" \
    -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    --name $CONTAINER_NAME \
    $IMAGE_NAME

# Wait for the container to start and initialize
echo -e "${YELLOW}⏳ Waiting for container to start and initialize...${NC}"
sleep 8

# Check if container is running
if docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${GREEN}✅ Container started successfully!${NC}"
    
    # Test health endpoint
    echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
    if curl -s http://localhost:$PORT/health >/dev/null; then
        echo -e "${GREEN}✅ Health check passed!${NC}"
        echo ""
        echo -e "${GREEN}🎉 Backend is ready for development!${NC}"
        echo ""
        echo "📍 Available endpoints:"
        echo "   Health: http://localhost:$PORT/health"
        echo "   Ping:   http://localhost:$PORT/ping"
        echo "   Story:  http://localhost:$PORT/generateStory"
        echo ""
        echo "🔑 Environment status:"
        echo "   OpenAI API: ✅ Configured"
        if [ -n "$AWS_ACCESS_KEY_ID" ]; then
            echo "   AWS S3:     ✅ Configured (images will upload)"
        else
            echo "   AWS S3:     ⚠️  Not configured (placeholder images only)"
        fi
        echo ""
        echo "🔧 Useful commands:"
        echo "   View logs:    docker logs -f $CONTAINER_NAME"
        echo "   Stop server:  docker stop $CONTAINER_NAME"
        echo "   Restart:      ./dev-local.sh"
        echo ""
        echo "🧪 Test story generation:"
        echo "   curl -X POST http://localhost:$PORT/generateStory \\"
        echo "     -H \"Content-Type: application/json\" \\"
        echo "     -d '{\"prompt\": \"a friendly cat adventure\"}'"
    else
        echo -e "${RED}❌ Health check failed. Check container logs:${NC}"
        echo "   docker logs $CONTAINER_NAME"
    fi
else
    echo -e "${RED}❌ Container failed to start. Check logs:${NC}"
    docker logs $CONTAINER_NAME
    exit 1
fi