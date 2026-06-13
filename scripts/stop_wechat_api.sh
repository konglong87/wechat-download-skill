#!/usr/bin/env bash
# Stop the wechat-download-api service.
# Usage: bash stop_wechat_api.sh [port]
set -euo pipefail

PORT="${1:-8765}"

# Find the repo (same logic as start script)
find_repo() {
    if [ -n "${WECHAT_API_REPO:-}" ] && [ -f "$WECHAT_API_REPO/app.py" ]; then
        echo "$WECHAT_API_REPO"
        return
    fi
    for candidate in "./wechat-download-api" "../wechat-download-api"; do
        if [ -f "$candidate/app.py" ]; then
            echo "$(cd "$candidate" && pwd)"
            return
        fi
    done
    echo ""
}

REPO=$(find_repo)
if [ -n "$REPO" ] && [ -f "$REPO/logs/api.pid" ]; then
    PID=$(cat "$REPO/logs/api.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✓ Stopped (PID $PID)"
        rm -f "$REPO/logs/api.pid"
        exit 0
    fi
    rm -f "$REPO/logs/api.pid"
fi

# Fallback: kill by port
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null || true
        echo "✓ Stopped port $PORT (PID $PID)"
        exit 0
    fi
fi

echo "wechat-download-api is not running."