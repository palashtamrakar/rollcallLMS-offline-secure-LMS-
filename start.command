#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

echo "=================================================="
echo "          ROLL CALL LMS — LOCALHOST APP           "
echo "=================================================="
echo "Starting backend server on http://localhost:8000..."

if [ -f "./backend/.venv/bin/uvicorn" ]; then
    ./backend/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
else
    python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
fi

SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null" EXIT INT TERM

sleep 1
echo "Opening browser at http://localhost:8000..."
open "http://localhost:8000" 2>/dev/null || open "http://127.0.0.1:8000" 2>/dev/null || true

echo ""
echo "Roll Call LMS is running at http://localhost:8000"
echo "Press Ctrl+C to stop the server."
wait $SERVER_PID
