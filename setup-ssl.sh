#!/bin/bash

# Script to set up self-signed SSL certificates for HTTPS

echo "🔐 Setting up SSL certificates for HTTPS..."

# Create SSL directory
mkdir -p ssl

# Generate self-signed SSL certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/server.key \
    -out ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=204.236.220.17"

echo "✅ SSL certificates created:"
echo "  • ssl/server.key (private key)"
echo "  • ssl/server.crt (certificate)"
echo ""
echo "⚠️  Note: These are self-signed certificates."
echo "   Browsers will show security warnings initially."
echo "   For production, use certificates from a CA like Let's Encrypt."