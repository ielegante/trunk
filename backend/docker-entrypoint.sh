#!/bin/bash
# Trunk Legal Git - Docker Entry Point
# Initializes the simple deployment environment

set -e

echo "Starting Trunk Legal Git..."

# Create data directories
mkdir -p /data/db
mkdir -p /data/logs
mkdir -p /data/repos

# Initialize database if not exists
if [ ! -f /data/db/trunk.db ]; then
    echo "Initializing database..."
    cd /app/backend && python -c "
from app.database import init_database
init_database()
print('Database initialized successfully')
"
fi

# Set permissions if running as root
if [ "$(id -u)" = "0" ]; then
    chown -R trunk:trunk /data
fi

# Start supervisor
exec "$@"
