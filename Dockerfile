FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for webpack build + weasyprint rendering libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl nodejs npm \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies (no torch/sentence-transformers — uses Gemini embeddings)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build frontend React bundles (webpack)
RUN npm ci --prefer-offline && npm run build && rm -rf node_modules

# Set Flask app for migrations and asset builds
ENV FLASK_APP=run.py

# Pre-build CSS bundles (Flask-Assets: 85 files → 1 minified bundle)
RUN flask assets build

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--timeout", "120", "--keep-alive", "5", "--preload", "run:app"]
