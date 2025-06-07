#!/bin/bash

# Build the Docker image
docker build -t lambda-builder .

# Create a temporary container and copy the deployment package
docker create --name temp-container lambda-builder
docker cp temp-container:/tmp/deployment.zip ./deployment.zip

# Clean up
docker rm temp-container

echo "Deployment package has been created at ./deployment.zip" 