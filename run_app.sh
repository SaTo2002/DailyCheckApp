#!/bin/bash

# ==============================================================================
# DailyCheckApp - Linux Startup Script (run_app.sh)
# ==============================================================================

# Get current script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================================"
echo "          🚀 Starting DailyCheckApp Server on Linux..."
echo "============================================================"
echo ""
echo "📍 Working Directory: $DIR"
echo "🌐 Server URL: http://127.0.0.1:5000"
echo ""

# Activate Virtual Environment if exists, else use system python3
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python app.py
elif [ -d "venv" ]; then
    source venv/bin/activate
    python app.py
else
    python3 app.py
fi
