#!/usr/bin/env bash
# Start wechat-download-api in the background.
#
# By default, looks for the wechat-download-api repo at:
#   1. $WECHAT_API_REPO  (env var, if set)
#   2. ./wechat-download-api  (relative to CWD)
#   3. ../wechat-download-api  (sibling directory)
# If not found, it clones the repo into ./wechat-download-api.
#
# Usage: bash start_wechat_api.sh [port]
set -euo pipefail

PORT="${1:-8765}"

# ---- resolve repo path ----
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
if [ -z "$REPO" ]; then
    if ! command -v git >/dev/null 2>&1; then
        echo "ERROR: Cannot find wechat-download-api checkout and git is not installed."
        echo "Set WECHAT_API_REPO=/path/to/wechat-download-api after cloning it manually."
        exit 1
    fi

    echo "wechat-download-api not found. Cloning into ./wechat-download-api ..."
    git clone https://github.com/tmwgsicp/wechat-download-api.git ./wechat-download-api
    REPO="$(cd ./wechat-download-api && pwd)"
fi

echo "Using wechat-download-api at: $REPO"
cd "$REPO"

# ---- already running? ----
if command -v lsof >/dev/null 2>&1 && lsof -ti:"$PORT" >/dev/null 2>&1; then
    # Port is occupied — verify it's actually wechat-download-api
    if curl -s "http://localhost:$PORT/api/health" 2>/dev/null | grep -q '"status":"healthy"'; then
        echo "Already running on port $PORT (wechat-download-api confirmed)"
        echo "Dashboard: http://localhost:$PORT"
        exit 0
    else
        echo "ERROR: Port $PORT is in use by another process, not wechat-download-api."
        echo "Use a different port: bash scripts/start_wechat_api.sh 9876"
        exit 1
    fi
fi

# ---- ensure .env ----
if [ ! -f .env ]; then
    cp env.example .env 2>/dev/null || echo "WARNING: no .env or env.example"
fi

# Update port in .env (macOS sed compat)
if grep -q "^PORT=" .env 2>/dev/null; then
    sed -i.bak "s/^PORT=.*/PORT=$PORT/" .env && rm -f .env.bak
else
    echo "PORT=$PORT" >> .env
fi
if grep -q "^SITE_URL=" .env 2>/dev/null; then
    sed -i.bak "s|^SITE_URL=.*|SITE_URL=http://localhost:$PORT|" .env && rm -f .env.bak
else
    echo "SITE_URL=http://localhost:$PORT" >> .env
fi

# ---- install deps if missing ----
if ! python3 -c "import fastapi, curl_cffi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip3 install fastapi uvicorn pydantic httpx python-dotenv 'curl_cffi>=0.7.0' beautifulsoup4
fi

# ---- start ----
mkdir -p logs
echo "Starting on port $PORT ..."
nohup python3 app.py > logs/api.log 2>&1 &
PID=$!
echo "$PID" > logs/api.pid

sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "✓ Started!  PID: $PID"
    echo "  Dashboard:  http://localhost:$PORT"
    echo "  Login:      http://localhost:$PORT/login.html"
    echo "  API docs:   http://localhost:$PORT/api/docs"
else
    echo "✗ Failed to start. Log:"
    tail -20 logs/api.log
    exit 1
fi
