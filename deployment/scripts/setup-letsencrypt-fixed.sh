#!/bin/bash

# Setup Let's Encrypt SSL certificate for api.mystorybuddy.com
# This script should be run on the EC2 instance

echo "🔐 Setting up Let's Encrypt SSL for api.mystorybuddy.com..."

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing Certbot..."
    sudo yum update -y
    sudo amazon-linux-extras install -y epel
    sudo yum install -y certbot python3-certbot-nginx
fi

# Stop Docker containers temporarily to free port 80
echo "🛑 Stopping Docker containers temporarily..."
cd /opt/my-story-buddy
sudo docker-compose down

# Stop nginx if running
echo "🛑 Stopping nginx temporarily..."
sudo systemctl stop nginx 2>/dev/null || true

# Generate Let's Encrypt certificate
echo "🔑 Generating Let's Encrypt certificate..."
sudo certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email admin@mystorybuddy.com \
    -d api.mystorybuddy.com

# Check if certificate was generated successfully
if [ ! -f "/etc/letsencrypt/live/api.mystorybuddy.com/fullchain.pem" ]; then
    echo "❌ Certificate generation failed!"
    echo "Make sure api.mystorybuddy.com points to this server's IP: $(curl -s ifconfig.me)"
    echo "DNS records needed:"
    echo "  A record: api.mystorybuddy.com → $(curl -s ifconfig.me)"
    
    # Restart Docker containers even if cert failed
    echo "🚀 Restarting Docker containers..."
    sudo docker-compose up -d
    exit 1
fi

echo "✅ Certificate generated successfully!"

# Copy the new nginx configuration
echo "⚙️  Updating nginx configuration..."
sudo cp /opt/my-story-buddy/nginx-api-path.conf /etc/nginx/conf.d/mystorybuddy.conf

# Remove any conflicting default configurations
sudo rm -f /etc/nginx/conf.d/default.conf
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Create nginx main config if it doesn't exist or is misconfigured
echo "⚙️  Ensuring nginx main configuration..."
if ! sudo nginx -t 2>/dev/null; then
    echo "📝 Creating nginx main configuration..."
    sudo tee /etc/nginx/nginx.conf > /dev/null <<EOF
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    log_format  main  '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    sendfile            on;
    tcp_nopush          on;
    tcp_nodelay         on;
    keepalive_timeout   65;
    types_hash_max_size 2048;

    include             /etc/nginx/mime.types;
    default_type        application/octet-stream;

    include /etc/nginx/conf.d/*.conf;
}
EOF
fi

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    
    # Start nginx
    echo "🚀 Starting nginx..."
    sudo systemctl start nginx
    sudo systemctl enable nginx
    
    # Wait a moment for nginx to fully start
    sleep 5
    
    # Start Docker containers (they will run behind nginx proxy)
    echo "🚀 Starting Docker containers..."
    sudo docker-compose up -d
    
    # Set up automatic certificate renewal
    echo "🔄 Setting up automatic certificate renewal..."
    
    # Add renewal cron job if it doesn't exist
    if ! sudo crontab -l 2>/dev/null | grep -q "certbot renew"; then
        (sudo crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --nginx --deploy-hook 'systemctl reload nginx'") | sudo crontab -
        echo "✅ Automatic certificate renewal configured"
    else
        echo "✅ Automatic certificate renewal already configured"
    fi
    
    echo "🎉 Let's Encrypt setup complete!"
    echo ""
    echo "🌐 Your backend is now available at:"
    echo "   • https://api.mystorybuddy.com (direct)"
    echo "   • https://www.mystorybuddy.com/api (via CloudFront - after CloudFront config)"
    echo ""
    echo "🧪 Testing HTTPS endpoint..."
    sleep 10
    if curl -k -f https://localhost/health > /dev/null 2>&1; then
        echo "✅ HTTPS endpoint is working!"
    else
        echo "⚠️  HTTPS endpoint test failed, but configuration is complete."
    fi
    
    echo ""
    echo "🔍 Next steps:"
    echo "   1. Configure CloudFront to route /api/* to api.mystorybuddy.com"
    echo "   2. Update frontend code to use /api endpoints"
    echo "   3. Test the complete setup"
    
else
    echo "❌ Nginx configuration error. Please check the configuration."
    echo "🚀 Restarting Docker containers..."
    sudo docker-compose up -d
    exit 1
fi