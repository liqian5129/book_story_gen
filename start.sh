#!/bin/bash
cd "$(dirname "$0")"

# Install deps if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  pip3 install -r requirements.txt
fi

# Copy .env.example to .env if not present
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — please fill in your API keys"
fi

PORT=${PORT:-8888}
echo "Starting 书背后的故事 on http://localhost:$PORT"
PYTHONUNBUFFERED=1 python3 -m uvicorn server:app --host 0.0.0.0 --port $PORT --reload
