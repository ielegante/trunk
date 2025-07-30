#!/bin/bash
# Trunk Simple Setup Script
# One-command setup for small law firms

set -e

echo "======================================"
echo "   Trunk Document Processing Setup    "
echo "======================================"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    echo "Please install Docker Compose from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker is installed"

# Create data directories
echo "Creating data directories..."
mkdir -p data logs cache
echo "✅ Directories created"

# Build and start the container
echo ""
echo "Building Trunk container (this may take a few minutes)..."
docker-compose build

echo ""
echo "Starting Trunk..."
docker-compose up -d

# Wait for service to be ready
echo ""
echo "Waiting for service to start..."
sleep 5

# Check health
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo ""
    echo "✅ Trunk is running successfully!"
    echo ""
    echo "======================================"
    echo "   Setup Complete!                    "
    echo "======================================"
    echo ""
    echo "Trunk is now running at: http://localhost:8080"
    echo ""
    echo "To stop Trunk:    docker-compose down"
    echo "To view logs:     docker-compose logs -f"
    echo "To restart:       docker-compose restart"
    echo ""
    echo "Next steps:"
    echo "1. Install the Chrome extension"
    echo "2. Configure Google Drive permissions"
    echo "3. Start managing your documents!"
    echo ""
else
    echo ""
    echo "❌ Service failed to start properly"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
