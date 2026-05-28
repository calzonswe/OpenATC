FROM python:3.12-slim AS builder

WORKDIR /build

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download Piper TTS binary
RUN wget -q https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /usr/local/bin/ --strip-components=1 \
    && rm /tmp/piper.tar.gz

# --- Final stage ---
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps: ffmpeg for Opus decode, piper binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy piper binary from builder
COPY --from=builder /usr/local/bin/piper /usr/local/bin/piper

# Copy Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install ML deps (lazy-loaded at runtime)
RUN pip install --no-cache-dir faster-whisper==1.1.0 ollama==0.4.0

# Copy application code, nav data, scripts, config
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY config.toml .

# Create voices directory (bind mount will override this in production)
RUN mkdir -p /app/voices

EXPOSE 8765

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
