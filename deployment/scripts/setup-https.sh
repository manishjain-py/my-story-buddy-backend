#!/bin/bash

# Setup HTTPS for EC2 instance using Let's Encrypt or self-signed certificates

echo "🔐 Setting up HTTPS for EC2 instance..."

# Install nginx and openssl
echo "📦 Installing required packages..."
sudo yum update -y
sudo yum install -y openssl

# Install nginx using Amazon Linux Extras
echo "📦 Installing nginx using Amazon Linux Extras..."
sudo amazon-linux-extras install -y nginx1

# Create nginx configuration for HTTPS
echo "⚙️  Creating nginx configuration..."
sudo mkdir -p /etc/nginx/conf.d

# Create SSL certificates directory
sudo mkdir -p /etc/ssl/certs
sudo mkdir -p /etc/ssl/private

# Generate self-signed SSL certificate
echo "🔑 Generating self-signed SSL certificate..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/mystorybuddy.key \
    -out /etc/ssl/certs/mystorybuddy.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=204.236.220.17"

# Set proper permissions
sudo chmod 600 /etc/ssl/private/mystorybuddy.key
sudo chmod 644 /etc/ssl/certs/mystorybuddy.crt

# Create nginx configuration
sudo tee /etc/nginx/conf.d/mystorybuddy.conf > /dev/null <<EOF
# HTTP server (redirect to HTTPS)
server {
    listen 80;
    server_name 204.236.220.17;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl;
    server_name 204.236.220.17;
    
    # SSL certificates
    ssl_certificate /etc/ssl/certs/mystorybuddy.crt;
    ssl_certificate_key /etc/ssl/private/mystorybuddy.key;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # CORS headers
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' '*' always;
    
    # Handle preflight requests
    location / {
        if (\$request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' '*';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
        
        # Proxy to backend
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Increase timeouts for long-running requests
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
EOF

# Start and enable nginx
echo "🚀 Starting nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Check nginx status
echo "✅ Nginx status:"
sudo systemctl status nginx --no-pager

# Test configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

echo "✅ HTTPS setup complete!"
echo "🌐 Your backend should now be available at:"
echo "   • HTTP:  http://204.236.220.17 (redirects to HTTPS)"
echo "   • HTTPS: https://204.236.220.17"
echo ""
echo "⚠️  Note: Browsers will show a security warning for self-signed certificates."
echo "   Click 'Advanced' -> 'Proceed to site' to accept the certificate."