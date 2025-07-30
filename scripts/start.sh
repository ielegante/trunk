#!/bin/bash
# Production startup script for Trunk Document Processing Service

set -e

# Configuration
APP_NAME="trunk-doc-processor"
APP_DIR="/app"
LOG_DIR="/app/logs"
PID_FILE="/app/app.pid"
CONFIG_FILE="/app/config/production.py"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/startup.log"
}

# Function to check if service is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to wait for dependencies
wait_for_dependencies() {
    log "Waiting for dependencies to be ready..."

    # Wait for Redis
    if [ -n "$REDIS_URL" ]; then
        log "Waiting for Redis..."
        until redis-cli -u "$REDIS_URL" ping > /dev/null 2>&1; do
            log "Redis is not ready yet. Waiting..."
            sleep 2
        done
        log "Redis is ready"
    fi

    # Wait for PostgreSQL
    if [ -n "$DATABASE_URL" ]; then
        log "Waiting for PostgreSQL..."
        until pg_isready -d "$DATABASE_URL" > /dev/null 2>&1; do
            log "PostgreSQL is not ready yet. Waiting..."
            sleep 2
        done
        log "PostgreSQL is ready"
    fi

    log "All dependencies are ready"
}

# Function to perform pre-flight checks
preflight_checks() {
    log "Performing pre-flight checks..."

    # Check Python version
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    log "Python version: $PYTHON_VERSION"

    # Check required environment variables
    required_vars=(
        "ENV"
        "SERVER_HOST"
        "SERVER_PORT"
    )

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done

    # Check directory permissions
    if [ ! -w "$APP_DIR" ]; then
        log "ERROR: App directory $APP_DIR is not writable"
        exit 1
    fi

    if [ ! -w "$LOG_DIR" ]; then
        log "ERROR: Log directory $LOG_DIR is not writable"
        exit 1
    fi

    # Check disk space
    DISK_USAGE=$(df "$APP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 85 ]; then
        log "WARNING: Disk usage is at $DISK_USAGE%. Consider freeing up space."
    fi

    # Check memory
    MEMORY_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    if [ "$MEMORY_USAGE" -gt 80 ]; then
        log "WARNING: Memory usage is at $MEMORY_USAGE%"
    fi

    log "Pre-flight checks completed"
}

# Function to start the application
start_application() {
    log "Starting $APP_NAME..."

    # Change to app directory
    cd "$APP_DIR"

    # Set Python path
    export PYTHONPATH="$APP_DIR:$PYTHONPATH"

    # Start the application
    if [ "$ENV" = "production" ]; then
        # Production: Use gunicorn with multiple workers
        log "Starting in production mode with gunicorn"
        gunicorn \
            --bind "${SERVER_HOST}:${SERVER_PORT}" \
            --workers "${WORKERS:-4}" \
            --worker-class uvicorn.workers.UvicornWorker \
            --worker-connections "${WORKER_CONNECTIONS:-1000}" \
            --max-requests 1000 \
            --max-requests-jitter 50 \
            --preload \
            --timeout 300 \
            --graceful-timeout 30 \
            --keep-alive 2 \
            --log-level info \
            --log-file "$LOG_DIR/gunicorn.log" \
            --access-logfile "$LOG_DIR/access.log" \
            --error-logfile "$LOG_DIR/error.log" \
            --pid "$PID_FILE" \
            --daemon \
            doc_processing.main:app
    else
        # Development: Use uvicorn directly
        log "Starting in development mode with uvicorn"
        uvicorn \
            doc_processing.main:app \
            --host "${SERVER_HOST}" \
            --port "${SERVER_PORT}" \
            --reload \
            --log-level debug \
            --access-log \
            &
        echo $! > "$PID_FILE"
    fi

    # Wait a moment for the process to start
    sleep 2

    # Check if the service started successfully
    if is_running; then
        PID=$(cat "$PID_FILE")
        log "$APP_NAME started successfully (PID: $PID)"

        # Wait for the service to be ready
        log "Waiting for service to be ready..."
        for i in {1..30}; do
            if curl -f "http://${SERVER_HOST}:${SERVER_PORT}/health" > /dev/null 2>&1; then
                log "Service is ready and responding to health checks"
                return 0
            fi
            log "Service not ready yet. Waiting... ($i/30)"
            sleep 1
        done

        log "WARNING: Service started but health check is not responding"
        return 1
    else
        log "ERROR: Failed to start $APP_NAME"
        return 1
    fi
}

# Function to stop the application
stop_application() {
    log "Stopping $APP_NAME..."

    if is_running; then
        PID=$(cat "$PID_FILE")
        log "Sending SIGTERM to process $PID"
        kill -TERM "$PID"

        # Wait for graceful shutdown
        TIMEOUT=${GRACEFUL_SHUTDOWN_TIMEOUT:-30}
        for i in $(seq 1 $TIMEOUT); do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                log "$APP_NAME stopped gracefully"
                rm -f "$PID_FILE"
                return 0
            fi
            sleep 1
        done

        # Force kill if still running
        log "Graceful shutdown timeout. Force killing process $PID"
        kill -KILL "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        log "$APP_NAME stopped forcefully"
    else
        log "$APP_NAME is not running"
    fi
}

# Function to restart the application
restart_application() {
    log "Restarting $APP_NAME..."
    stop_application
    sleep 2
    start_application
}

# Function to check application status
check_status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log "$APP_NAME is running (PID: $PID)"

        # Check health endpoint
        if curl -f "http://${SERVER_HOST}:${SERVER_PORT}/health" > /dev/null 2>&1; then
            log "Health check: OK"
        else
            log "Health check: FAILED"
            return 1
        fi

        # Show resource usage
        ps -p "$PID" -o pid,ppid,cmd,%mem,%cpu --no-headers | while read pid ppid cmd mem cpu; do
            log "Resource usage - PID: $pid, Memory: $mem%, CPU: $cpu%"
        done

        return 0
    else
        log "$APP_NAME is not running"
        return 1
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_DIR/app.log" ]; then
        tail -f "$LOG_DIR/app.log"
    else
        log "No application logs found"
    fi
}

# Function to cleanup
cleanup() {
    log "Performing cleanup..."

    # Remove stale PID file
    if [ -f "$PID_FILE" ]; then
        if ! is_running; then
            rm -f "$PID_FILE"
            log "Removed stale PID file"
        fi
    fi

    # Cleanup old logs (keep last 10 files)
    find "$LOG_DIR" -name "*.log.*" -type f -mtime +7 -delete 2>/dev/null || true

    # Cleanup temporary files
    if [ -d "/app/data/temp" ]; then
        find "/app/data/temp" -type f -mtime +1 -delete 2>/dev/null || true
    fi

    log "Cleanup completed"
}

# Main execution
case "$1" in
    start)
        if is_running; then
            log "$APP_NAME is already running"
            exit 0
        fi

        wait_for_dependencies
        preflight_checks
        start_application
        ;;

    stop)
        stop_application
        ;;

    restart)
        restart_application
        ;;

    status)
        check_status
        ;;

    logs)
        show_logs
        ;;

    cleanup)
        cleanup
        ;;

    health)
        if curl -f "http://${SERVER_HOST}:${SERVER_PORT}/health" > /dev/null 2>&1; then
            echo "OK"
            exit 0
        else
            echo "FAILED"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|status|logs|cleanup|health}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the application"
        echo "  stop     - Stop the application"
        echo "  restart  - Restart the application"
        echo "  status   - Check application status"
        echo "  logs     - Show application logs"
        echo "  cleanup  - Clean up old logs and temporary files"
        echo "  health   - Check health endpoint"
        exit 1
        ;;
esac
