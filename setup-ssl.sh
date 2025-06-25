#!/bin/bash

# Script to set up self-signed SSL certificates for HTTPS

echo "🔐 Setting up SSL certificates for HTTPS..."

# Install openssl if not available
if ! command -v openssl &> /dev/null; then
    echo "📦 Installing openssl..."
    sudo yum install -y openssl || sudo apt-get install -y openssl
fi

# Create SSL directory
mkdir -p ssl

# Generate self-signed SSL certificate
echo "🔑 Generating self-signed SSL certificate..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/server.key \
    -out ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=204.236.220.17"

# Set proper permissions
chmod 600 ssl/server.key
chmod 644 ssl/server.crt

echo "✅ SSL certificates created:"
echo "  • ssl/server.key (private key)"
echo "  • ssl/server.crt (certificate)"
echo ""
echo "⚠️  Note: These are self-signed certificates."
echo "   Browsers will show security warnings initially."
echo "   For production, use certificates from a CA like Let's Encrypt."