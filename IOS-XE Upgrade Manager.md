# IOS-XE Upgrade Manager

A full-stack Flask web application for managing, pre-checking, and upgrading Cisco IOS-XE devices (switches and routers). Built to streamline the upgrade lifecycle the way Cisco DNA Center does, but self-hosted and lightweight.

---

## Features

### 📡 Device Discovery
- Add device IPs manually or in bulk via the UI
- Auto-discovers devices using NETCONF (ncclient) with SSH (Netmiko) fallback
- Determines device role (switch vs. router) automatically from the part number
- Stores all discovered data in a persistent SQLite database

### 📊 Device Inventory
- Clean table view of all discovered devices with live status badges
- Columns: IP, Hostname, Model, Version, ROMMON, Boot Variable, Filesystem, NETCONF state, Last Seen
- Click any NETCONF badge to toggle NETCONF-YANG on/off — performs a **live SSH check** of the real device state before prompting for confirmation, and auto-syncs any drift between the DB and device
- Select devices individually or in bulk via checkboxes for bulk operations

### ✅ Pre-Check Engine
- Runs a full suite of pre-upgrade validations per device via NETCONF or SSH
- Checks include:
  - Upgrade vs. downgrade detection
  - Boot variable validation
  - Disk space (Error < 1 GB, Warning < 2 GB) — checked per stack member on switches
  - ROMMON variable validation (`SWITCH_IGNORE_STARTUP_CFG`)
  - Running image vs. boot variable consistency
  - Stack member health (for switch stacks)
- Results displayed per-device with Pass / Warning / Fail status
- Detailed pre-check report page per device

### 📦 Image Repository
- Local HTTP file server (port 80) managed entirely through the UI
- Upload `.bin` firmware images via drag-and-drop or file picker
- Add MD5 checksums alongside images for post-copy verification
- Repository page displays the configured HTTP download URL for use on devices
- HTTP server IP is configured in Dashboard → Settings and detected automatically from host interfaces

### 🔁 Image Copy & Verify
- Initiates `copy http://...` from the device to pull the image from the local repo
- Tracks copy progress in real time via SSE event stream
- Post-copy MD5 verification against the stored checksum

### ⬆️ Upgrade Scheduling
- Schedule upgrades per device or in bulk
- Uses `install add file flash:<image> activate commit prompt-level none` (switches) or `bootflash:` (routers)
- Schedule picker uses the local machine timezone
- Upgrades run as background jobs — real-time log output and status visible per device in the UI

### 🗂️ Jobs & History
- All operations (discovery, pre-check, copy, verify, upgrade) run as tracked jobs
- Real-time status polling with SSE events
- Clear Jobs button to purge completed job history

### ⚙️ Settings
- Device credentials (SSH username, password, enable password, NETCONF port)
- Global timezone for scheduling
- Repository HTTP Server IP — dropdown auto-populated from all detected host IPv4 addresses, with a manual entry option

---

## Supported Devices

All Cisco IOS-XE 17.0+ platforms:
- **Switches:** Catalyst 9200, 9300, 9400, 9500, 9600 series (stackable and standalone)
- **Routers:** ASR 1000, ISR 4000, CSR 1000v, Catalyst 8000 series

Filesystem is automatically set to `flash:` for switches and `bootflash:` for routers.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask |
| Device comms | ncclient (NETCONF), Netmiko (SSH/CLI) |
| Database | SQLite (via built-in `sqlite3`) |
| Scheduling | APScheduler |
| Real-time updates | Server-Sent Events (SSE) |
| Frontend | Vanilla HTML/CSS/JS (Inter font, dark theme) |
| Containerization | Docker |

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
docker pull co88dy/iosxe-upgrade-manager:latest

docker run -d \
  --name iosxe-upgrade-manager \
  -p 5000:5000 \
  -p 80:80 \
  -v $(pwd)/data:/app/app/database \
  -v $(pwd)/repo:/app/app/repo \
  co88dy/iosxe-upgrade-manager:latest
```

Open `http://localhost:5000` in your browser.

> **Note:** Port 80 must be available on the host for devices to pull images via HTTP. Use the host machine IP (not `127.0.0.1`) in Dashboard → Settings → Repository HTTP Server IP.

### Option 2 — Local / venv

```bash
git clone https://github.com/co88dy/IOSXE-Upgrade-Manager.git
cd IOSXE-Upgrade-Manager

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 main.py
```

Open `http://localhost:5000`.

---

## Configuration

All settings are stored in `config.json` at the project root. On first run the file is pre-populated with safe defaults. **Do not commit credentials** — add `config.json` to `.gitignore` if deploying publicly.

Key fields:

| Field | Description |
|---|---|
| `credentials.ssh_username` | SSH login for all devices |
| `credentials.ssh_password` | SSH password |
| `credentials.enable_password` | Enable/privileged exec password |
| `credentials.netconf_port` | NETCONF port (default 830) |
| `http_server_ip` | IP devices use to pull images via HTTP |
| `scheduler.timezone` | Timezone for scheduled upgrades (e.g. `America/Denver`) |
| `flask.debug` | Set `false` in production |

Settings can also be changed at runtime via Dashboard → Settings without editing the file manually.

---

## Project Structure

```
.
├── main.py                        # Flask app entry point
├── config.json                    # Runtime config (credentials, paths, etc.)
├── requirements.txt
├── app/
│   ├── blueprints/                # Flask route handlers (one file per feature)
│   │   ├── discovery.py           # Device discovery + NETCONF toggle
│   │   ├── bulk_ops.py            # Bulk pre-check and operations
│   │   ├── copy_image.py          # Image copy to device
│   │   ├── verify_image.py        # MD5 verification
│   │   ├── upgrade.py             # Upgrade scheduling and execution
│   │   ├── repository.py          # Local HTTP repo management
│   │   ├── settings.py            # Credentials + HTTP IP config
│   │   ├── jobs.py                # Job tracking and SSE events
│   │   └── reports.py             # Pre-check report pages
│   ├── database/
│   │   └── models.py              # SQLite schema and model helpers
│   ├── utils/
│   │   ├── ssh_client.py          # Netmiko SSH wrapper
│   │   ├── netconf_client.py      # ncclient NETCONF wrapper
│   │   ├── precheck_engine.py     # Pre-upgrade validation engine
│   │   └── event_bus.py           # SSE event broadcasting
│   ├── static/
│   │   ├── css/style.css          # Dark theme stylesheet
│   │   └── js/
│   │       ├── app.js             # Main dashboard JS
│   │       └── repository.js      # Repository page JS
│   ├── templates/
│   │   ├── index.html             # Main dashboard
│   │   ├── repository.html        # Image repository page
│   │   └── reports_prechecks.html # Pre-check results
│   └── repo/                      # Uploaded firmware images (served on port 80)
└── deployment/
    ├── Dockerfile
    └── docker_deploy.md           # Docker deployment notes
```

---

## License

MIT
