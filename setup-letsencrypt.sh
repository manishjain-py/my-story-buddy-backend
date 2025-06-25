#!/bin/bash

# Setup Let's Encrypt SSL certificate for api.mystorybuddy.com
# This script should be run on the EC2 instance

echo "🔐 Setting up Let's Encrypt SSL for api.mystorybuddy.com..."

# Install certbot and nginx plugin
echo "📦 Installing Certbot..."
sudo yum update -y
sudo amazon-linux-extras install -y epel
sudo yum install -y certbot python3-certbot-nginx

# Stop nginx temporarily for certificate generation
echo "🛑 Stopping nginx temporarily..."
sudo systemctl stop nginx

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
    exit 1
fi

echo "✅ Certificate generated successfully!"

# Copy the new nginx configuration
echo "⚙️  Updating nginx configuration..."
sudo cp /opt/my-story-buddy/nginx-api-path.conf /etc/nginx/conf.d/mystorybuddy.conf

# Remove any conflicting default configurations
sudo rm -f /etc/nginx/conf.d/default.conf
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    
    # Start nginx
    echo "🚀 Starting nginx..."
    sudo systemctl start nginx
    sudo systemctl enable nginx
    
    # Set up automatic certificate renewal
    echo "🔄 Setting up automatic certificate renewal..."
    sudo crontab -l > /tmp/crontab_backup 2>/dev/null || true
    
    # Add renewal cron job if it doesn't exist
    if ! sudo crontab -l 2>/dev/null | grep -q "certbot renew"; then
        echo "0 12 * * * /usr/bin/certbot renew --quiet --nginx" | sudo crontab -
        echo "✅ Automatic certificate renewal configured"
    else
        echo "✅ Automatic certificate renewal already configured"
    fi
    
    echo "🎉 Let's Encrypt setup complete!"
    echo ""
    echo "🌐 Your backend is now available at:"
    echo "   • https://api.mystorybuddy.com (direct)"
    echo "   • https://www.mystorybuddy.com/api (via CloudFront)"
    echo ""
    echo "🔍 Next steps:"
    echo "   1. Configure CloudFront to route /api/* to this EC2 instance"
    echo "   2. Update frontend code to use /api endpoints"
    echo "   3. Test the complete setup"
    
else
    echo "❌ Nginx configuration error. Please check the configuration."
    exit 1
fi