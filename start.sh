#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

echo "=================================================="
echo "          ROLL CALL LMS — LOCALHOST APP           "
echo "=================================================="
echo "Starting backend server on http://localhost:8000..."

if [ -x "./backend/.venv/bin/python" ]; then
    ./backend/.venv/bin/python backend/storage_bootstrap.py
else
    python3 backend/storage_bootstrap.py
fi
