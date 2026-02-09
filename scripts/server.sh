#!/bin/bash
# Server management script for whati8 API

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="/tmp/whati8_server.pid"
LOG_FILE="/tmp/whati8_server.log"
PORT="${WHATI8_PORT:-15853}"
HOST="${WHATI8_HOST:-0.0.0.0}"

cd "$PROJECT_DIR"

check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            # Stale PID file
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

start_server() {
    if check_running; then
        echo "Server is already running (PID: $(cat $PID_FILE))"
        echo "Access at: http://192.168.1.11:$PORT/docs"
        exit 1
    fi

    echo "Starting whati8 API server..."
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Log: $LOG_FILE"

    # Start server in background
    uv run python -m whati8 serve --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &

    # Save PID
    echo $! > "$PID_FILE"

    # Wait for server to start
    echo -n "Waiting for server to start"
    for i in {1..10}; do
        sleep 0.5
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            echo " ✓"
            echo ""
            echo "Server started successfully!"
            echo "  PID: $(cat $PID_FILE)"
            echo "  Health: http://localhost:$PORT/health"
            echo ""
            echo "Access API documentation:"
            echo "  Swagger UI: http://192.168.1.11:$PORT/docs"
            echo "  ReDoc:      http://192.168.1.11:$PORT/redoc"
            echo "  Local:      http://localhost:$PORT/docs"
            echo ""
            echo "View logs: tail -f $LOG_FILE"
            return 0
        fi
        echo -n "."
    done

    echo " ✗"
    echo "Server failed to start. Check logs:"
    echo "  tail -20 $LOG_FILE"

    # Clean up PID file if start failed
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    exit 1
}

stop_server() {
    if ! check_running; then
        echo "Server is not running"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    echo "Stopping whati8 API server (PID: $PID)..."

    # Try graceful shutdown
    kill "$PID" 2>/dev/null || true

    # Wait for shutdown
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "Server stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 0.5
    done

    # Force kill if still running
    echo "Server didn't stop gracefully, forcing..."
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Server stopped (forced)"
}

restart_server() {
    echo "Restarting whati8 API server..."
    stop_server
    sleep 1
    start_server
}

status_server() {
    if check_running; then
        PID=$(cat "$PID_FILE")
        echo "Server is running"
        echo "  PID: $PID"
        echo "  Port: $PORT"
        echo "  Swagger UI: http://192.168.1.11:$PORT/docs"
        echo "  Logs: $LOG_FILE"

        # Check if actually responding
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            echo "  Status: ✓ Healthy"
        else
            echo "  Status: ✗ Not responding"
        fi
    else
        echo "Server is not running"
    fi
}

logs_server() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "No log file found at: $LOG_FILE"
        exit 1
    fi

    if [ "$1" = "-f" ] || [ "$1" = "--follow" ]; then
        tail -f "$LOG_FILE"
    else
        tail -50 "$LOG_FILE"
    fi
}

case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status_server
        ;;
    logs)
        logs_server "$2"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the API server"
        echo "  stop     - Stop the API server"
        echo "  restart  - Restart the API server"
        echo "  status   - Check server status"
        echo "  logs     - View recent logs (add -f to follow)"
        echo ""
        echo "Environment variables:"
        echo "  WHATI8_PORT - Server port (default: 15853)"
        echo "  WHATI8_HOST - Server host (default: 0.0.0.0)"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs -f"
        echo "  WHATI8_PORT=8080 $0 start"
        exit 1
        ;;
esac
