#!/bin/bash
set -e

# Clean up old package and zip
rm -rf package deployment.zip

# Install dependencies using venv pip
./venv/bin/pip install --target ./package -r requirements.txt

# Copy app files
cp main.py package/
cp lambda_function.py package/ 2>/dev/null || true

# Zip everything
cd package
zip -r ../deployment.zip .
cd ..

echo "deployment.zip is ready for AWS Lambda upload." 