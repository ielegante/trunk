#!/bin/bash
# Test Docker build for simplified architecture

echo "🔨 Testing Docker build for simplified Trunk Legal Git architecture..."
echo "=================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker to proceed."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker."
    exit 1
fi

echo "✅ Docker is installed and running"
echo ""

# Start the build
echo "🚀 Starting Docker build..."
echo "Building image: trunk-legal-git:simple"
echo ""

# Build the Docker image
docker build -f Dockerfile.simple -t trunk-legal-git:simple . 2>&1 | tee docker-build.log

# Check if build was successful
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ Docker build completed successfully!"
    echo ""

    # Show image details
    echo "📦 Image details:"
    docker images trunk-legal-git:simple
    echo ""

    # Show image size
    IMAGE_SIZE=$(docker images trunk-legal-git:simple --format "{{.Size}}")
    echo "💾 Image size: $IMAGE_SIZE"
    echo ""

    # Test container startup
    echo "🧪 Testing container startup..."
    docker run -d --name trunk-test \
        -p 8080:8080 \
        -v $(pwd)/test-data:/data \
        trunk-legal-git:simple

    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully"
        echo ""

        # Wait for startup
        echo "⏳ Waiting for application to start (30 seconds)..."
        sleep 30

        # Test health endpoint
        echo "🏥 Testing health endpoint..."
        if curl -f http://localhost:8080/health 2>/dev/null; then
            echo ""
            echo "✅ Health check passed!"
        else
            echo "❌ Health check failed"
        fi
        echo ""

        # Show container logs
        echo "📋 Container logs (last 20 lines):"
        docker logs trunk-test --tail 20
        echo ""

        # Clean up test container
        echo "🧹 Cleaning up test container..."
        docker stop trunk-test && docker rm trunk-test
        echo "✅ Cleanup completed"
    else
        echo "❌ Container failed to start"
        exit 1
    fi

    echo ""
    echo "🎉 Docker build test completed successfully!"
    echo ""
    echo "📝 Build log saved to: docker-build.log"
    echo ""
    echo "🚀 To run the container:"
    echo "docker run -d \\"
    echo "  --name trunk-legal-git \\"
    echo "  -p 8080:8080 \\"
    echo "  -v trunk-data:/data \\"
    echo "  trunk-legal-git:simple"

else
    echo ""
    echo "❌ Docker build failed!"
    echo "Check docker-build.log for details"
    exit 1
fi
