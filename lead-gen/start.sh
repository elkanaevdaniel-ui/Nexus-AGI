#!/bin/bash
# Lead Gen Service startup script
set -e

cd "$(dirname "$0")"

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "Starting Lead Gen service on port ${LEAD_GEN_PORT:-8082}..."
uvicorn src.main:app --host 0.0.0.0 --port "${LEAD_GEN_PORT:-8082}" --reload
