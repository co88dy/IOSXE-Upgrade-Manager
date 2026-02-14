#!/bin/bash
# WSL Installation Script for IOS-XE Upgrade Manager

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     IOS-XE Upgrade Manager - WSL Installation            ║"
echo "╚═══════════════════════════════════════════════════════════╝"

# Create virtual environment
echo "[1/5] Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "[2/5] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "[3/5] Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "[4/5] Installing dependencies..."
pip install flask flask-apscheduler ncclient netmiko paramiko xmltodict

# Set Flask app
echo "[5/5] Setting environment variables..."
export FLASK_APP=main.py

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the application:"
echo "  1. source venv/bin/activate"
echo "  2. python main.py"
echo ""
echo "The application will be available at http://localhost:5000"
