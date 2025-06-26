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

# Stop and remove existing container if running
echo -e "${YELLOW}🔄 Stopping existing container (if any)...${NC}"
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Build the Docker image
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
docker build -f Dockerfile.ec2 -t $IMAGE_NAME . --no-cache

# Start the container
echo -e "${YELLOW}🐳 Starting container...${NC}"

# Build docker run command with conditional AWS credentials mounting
DOCKER_CMD="docker run -d -p $PORT:$PORT -e OPENAI_API_KEY=\"$OPENAI_API_KEY\" -e AWS_REGION=\"us-east-1\""

# Add AWS credentials - prefer mounting ~/.aws directory, fallback to environment variables
if [ -f "$HOME/.aws/credentials" ] || [ -f "$HOME/.aws/config" ]; then
    echo -e "${BLUE}📁 Mounting ~/.aws directory for credentials${NC}"
    DOCKER_CMD="$DOCKER_CMD -v $HOME/.aws:/root/.aws:ro"
elif [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${BLUE}🔑 Using environment variables for AWS credentials${NC}"
    DOCKER_CMD="$DOCKER_CMD -e AWS_ACCESS_KEY_ID=\"$AWS_ACCESS_KEY_ID\" -e AWS_SECRET_ACCESS_KEY=\"$AWS_SECRET_ACCESS_KEY\""
fi

DOCKER_CMD="$DOCKER_CMD --name $CONTAINER_NAME $IMAGE_NAME"

# Execute the docker command
eval $DOCKER_CMD

# Wait for the container to start and initialize
echo -e "${YELLOW}⏳ Waiting for container to start and initialize...${NC}"
sleep 15

# Check if container is running
if docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${GREEN}✅ Container started successfully!${NC}"
    
    # Test health endpoint with retry
    echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
    HEALTH_CHECK_RETRIES=0
    MAX_RETRIES=10
    HEALTH_CHECK_PASSED=false
    
    while [ $HEALTH_CHECK_RETRIES -lt $MAX_RETRIES ]; do
        if curl -s http://localhost:$PORT/health >/dev/null 2>&1; then
            HEALTH_CHECK_PASSED=true
            break
        fi
        HEALTH_CHECK_RETRIES=$((HEALTH_CHECK_RETRIES + 1))
        echo -e "${YELLOW}   Attempt $HEALTH_CHECK_RETRIES/$MAX_RETRIES failed, retrying in 2 seconds...${NC}"
        sleep 2
    done
    
    if [ "$HEALTH_CHECK_PASSED" = true ]; then
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
        if [ "$AWS_CREDENTIALS_AVAILABLE" = true ]; then
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
        echo ""
        echo "🎭 Test avatar endpoints:"
        echo "   curl -X GET http://localhost:$PORT/personalization/avatar \\"
        echo "     -H \"Authorization: Bearer your-jwt-token\""
    else
        echo -e "${RED}❌ Health check failed after $MAX_RETRIES attempts. Check container logs:${NC}"
        echo "   docker logs $CONTAINER_NAME"
        echo ""
        echo "💡 Common issues:"
        echo "   - Database connection issues (check DB_PASSWORD)"
        echo "   - Port 8003 already in use"
        echo "   - Container taking longer to initialize"
    fi
else
    echo -e "${RED}❌ Container failed to start. Check logs:${NC}"
    docker logs $CONTAINER_NAME
    exit 1
fi