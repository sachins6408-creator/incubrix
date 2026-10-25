FROM python:3.11-slim

# Install ffmpeg and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY src/ ./src/
COPY static/ ./static/
COPY docs/ ./docs/

# Create runtime directories
RUN mkdir -p data/storage/uploads data/storage/renders data/db

ENV PYTHONPATH=/app/src
ENV FFMPEG_PATH=/usr/bin/ffmpeg
ENV FFPROBE_PATH=/usr/bin/ffprobe

EXPOSE 8000

CMD ["uvicorn", "incubrix.api.v1.app:app", "--host", "0.0.0.0", "--port", "8000"]
