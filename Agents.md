# Agent Notes - IOS-XE Upgrade Manager

## Project Overview

This is a **Flask-based web application** for automated Cisco IOS-XE software management. The application uses a model-driven approach with NETCONF/YANG for device communication, automated pre-checks, and one-step upgrade orchestration.

## Key Architecture Decisions

### Communication Strategy
1. **NETCONF (Primary)**: Uses `ncclient` to query YANG models for structured data
   - Device hardware inventory: `Cisco-IOS-XE-device-hardware-oper`
   - Filesystem data: `Cisco-IOS-XE-platform-software-oper`
   - Configuration: `Cisco-IOS-XE-native`

2. **SSH (Fallback)**: Uses `netmiko` for:
   - Enabling/disabling NETCONF on devices
   - ROMMON variable checks (`show romvar`)
   - Executing install commands
   - Devices without NETCONF enabled

3. **HTTP (Image Transfer)**: Flask serves images on port 80 for device downloads via `copy http://` commands

### Database Design
- **SQLite** chosen for simplicity and zero-configuration
- 4 tables: `inventory`, `repository`, `jobs`, `prechecks`
- Automatic initialization on first run
- Location: `app/database/network_inventory.db`

### Real-Time Logging
- **Server-Sent Events (SSE)** instead of WebSockets
- Rationale: Unidirectional logging, automatic reconnection, simpler implementation
- Endpoint: `GET /api/events`

## Critical Implementation Details

### Device Role Detection
The app automatically determines if a device is a **Switch** or **Router** based on PID:
- **Switches**: C9xxx, C3850, C3650 → Use `flash:` filesystem
- **Routers**: ASR, ISR, C8xxx → Use `bootflash:` filesystem

This affects:
- Filesystem queries for disk space
- Stack member detection (switches only)
- Install command filesystem parameter

### Pre-Check Engine
Four mandatory checks before upgrade:
1. **Version Comparison**: Target ≠ current version
2. **Boot Variables**: Verify `packages.conf` for Install Mode
3. **Disk Space**: Error if <1GB, Warning if <2GB (all stack members)
4. **ROMMON Flags**: Critical error if `SWITCH_IGNORE_STARTUP_CFG=1`

### One-Step Install Process
Command executed via SSH:
```bash
install add file <filesystem>:<filename> activate commit prompt-level none
```

This combines Add + Activate + Commit into a single operation, eliminating manual intervention.

## File Structure

```
/Users/codyharmon/Documents/Code/IOSXE Upgrade/
├── main.py                    # Flask app entry point
├── config.json                # Application configuration
├── requirements.txt           # Python dependencies
├── README.md                  # User documentation
├── app/
│   ├── blueprints/
│   │   ├── discovery.py       # Device discovery & NETCONF toggle
│   │   ├── repository.py      # Image upload & MD5 verification
│   │   └── upgrade.py         # Pre-checks, scheduling, SSE
│   ├── database/
│   │   └── models.py          # SQLite schema & CRUD operations
│   ├── utils/
│   │   ├── netconf_client.py  # NETCONF/YANG operations
│   │   ├── ssh_client.py      # SSH/Netmiko operations
│   │   └── precheck_engine.py # Validation logic
│   ├── static/
│   │   ├── css/style.css      # Dark-mode UI styling
│   │   └── js/app.js          # Frontend logic & SSE handling
│   └── templates/
│       └── index.html         # Main dashboard
└── deployment/
    ├── install_wsl.sh         # WSL installation script
    ├── Dockerfile             # Container image
    ├── docker-compose.yml     # Multi-container setup
    └── flake.nix              # Nix development environment
```

## Common Issues & Solutions

### Issue: Template Not Found
**Symptom**: `jinja2.exceptions.TemplateNotFound: index.html`  
**Cause**: Flask looks for templates in `templates/` relative to `main.py`, but structure uses `app/templates/`  
**Solution**: Specify custom folders in Flask init:
```python
app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')
```

### Issue: Python 3.13 Compatibility
**Symptom**: `ModuleNotFoundError: No module named 'telnetlib'`  
**Cause**: Python 3.13 removed `telnetlib`, but `netmiko 4.3.0` still imports it  
**Solution**: Upgrade to `netmiko 4.4.0` or later

### Issue: NETCONF Connection Failures
**Symptom**: Devices show "Offline" or "NETCONF Disabled"  
**Troubleshooting**:
1. Verify NETCONF is enabled: `show netconf-yang status`
2. Check port 830 is accessible
3. Verify credentials in `config.json`
4. Use SSH fallback for discovery if NETCONF unavailable

## Testing Recommendations

### Without Real Devices
1. Test UI rendering and navigation
2. Verify API endpoints return proper error messages
3. Test file upload validation (MD5, file size)
4. Confirm SSE connection establishes

### With Real Devices
1. Start with a single test device
2. Verify discovery via NETCONF
3. Test NETCONF toggle functionality
4. Run pre-checks on known-good device
5. Test upgrade on non-production device first

## Configuration

Edit `config.json` for your environment:
```json
{
  "credentials": {
    "ssh_username": "admin",
    "ssh_password": "cisco",
    "netconf_port": 830
  },
  "flask": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": true
  }
}
```

**Security Note**: Move credentials to environment variables for production use.

## Deployment Options

1. **Development**: `python main.py` (Flask dev server)
2. **WSL/Linux**: `./deployment/install_wsl.sh`
3. **Docker**: `docker-compose up -d`
4. **Nix**: `nix develop`

## Dependencies

- **Flask 3.0.0**: Web framework
- **ncclient 0.6.15**: NETCONF client
- **netmiko 4.4.0**: SSH automation (Python 3.13 compatible)
- **paramiko 3.4.0**: SSH protocol library
- **xmltodict 0.13.0**: XML parsing for NETCONF responses
- **Flask-APScheduler 1.13.1**: Job scheduling (future enhancement)

## Current Development Status

### ✅ Phase 4: Target Image Selection (COMPLETE)
**Objective**: Enable users to select target images for each device from the repository.

**Implemented Features**:
1. **UI Changes**:
   - Added "Target Image" column to device table with dropdown
   - Added "Image Status" column showing Copied/Verified badges
   - Precheck buttons work with or without target selection
   - Target image persists after running prechecks

2. **Backend**:
   - API endpoint: `POST /api/devices/<ip>/set-target`
   - Database columns: `target_image`, `image_copied`, `image_verified`
   - Fixed data persistence issue in `InventoryModel.add_device()`

3. **Bug Fixes**:
   - Fixed target image disappearing after prechecks (SQL INSERT OR REPLACE issue)
   - Ensured all three fields persist during device updates

### ✅ Phase 5: Enhanced Prechecks (COMPLETE)
**Objective**: Add advanced validation checks beyond basic version/space/boot checks.

**Implemented Checks**:
1. **NPE Image Detection** ✅:
   - Scans target filename for "NPE" or "npe" keyword
   - Displays warning: "NPE Image: Some features may be unavailable"
   - Status: WARNING (not blocking)

2. **Version Comparison** ✅:
   - Parses semantic versions (e.g., 17.9.4 vs 17.12.1)
   - Detects: Upgrade, Downgrade, or Major Jump (e.g., 16.x → 17.x)
   - Displays: "⬆️ Upgrade" / "⬇️ Downgrade" / "⚠️ Major Jump"
   - Status: INFO for upgrade, WARNING for downgrade/major jump

3. **Commit Status Check** ✅:
   - **Method** (SSH): Parses `show install summary` output
   - Looks for "C" (Committed) or "U" (Uncommitted) flag next to IMG packages
   - Displays: "✅ Committed" or "⚠️ Not Committed"
   - Status: WARNING if not committed, PASS if committed
   - Skips check for Bundle Mode devices

**Implementation Notes**:
- Version parsing uses regex: `(\d+)\.(\d+)\.(\d+)` for major.minor.patch
- Commit check runs during "Run Prechecks" action
- All checks stored in `prechecks` table with severity levels
- Fixed SSH command execution to use `ssh.connection.send_command()`

### 🚧 Phase 6: Image Copy Workflow (NEXT)
**Objective**: Copy images from local repository to devices via HTTP.

**Planned Features**:
1. **UI**: "Copy Image" button (enabled when target image selected)
2. **Backend**: `POST /api/operations/copy-image` endpoint
3. **SSH Command**: `copy http://<server>:5000/repository/download/<file> flash:<file>`
4. **Progress Tracking**: Real-time logs in event stream
5. **Status Update**: Set `image_copied = 'Yes'` on completion


## Future Enhancements

1. **APScheduler Integration**: Currently jobs run immediately; add scheduled execution
2. **Multi-Device Upgrades**: Batch upgrade multiple devices with rollback capability
3. **Rollback Functionality**: Implement `install rollback` command support
4. **ISSU Support**: Add In-Service Software Upgrade for stack switches
5. **Notification System**: Email/Slack alerts for upgrade completion/failures
6. **Audit Logging**: Track all user actions and device changes

## Related Documentation

- [IOS-XE Upgrade Manager.md](file:///Users/codyharmon/Documents/Code/IOSXE%20Upgrade/IOS-XE%20Upgrade%20Manager.md) - Original technical specification
- [README.md](file:///Users/codyharmon/Documents/Code/IOSXE%20Upgrade/README.md) - User-facing documentation
- [Walkthrough](file:///Users/codyharmon/.gemini/antigravity/brain/2fb334ff-7725-4eef-bddf-7f6c07f4fd94/walkthrough.md) - Implementation details and testing results
