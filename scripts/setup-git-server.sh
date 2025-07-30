#!/bin/bash
# Sprint 1: Git Server Setup Script
# Sets up GitLab CE for Trunk document repositories

set -e

echo "======================================"
echo "   Trunk Git Server Setup             "
echo "======================================"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "Please install Docker Desktop first."
    exit 1
fi

# Choose git server
echo "Which git server would you like to use?"
echo "1) GitLab CE (recommended, more features)"
echo "2) Gitea (lightweight alternative)"
read -p "Enter choice (1 or 2): " choice

case $choice in
    1)
        GIT_SERVER="gitlab"
        echo "Setting up GitLab CE..."
        ;;
    2)
        GIT_SERVER="gitea"
        echo "Setting up Gitea..."
        ;;
    *)
        echo "Invalid choice. Defaulting to GitLab CE."
        GIT_SERVER="gitlab"
        ;;
esac

# Create directories
echo "Creating data directories..."
if [ "$GIT_SERVER" = "gitlab" ]; then
    mkdir -p gitlab/{config,logs,data}
    chmod -R 755 gitlab/
else
    mkdir -p gitea/data
    chmod -R 755 gitea/
fi

# Start the selected git server
echo "Starting $GIT_SERVER..."
if [ "$GIT_SERVER" = "gitlab" ]; then
    docker-compose up -d gitlab
    echo ""
    echo "⏳ GitLab is starting (this may take 5-10 minutes)..."
    echo ""
    echo "You can check the startup progress with:"
    echo "  docker-compose logs -f gitlab"
    echo ""
    echo "Once started, access GitLab at: http://localhost:8090"
    echo "Default credentials:"
    echo "  Username: root"
    echo "  Password: TrunkAdmin123!"
    echo ""
    echo "⚠️  IMPORTANT: Change the admin password after first login!"
else
    docker-compose --profile gitea up -d
    echo ""
    echo "Waiting for Gitea to start..."
    sleep 10
    echo ""
    echo "✅ Gitea is running!"
    echo "Access Gitea at: http://localhost:3000"
    echo ""
    echo "First-time setup:"
    echo "1. Go to http://localhost:3000"
    echo "2. Complete the installation wizard"
    echo "3. Create an admin account"
fi

echo ""
echo "======================================"
echo "   Git Server Setup Complete          "
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Access the git server web interface"
echo "2. Create user accounts for your law firm"
echo "3. Create repositories for each Google Drive folder"
echo "4. Configure the Chrome extension to connect"
echo ""
echo "To stop the git server:"
echo "  docker-compose down"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f $GIT_SERVER"
