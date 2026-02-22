# Start from Python 3.11 slim image (Bookworm/OpenSSL 3)
FROM python:3.11-slim

# Enable legacy cryptography in OpenSSL 3 for older Cisco devices (ssh-rsa, diffie-hellman-group14-sha1)
RUN sed -i 's/^DEFAULT@SECLEVEL=2/DEFAULT@SECLEVEL=0/' /etc/ssl/openssl.cnf && \
    sed -i 's/^\[provider_sect\]/[provider_sect]\nlegacy = legacy_sect/' /etc/ssl/openssl.cnf && \
    sed -i 's/^\[default_sect\]/[default_sect]\nactivate = 1\n[legacy_sect]\nactivate = 1/' /etc/ssl/openssl.cnf

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    iputils-ping \
    openssh-client \
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
