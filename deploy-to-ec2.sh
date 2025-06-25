#!/bin/bash

# Deploy My Story Buddy to EC2 with Docker
# Usage: ./deploy-to-ec2.sh [PUBLIC_IP]

set -e

# Configuration
REGION="us-east-1"
ECR_REPO="926211191776.dkr.ecr.us-east-1.amazonaws.com/my-story-buddy-backend"
APP_PORT="8003"
KEY_PAIR_NAME="my-story-buddy-key"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Deploying My Story Buddy to EC2${NC}"

# Get public IP from argument or config file
if [ -n "$1" ]; then
  PUBLIC_IP="$1"
elif [ -f "ec2-config.env" ]; then
  source ec2-config.env
else
  echo -e "${RED}❌ No public IP provided. Usage: ./deploy-to-ec2.sh [PUBLIC_IP]${NC}"
  echo -e "${YELLOW}💡 Or run ./setup-ec2-infrastructure.sh first${NC}"
  exit 1
fi

# Check prerequisites
if [ -z "$OPENAI_API_KEY" ]; then
  echo -e "${RED}❌ OPENAI_API_KEY environment variable not set${NC}"
  echo -e "${YELLOW}💡 Please run: export OPENAI_API_KEY='your-key-here'${NC}"
  exit 1
fi

if [ ! -f "${KEY_PAIR_NAME}.pem" ]; then
  echo -e "${RED}❌ SSH key ${KEY_PAIR_NAME}.pem not found${NC}"
  echo -e "${YELLOW}💡 Please run ./setup-ec2-infrastructure.sh first${NC}"
  exit 1
fi

echo "Deploying to: $PUBLIC_IP"

# Step 1: Build and push Docker image to ECR
echo -e "${YELLOW}📦 Building and pushing Docker image...${NC}"
docker build --platform linux/amd64 -t my-story-buddy-backend:latest .

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO

# Tag and push
docker tag my-story-buddy-backend:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

echo -e "${GREEN}✅ Image pushed to ECR${NC}"

# Step 2: Create deployment files
echo -e "${YELLOW}📝 Creating deployment files...${NC}"

# Create Docker Compose file
cat > docker-compose.yml << EOF
version: '3.8'

services:
  my-story-buddy:
    image: $ECR_REPO:latest
    container_name: my-story-buddy-app
    ports:
      - "80:8003"
      - "$APP_PORT:8003"
    environment:
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
      - AWS_REGION=$REGION
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
EOF

# Create environment file
cat > .env << EOF
OPENAI_API_KEY=$OPENAI_API_KEY
AWS_REGION=$REGION
EOF

# Create deployment script for EC2
cat > deploy-on-ec2.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting deployment on EC2..."

# Configure AWS credentials for ECR access
aws configure set region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 926211191776.dkr.ecr.us-east-1.amazonaws.com

# Pull latest image
docker-compose pull

# Stop existing container
docker-compose down

# Start new container
docker-compose up -d

# Wait for health check
echo "⏱️ Waiting for application to be healthy..."
sleep 30

# Test health endpoint
if curl -f http://localhost:8003/health > /dev/null 2>&1; then
  echo "✅ Application is healthy!"
  echo "🌐 Application is running at:"
  echo "  - http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8003"
  echo "  - http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
else
  echo "❌ Health check failed"
  echo "📋 Container logs:"
  docker-compose logs --tail=50
  exit 1
fi
EOF

chmod +x deploy-on-ec2.sh

# Create systemd service for auto-restart
cat > my-story-buddy.service << EOF
[Unit]
Description=My Story Buddy Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/my-story-buddy
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✅ Deployment files created${NC}"

# Step 3: Wait for EC2 to be ready
echo -e "${YELLOW}⏱️ Waiting for EC2 instance to be ready...${NC}"
for i in {1..60}; do
  if ssh -i ${KEY_PAIR_NAME}.pem -o StrictHostKeyChecking=no -o ConnectTimeout=5 ec2-user@$PUBLIC_IP "echo 'Ready'" 2>/dev/null; then
    echo -e "${GREEN}✅ EC2 instance is ready${NC}"
    break
  fi
  echo "Attempt $i/60: Waiting for SSH..."
  sleep 10
done

# Step 4: Copy files to EC2
echo -e "${YELLOW}📤 Copying files to EC2...${NC}"
scp -i ${KEY_PAIR_NAME}.pem -o StrictHostKeyChecking=no \
  docker-compose.yml .env deploy-on-ec2.sh my-story-buddy.service \
  ec2-user@$PUBLIC_IP:/tmp/

# Step 5: Deploy on EC2
echo -e "${YELLOW}🎯 Deploying on EC2...${NC}"
ssh -i ${KEY_PAIR_NAME}.pem -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP << 'ENDSSH'
# Move files to app directory
sudo mkdir -p /opt/my-story-buddy
sudo mv /tmp/docker-compose.yml /tmp/.env /tmp/deploy-on-ec2.sh /opt/my-story-buddy/
sudo chown -R ec2-user:ec2-user /opt/my-story-buddy
cd /opt/my-story-buddy

# Install systemd service
sudo mv /tmp/my-story-buddy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable my-story-buddy

# Run deployment
./deploy-on-ec2.sh

echo "🎉 Deployment completed!"
ENDSSH

# Step 6: Update frontend configuration
echo -e "${YELLOW}🔧 Updating frontend configuration...${NC}"
FRONTEND_DIR="../my-story-buddy-frontend"

if [ -d "$FRONTEND_DIR" ]; then
  echo "VITE_API_URL=http://$PUBLIC_IP" > "$FRONTEND_DIR/.env.production"
  echo -e "${GREEN}✅ Frontend configuration updated${NC}"
  
  if command -v npm &> /dev/null; then
    echo -e "${YELLOW}🏗️ Rebuilding frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build
    echo -e "${GREEN}✅ Frontend rebuilt with new API URL${NC}"
    cd - > /dev/null
  fi
else
  echo -e "${YELLOW}⚠️ Frontend directory not found${NC}"
fi

# Clean up local files
rm -f docker-compose.yml .env deploy-on-ec2.sh my-story-buddy.service

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${GREEN}📋 Deployment Summary:${NC}"
echo -e "${BLUE}  EC2 Public IP: $PUBLIC_IP${NC}"
echo -e "${BLUE}  Application URL: http://$PUBLIC_IP${NC}"
echo -e "${BLUE}  API URL: http://$PUBLIC_IP:8003${NC}"
echo -e "${BLUE}  SSH Access: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP${NC}"
echo ""
echo -e "${GREEN}🔗 Available Endpoints:${NC}"
echo -e "  Health Check: http://$PUBLIC_IP:8003/health"
echo -e "  Ping Test: http://$PUBLIC_IP:8003/ping"
echo -e "  Story Generation: http://$PUBLIC_IP:8003/generateStory"
echo -e "  Fun Facts: http://$PUBLIC_IP:8003/generateFunFacts"
echo ""
echo -e "${YELLOW}📝 Useful Commands:${NC}"
echo -e "  Check logs: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP 'cd /opt/my-story-buddy && docker-compose logs'"
echo -e "  Restart app: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP 'sudo systemctl restart my-story-buddy'"
echo -e "  Deploy update: ./deploy-to-ec2.sh $PUBLIC_IP"