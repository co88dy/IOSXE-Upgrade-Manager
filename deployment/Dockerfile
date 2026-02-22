# Start from Python 3.11 slim buster image (Debian 10/OpenSSL 1.1.1)
# 1. Buster avoids Glibc 2.31+ which crashes heavily on WSL1 with "exec format error"
# 2. OpenSSL 1.1.1 inherently supports legacy algorithms for Cisco SSH without hacking policy files.
FROM python:3.11-slim-buster

# Set working directory
WORKDIR /app

# Buster is EOL, so update sources.list to point to the Debian Archive and ignore expiration checks
RUN echo "deb http://archive.debian.org/debian/ buster main" > /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list && \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until

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
