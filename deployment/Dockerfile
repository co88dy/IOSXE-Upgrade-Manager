# Start from Python 3.11 Bullseye slim image
# Note: We use bullseye instead of bookworm to use OpenSSL 1.1.1,
# as OpenSSL 3 (in bookworm) strictly blocks the SHA1 legacy crypto used by many Cisco devices via SSH.
FROM --platform=$TARGETPLATFORM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create database and repo directories if they don't exist
RUN mkdir -p app/database app/repo

# Set environment variables
ENV FLASK_APP=main.py
ENV FLASK_ENV=production

# Expose ports
EXPOSE 5000 80

# Run the application
CMD ["python", "main.py"]
