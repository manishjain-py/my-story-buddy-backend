#!/bin/bash

# EC2 Infrastructure Setup for My Story Buddy
# Creates EC2 instance, security group, and key pair

set -e

# Configuration
REGION="us-east-1"
INSTANCE_NAME="my-story-buddy-server"
KEY_PAIR_NAME="my-story-buddy-key"
SECURITY_GROUP_NAME="my-story-buddy-sg"
INSTANCE_TYPE="t3.medium"  # 2 vCPU, 4GB RAM - good for Docker apps
VOLUME_SIZE="20"           # GB

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🏗️ Setting up EC2 Infrastructure for My Story Buddy${NC}"

# Check prerequisites
if ! command -v aws &> /dev/null; then
  echo -e "${RED}❌ AWS CLI not found${NC}"
  exit 1
fi

# Get latest Amazon Linux 2 AMI
echo -e "${YELLOW}🔍 Finding latest Amazon Linux 2 AMI...${NC}"
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region $REGION)

echo "Using AMI: $AMI_ID"

# Create key pair if it doesn't exist
echo -e "${YELLOW}🔑 Creating SSH key pair...${NC}"
if aws ec2 describe-key-pairs --key-names $KEY_PAIR_NAME --region $REGION 2>/dev/null; then
  echo "Key pair already exists"
else
  aws ec2 create-key-pair \
    --key-name $KEY_PAIR_NAME \
    --query 'KeyMaterial' \
    --output text \
    --region $REGION > ${KEY_PAIR_NAME}.pem
  
  chmod 400 ${KEY_PAIR_NAME}.pem
  echo -e "${GREEN}✅ Key pair created: ${KEY_PAIR_NAME}.pem${NC}"
fi

# Create security group
echo -e "${YELLOW}🔒 Creating security group...${NC}"
if aws ec2 describe-security-groups --group-names $SECURITY_GROUP_NAME --region $REGION 2>/dev/null; then
  echo "Security group already exists"
  SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
    --group-names $SECURITY_GROUP_NAME \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $REGION)
else
  SECURITY_GROUP_ID=$(aws ec2 create-security-group \
    --group-name $SECURITY_GROUP_NAME \
    --description "Security group for My Story Buddy application" \
    --query 'GroupId' \
    --output text \
    --region $REGION)
  
  # Add rules for HTTP, HTTPS, SSH, and custom app port
  aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 \
    --region $REGION
  
  aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --region $REGION
  
  aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $REGION
  
  aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 8003 \
    --cidr 0.0.0.0/0 \
    --region $REGION
  
  echo -e "${GREEN}✅ Security group created: $SECURITY_GROUP_ID${NC}"
fi

# User data script for initial setup
USER_DATA=$(cat << 'EOF'
#!/bin/bash
yum update -y

# Install Docker
amazon-linux-extras install docker -y
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install AWS CLI v2 (if not already installed)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Create app directory
mkdir -p /opt/my-story-buddy
chown ec2-user:ec2-user /opt/my-story-buddy

# Create log directory
mkdir -p /var/log/my-story-buddy
chown ec2-user:ec2-user /var/log/my-story-buddy

echo "EC2 setup completed at $(date)" > /var/log/my-story-buddy/setup.log
EOF
)

# Launch EC2 instance
echo -e "${YELLOW}🚀 Launching EC2 instance...${NC}"
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --count 1 \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_PAIR_NAME \
  --security-group-ids $SECURITY_GROUP_ID \
  --user-data "$USER_DATA" \
  --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=$VOLUME_SIZE,VolumeType=gp3}" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Application,Value=MyStoryBuddy}]" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region $REGION)

echo "Instance ID: $INSTANCE_ID"

# Wait for instance to be running
echo -e "${YELLOW}⏱️ Waiting for instance to be running...${NC}"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region $REGION)

echo ""
echo -e "${GREEN}🎉 EC2 Infrastructure Setup Complete!${NC}"
echo ""
echo -e "${GREEN}📋 Infrastructure Details:${NC}"
echo -e "${BLUE}  Instance ID: $INSTANCE_ID${NC}"
echo -e "${BLUE}  Instance Type: $INSTANCE_TYPE${NC}"
echo -e "${BLUE}  Public IP: $PUBLIC_IP${NC}"
echo -e "${BLUE}  Security Group: $SECURITY_GROUP_ID${NC}"
echo -e "${BLUE}  SSH Key: ${KEY_PAIR_NAME}.pem${NC}"
echo ""
echo -e "${GREEN}🔗 Access Information:${NC}"
echo -e "  SSH: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP"
echo -e "  HTTP: http://$PUBLIC_IP"
echo -e "  App Port: http://$PUBLIC_IP:8003"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo -e "  1. Wait 2-3 minutes for instance setup to complete"
echo -e "  2. Run: ./deploy-to-ec2.sh $PUBLIC_IP"
echo -e "  3. Your app will be available at: http://$PUBLIC_IP"
echo ""

# Save configuration for deployment script
cat > ec2-config.env << EOF
INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP
SECURITY_GROUP_ID=$SECURITY_GROUP_ID
KEY_PAIR_NAME=$KEY_PAIR_NAME
REGION=$REGION
EOF

echo -e "${GREEN}✅ Configuration saved to ec2-config.env${NC}"