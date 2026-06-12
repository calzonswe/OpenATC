#!/bin/bash
# OpenATC Server — Docker entrypoint
set -e

echo "=== OpenATC Server Entrypoint ==="

# Step 1: Download TTS voices if volume is empty
if [ ! -f /app/voices/.downloaded ]; then
    echo "[1/4] Downloading TTS voices..."
    python /app/scripts/download_voices.py
    touch /app/voices/.downloaded
else
    echo "[1/4] TTS voices already cached"
fi

# Step 2: Wait for Ollama to be ready
echo "[2/4] Waiting for Ollama at ${LLM_HOST:-http://ollama:11434}..."
OLLAMA_HOST="${LLM_HOST:-http://ollama:11434}"
RETRIES=30
COUNT=0
until curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; do
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $RETRIES ]; then
        echo "ERROR: Ollama did not become ready after $RETRIES attempts"
        exit 1
    fi
    sleep 2
done
echo "      Ollama is ready"

# Step 3: Pull LLM model if not present
MODEL="${LLM_MODEL:-qwen2.5:7b}"
echo "[3/4] Ensuring LLM model '$MODEL' is available..."
EXISTING=$(curl -s "$OLLAMA_HOST/api/tags" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = [m['name'] for m in data.get('models', [])]
    print('|'.join(models))
except: print('')
")
if echo "$EXISTING" | grep -q "$MODEL"; then
    echo "      Model '$MODEL' already pulled"
else
    echo "      Pulling $MODEL (this may take a while)..."
    curl -s -X POST "$OLLAMA_HOST/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$MODEL\"}"
    echo ""
    echo "      Model pull complete"
fi

# Step 4: Start the server
LOG_LEVEL="${SERVER_LOG_LEVEL:-info}"
echo "[4/4] Starting OpenATC Server (log_level=$LOG_LEVEL)..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8765 --log-level "$LOG_LEVEL"
