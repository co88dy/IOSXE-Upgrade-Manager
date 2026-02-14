# IOS-XE Upgrade Manager

A model-driven web application for automated Cisco IOS-XE software management using NETCONF, SSH, and HTTP protocols.

## Features

- **Device Discovery**: Automatic discovery via NETCONF with SSH fallback
- **Pre-Check Engine**: Automated validation (disk space, boot variables, ROMMON flags, version comparison)
- **Repository Management**: Image upload with MD5 verification
- **One-Step Upgrades**: Automated install/activate/commit workflow
- **Real-Time Monitoring**: Server-Sent Events (SSE) for live upgrade logs
- **Modern UI**: Dark-mode interface with glassmorphism effects

## Quick Start

### Option 1: Native Install (Shell Script)
For Linux/WSL environments, use the included installer script:
```bash
cd deployment
chmod +x install_wsl.sh
./install_wsl.sh
source venv/bin/activate
python main.py
```

### Option 2: Docker (Recommended)
Run the application as a reproducible container using Nix:

1. **Build the Image**:
   ```bash
   nix build .#docker-image
   ```

2. **Load Image**:
   ```bash
   docker load < result
   ```

3. **Run Container**:
   ```bash
   docker run -d \
     --name iosxe-manager \
     -p 5000:5000 \
     -p 80:80 \
     -v "$(pwd):/app" \
     ios-xe-upgrade-manager:latest
   ```

## Configuration

Edit `config.json` to customize:
- Database path
- Repository directory
- Default credentials
- Flask server settings

## Architecture

- **Backend**: Flask with modular blueprints
- **Database**: SQLite for lightweight persistence
- **Communication**: NETCONF (primary), SSH (fallback), HTTP (image transfer)
- **Frontend**: Vanilla JavaScript with SSE for real-time updates

## Usage

1. **Discover Devices**: Enter IP addresses and click "Discover Devices"
2. **Upload Images**: Drag and drop IOS-XE .bin files to repository
3. **Run Pre-Checks**: Select device and target version, run validation
4. **Schedule Upgrade**: If pre-checks pass, start upgrade immediately

## API Endpoints

- `POST /api/discover` - Discover devices
- `POST /api/netconf/toggle` - Enable/disable NETCONF
- `POST /api/repository/upload` - Upload image
- `POST /api/precheck` - Run pre-checks
- `POST /api/upgrade/schedule` - Schedule upgrade
- `GET /api/events` - SSE event stream

## Requirements

- Python 3.11+
- Network access to Cisco IOS-XE devices
- NETCONF enabled on devices (or SSH access to enable it)

## License

MIT License
