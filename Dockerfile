# Use a slightly older, more stable Python image
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for webpack build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev nodejs npm && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies (no torch/sentence-transformers — uses Gemini embeddings)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the code (the .dockerignore will skip the .venv bloat)
COPY . .

# Build frontend React bundles (webpack)
RUN npm ci --prefer-offline && npm run build && rm -rf node_modules

# Set Flask app for migrations
ENV FLASK_APP=run.py

# Pre-build CSS bundles (Flask-Assets: 85 files → 1 minified bundle)
RUN flask assets build

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Run migrations and start server
# PORT is set by Railway automatically
ENTRYPOINT ["./docker-entrypoint.sh"]