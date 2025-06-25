# My Story Buddy - EC2 Deployment Guide

## 📋 Overview

This guide covers deploying My Story Buddy to AWS EC2 using Docker containers. The setup provides a reliable, scalable alternative to AWS Lambda with full Docker compatibility.

## 🏗️ Architecture

- **Backend**: FastAPI application running in Docker on EC2
- **Container Registry**: AWS ECR for Docker images
- **Infrastructure**: EC2 instance with Docker and systemd auto-restart
- **Frontend**: React application with environment-based API URL configuration
- **Deployment**: Automated via shell scripts and optional GitHub Actions

---

## 🚀 Fresh Deployment (From Scratch)

### Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Docker installed** and running locally
3. **OpenAI API Key** for story generation
4. **Node.js/npm** for frontend builds

### Step 1: Set Environment Variables

```bash
# Required: Set your OpenAI API key
export OPENAI_API_KEY="your-openai-api-key-here"

# Verify AWS credentials are configured
aws sts get-caller-identity
```

### Step 2: Create Infrastructure

```bash
cd my-story-buddy-backend

# Create EC2 instance, security groups, and SSH keys
./setup-ec2-infrastructure.sh
```

**This script creates:**
- EC2 instance (t3.medium, Amazon Linux 2)
- Security groups (ports 22, 80, 443, 8003)
- SSH key pair (`my-story-buddy-key.pem`)
- Saves configuration to `ec2-config.env`

### Step 3: Deploy Application

```bash
# Wait 2-3 minutes for EC2 instance to fully initialize, then:
./deploy-to-ec2.sh

# Or if you have the public IP:
./deploy-to-ec2.sh <PUBLIC_IP>
```

**This script:**
- Builds EC2-specific Docker image
- Pushes to ECR
- Deploys to EC2 via SSH
- Sets up Docker Compose with auto-restart
- Updates frontend configuration
- Rebuilds frontend with new API URL

### Step 4: Verify Deployment

```bash
# Test endpoints (replace with your EC2 IP)
curl http://<EC2_PUBLIC_IP>/health
curl http://<EC2_PUBLIC_IP>/ping

# Test story generation
curl -X POST http://<EC2_PUBLIC_IP>/generateStory \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a friendly cat adventure"}'
```

### Step 5: Deploy Frontend

```bash
cd ../my-story-buddy-frontend

# Frontend is already built with new API URL
# Deploy to S3/CloudFront using existing process
npm run deploy  # or your existing deployment command
```

---

## 🔄 Updating Existing Deployment

### Quick Code Updates

```bash
cd my-story-buddy-backend

# Deploy code changes
./deploy-to-ec2.sh

# This will:
# - Build new Docker image
# - Push to ECR  
# - Update running container
# - Restart application
```

### Manual Updates via SSH

```bash
# SSH into the server
ssh -i my-story-buddy-key.pem ec2-user@<EC2_PUBLIC_IP>

# Navigate to app directory
cd /opt/my-story-buddy

# Pull latest image and restart
docker-compose pull
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Frontend Updates

```bash
cd my-story-buddy-frontend

# If API URL changed, update and rebuild
echo "VITE_API_URL=http://<NEW_EC2_IP>" > .env.production
npm run build

# Deploy to S3/CloudFront
npm run deploy
```

---

## 🤖 GitHub Actions Automation

### Setup GitHub Secrets

Add these secrets to your GitHub repository (`Settings > Secrets and variables > Actions`):

```
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
EC2_HOST=204.236.220.17  # Your EC2 public IP
EC2_SSH_KEY=contents-of-my-story-buddy-key.pem-file
OPENAI_API_KEY=your-openai-api-key
```

### Automatic Deployment

The GitHub Actions workflow (`.github/workflows/deploy-ec2.yml`) will:
- Trigger on push to `main` branch
- Build and push Docker image to ECR
- SSH into EC2 and update the application
- Verify deployment with health checks

---

## 🛠️ Management Commands

### Application Management

```bash
# Check application status
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && docker-compose ps'

# View application logs
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && docker-compose logs --tail=50'

# Restart application
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && docker-compose restart'

# Update environment variables
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && nano .env'
# Then restart: docker-compose restart
```

### System Management

```bash
# Check systemd service status
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'sudo systemctl status my-story-buddy'

# Restart via systemd
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'sudo systemctl restart my-story-buddy'

# View system logs
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'sudo journalctl -u my-story-buddy -f'
```

### Docker Management

```bash
# Clean up old images
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'docker image prune -f'

# View Docker resource usage
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'docker stats --no-stream'

# Rebuild from scratch (if needed)
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && docker-compose down && docker system prune -f && docker-compose up -d'
```

---

## 📁 File Structure

```
my-story-buddy-backend/
├── deploy-to-ec2.sh              # Main deployment script
├── setup-ec2-infrastructure.sh   # Infrastructure creation
├── Dockerfile.ec2                # EC2-specific Dockerfile
├── docker-compose.production.yml # Production Docker Compose
├── .env.production               # Environment variables template
├── .github/workflows/deploy-ec2.yml # GitHub Actions workflow
├── ec2-config.env                # Generated EC2 configuration
├── my-story-buddy-key.pem        # Generated SSH key
└── DEPLOYMENT-GUIDE.md           # This file
```

---

## 🔍 Troubleshooting

### Application Not Starting

```bash
# Check container logs
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && docker-compose logs'

# Check if ports are open
nmap -p 80,8003 <EC2_IP>

# Verify environment variables
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> 'cd /opt/my-story-buddy && cat .env'
```

### ECR Authentication Issues

```bash
# Re-configure AWS credentials on EC2
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> '
  aws configure set aws_access_key_id YOUR_ACCESS_KEY
  aws configure set aws_secret_access_key YOUR_SECRET_KEY
  aws configure set region us-east-1
'

# Re-login to ECR
ssh -i my-story-buddy-key.pem ec2-user@<EC2_IP> '
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 926211191776.dkr.ecr.us-east-1.amazonaws.com
'
```

### Frontend API Connection Issues

```bash
# Verify frontend is using correct API URL
cat ../my-story-buddy-frontend/.env.production

# Test API connectivity from frontend
curl -s http://<EC2_IP>/health

# Rebuild frontend with correct URL
cd ../my-story-buddy-frontend
echo "VITE_API_URL=http://<EC2_IP>" > .env.production
npm run build
```

---

## 💰 Cost Optimization

### Instance Sizing
- **t3.micro**: Development/testing (1 vCPU, 1GB RAM) - Free tier eligible
- **t3.small**: Light production (2 vCPU, 2GB RAM) - ~$15/month
- **t3.medium**: Current setup (2 vCPU, 4GB RAM) - ~$30/month
- **t3.large**: High traffic (2 vCPU, 8GB RAM) - ~$60/month

### Cost Monitoring
```bash
# Monitor instance costs
aws ce get-cost-and-usage --time-period Start=2025-06-01,End=2025-06-30 --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE

# Set up billing alerts in AWS Console
# Navigate to: AWS Console > Billing > Billing preferences > Alert preferences
```

---

## 🔐 Security Best Practices

### SSH Key Management
```bash
# Rotate SSH keys periodically
aws ec2 create-key-pair --key-name my-story-buddy-key-new --query 'KeyMaterial' --output text > my-story-buddy-key-new.pem
chmod 400 my-story-buddy-key-new.pem

# Update EC2 instance with new key (requires temporary access)
```

### Environment Variables
```bash
# Encrypt sensitive environment variables
# Use AWS Systems Manager Parameter Store for production:
aws ssm put-parameter --name "/mystorybuddy/openai-api-key" --value "your-key" --type "SecureString"
```

### Firewall Rules
```bash
# Restrict SSH access to your IP only
aws ec2 authorize-security-group-ingress --group-id sg-xxx --protocol tcp --port 22 --cidr YOUR.IP.ADDRESS/32
aws ec2 revoke-security-group-ingress --group-id sg-xxx --protocol tcp --port 22 --cidr 0.0.0.0/0
```

---

## 📞 Support

### Current Deployment Info
- **EC2 Instance**: `i-068f140bc18b8a8b6`
- **Public IP**: `204.236.220.17`
- **Region**: `us-east-1`
- **ECR Repository**: `926211191776.dkr.ecr.us-east-1.amazonaws.com/my-story-buddy-backend`

### Useful Commands Quick Reference
```bash
# Quick status check
curl http://204.236.220.17/health

# Quick restart
ssh -i my-story-buddy-key.pem ec2-user@204.236.220.17 'cd /opt/my-story-buddy && docker-compose restart'

# Quick logs
ssh -i my-story-buddy-key.pem ec2-user@204.236.220.17 'cd /opt/my-story-buddy && docker-compose logs --tail=20'

# Quick deployment
./deploy-to-ec2.sh 204.236.220.17
```

---

**Last Updated**: June 25, 2025  
**Deployment Version**: EC2 Docker v1.0