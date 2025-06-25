#!/bin/bash

# Complete My Story Buddy Deployment Script
# Deploys backend to AWS Lambda and updates frontend configuration

set -e  # Exit on any error

# Configuration
REGION="us-east-1"
REPO_NAME="my-story-buddy-backend"
FUNCTION_NAME="my-story-buddy-backend"
IMAGE_TAG="latest"
ROLE_NAME="my-story-buddy-lambda-role"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 My Story Buddy - Full Stack Deployment${NC}"

# Check prerequisites
if [ -z "$OPENAI_API_KEY" ]; then
  echo -e "${RED}❌ OPENAI_API_KEY environment variable not set${NC}"
  echo -e "${YELLOW}💡 Please run: export OPENAI_API_KEY='your-key-here'${NC}"
  exit 1
fi

if ! command -v aws &> /dev/null; then
  echo -e "${RED}❌ AWS CLI not found${NC}"
  echo -e "${YELLOW}💡 Please install AWS CLI and configure credentials${NC}"
  exit 1
fi

if ! command -v docker &> /dev/null; then
  echo -e "${RED}❌ Docker not found${NC}"
  echo -e "${YELLOW}💡 Please install Docker${NC}"
  exit 1
fi

# Step 1: Build Docker image
echo -e "${YELLOW}📦 Building Docker image for Lambda (linux/amd64)...${NC}"
docker build --platform linux/amd64 -t $REPO_NAME:$IMAGE_TAG .

# Step 2: Get AWS account info
echo -e "${YELLOW}🔍 Getting AWS account ID...${NC}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "Account ID: $ACCOUNT_ID"
echo "ECR URI: $ECR_URI"

# Step 3: Create ECR repository
echo -e "${YELLOW}🏗️ Creating ECR repository...${NC}"
aws ecr create-repository --repository-name $REPO_NAME --region $REGION 2>/dev/null || echo "Repository already exists"

# Step 4: Login to ECR and push image
echo -e "${YELLOW}🔑 Logging into ECR...${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

echo -e "${YELLOW}🏷️ Tagging and pushing image...${NC}"
docker tag $REPO_NAME:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker push $ECR_URI:$IMAGE_TAG

# Step 5: Create IAM role for Lambda (if it doesn't exist)
echo -e "${YELLOW}👤 Setting up IAM role...${NC}"
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME 2>/dev/null >/dev/null; then
  echo "IAM role already exists"
else
  echo "Creating IAM role..."
  aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document "$TRUST_POLICY" >/dev/null

  # Attach basic Lambda execution policy
  aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

  # Attach S3 access for image storage
  aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

  echo "Waiting for IAM role to propagate..."
  sleep 10
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Step 6: Create or update Lambda function
echo -e "${YELLOW}⚡ Deploying Lambda function...${NC}"
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>/dev/null >/dev/null; then
  echo "Updating existing Lambda function..."
  aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $ECR_URI:$IMAGE_TAG \
    --region $REGION >/dev/null
    
  # Update environment variables
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment Variables="{OPENAI_API_KEY=${OPENAI_API_KEY}}" \
    --region $REGION >/dev/null
else
  echo "Creating new Lambda function..."
  aws lambda create-function \
    --function-name $FUNCTION_NAME \
    --package-type Image \
    --code ImageUri=$ECR_URI:$IMAGE_TAG \
    --role $ROLE_ARN \
    --timeout 300 \
    --memory-size 1024 \
    --environment Variables="{OPENAI_API_KEY=${OPENAI_API_KEY}}" \
    --region $REGION >/dev/null
fi

# Step 7: Wait for function to be ready
echo -e "${YELLOW}⏱️ Waiting for Lambda function to be ready...${NC}"
aws lambda wait function-active --function-name $FUNCTION_NAME --region $REGION

# Step 8: Create Function URL (if it doesn't exist)
echo -e "${YELLOW}🌐 Setting up Function URL...${NC}"
LAMBDA_URL=$(aws lambda get-function-url-config --function-name $FUNCTION_NAME --region $REGION --query FunctionUrl --output text 2>/dev/null || echo "")

if [ -z "$LAMBDA_URL" ]; then
  echo "Creating Function URL..."
  aws lambda create-function-url-config \
    --function-name $FUNCTION_NAME \
    --cors "AllowCredentials=false,AllowMethods=*,AllowOrigins=*,AllowHeaders=*,MaxAge=86400" \
    --auth-type NONE \
    --region $REGION >/dev/null
  
  LAMBDA_URL=$(aws lambda get-function-url-config --function-name $FUNCTION_NAME --region $REGION --query FunctionUrl --output text)
fi

# Step 9: Update frontend configuration
echo -e "${YELLOW}🔧 Updating frontend configuration...${NC}"
FRONTEND_DIR="../my-story-buddy-frontend"

if [ -d "$FRONTEND_DIR" ]; then
  echo "Updating frontend .env.production..."
  echo "VITE_API_URL=$LAMBDA_URL" > "$FRONTEND_DIR/.env.production"
  echo -e "${GREEN}✅ Frontend .env.production updated!${NC}"
  
  if command -v npm &> /dev/null; then
    echo -e "${YELLOW}🏗️ Rebuilding frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build
    echo -e "${GREEN}✅ Frontend rebuilt with new API URL!${NC}"
    cd - > /dev/null
  else
    echo -e "${YELLOW}⚠️ npm not found. Please rebuild frontend manually${NC}"
  fi
else
  echo -e "${YELLOW}⚠️ Frontend directory not found at: $FRONTEND_DIR${NC}"
fi

# Step 10: Test deployment
echo -e "${YELLOW}🧪 Testing deployment...${NC}"

echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "${LAMBDA_URL}health" 2>/dev/null || echo "Failed")
if echo "$HEALTH_RESPONSE" | grep -q "healthy" 2>/dev/null; then
  echo -e "${GREEN}✅ Health check passed${NC}"
else
  echo -e "${YELLOW}⚠️ Health check response: $HEALTH_RESPONSE${NC}"
fi

echo "Testing ping endpoint..."
PING_RESPONSE=$(curl -s "${LAMBDA_URL}ping" 2>/dev/null || echo "Failed")
if echo "$PING_RESPONSE" | grep -q "pong" 2>/dev/null; then
  echo -e "${GREEN}✅ Ping test passed${NC}"
else
  echo -e "${YELLOW}⚠️ Ping response: $PING_RESPONSE${NC}"
fi

# Final success message
echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${GREEN}📋 Deployment Summary:${NC}"
echo -e "${BLUE}  Backend Function: $FUNCTION_NAME${NC}"
echo -e "${BLUE}  Region: $REGION${NC}"
echo -e "${BLUE}  Lambda URL: $LAMBDA_URL${NC}"
echo -e "${BLUE}  Docker Image: $ECR_URI:$IMAGE_TAG${NC}"
echo ""
echo -e "${GREEN}🔗 Available Endpoints:${NC}"
echo -e "  Health Check: ${LAMBDA_URL}health"
echo -e "  Ping Test: ${LAMBDA_URL}ping"
echo -e "  Story Generation: ${LAMBDA_URL}generateStory"
echo -e "  Fun Facts: ${LAMBDA_URL}generateFunFacts"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo -e "  1. Test story generation:"
echo -e "     curl -X POST ${LAMBDA_URL}generateStory \\"
echo -e "          -H 'Content-Type: application/json' \\"
echo -e "          -d '{\"prompt\":\"a friendly cat adventure\"}'"
echo ""
echo -e "  2. Deploy frontend to S3/CloudFront:"
echo -e "     cd ../my-story-buddy-frontend && npm run deploy"
echo ""
echo -e "  3. Monitor logs:"
echo -e "     aws logs tail /aws/lambda/$FUNCTION_NAME --follow"