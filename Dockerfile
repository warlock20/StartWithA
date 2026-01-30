# Use a slightly older, more stable Python image
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install heavy requirements FIRST for better caching
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir sentence-transformers

# Install the rest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the code (the .dockerignore will skip the .venv bloat)
COPY . .

# Set Flask app for migrations
ENV FLASK_APP=run.py

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Run migrations and start server
# PORT is set by Railway automatically
ENTRYPOINT ["./docker-entrypoint.sh"]