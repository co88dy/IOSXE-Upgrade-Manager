# Docker Deployment Guide (IOSXE-Upgrade-Manager)

---

## Option A — Pull from Docker Hub (Recommended)
No build step required — pull the pre-built image directly.

```bash
# 1. Pull the latest image
docker pull co88dy/iosxe-upgrade-manager:latest

# 2. Cleanup any old containers (safe to skip on first run)
docker stop IOSXE-Upgrade-Manager > /dev/null 2>&1
docker rm IOSXE-Upgrade-Manager > /dev/null 2>&1

# 3. Run the container
docker run -d \
  --name IOSXE-Upgrade-Manager \
  --restart unless-stopped \
  -p 5000:5000 \
  -p 80:80 \
  -v ios-xe-db:/app/app/database \
  -v ios-xe-repo:/app/app/repo \
  -v ios-xe-logs:/app/app/logs \
  co88dy/iosxe-upgrade-manager:latest
```

Open `http://<host-ip>:5000` in your browser.

> **Updating to a new release:**
> ```bash
> docker pull co88dy/iosxe-upgrade-manager:latest
> docker stop IOSXE-Upgrade-Manager && docker rm IOSXE-Upgrade-Manager
> # Re-run the docker run command above
> ```

---

## Option B — Build from Source
If you are developing locally or need to rebuild the image, use `buildx` to ensure the image works on both ARM (Mac) and AMD64 (Jumpbox) machines.

```bash
# 1. Build and push the multi-architecture image
docker buildx build --platform linux/amd64,linux/arm64 -f deployment/Dockerfile -t co88dy/iosxe-upgrade-manager:latest --push .

# 2. Cleanup old containers (on the host extending the app)
docker stop IOSXE-Upgrade-Manager >/dev/null 2>&1
docker rm IOSXE-Upgrade-Manager >/dev/null 2>&1

# 3. Run the new container
# - Mapper Host 80 -> Container 5000 (Repo Access)
# - Mapper Host 5000 -> Container 5000 (Web UI)
docker run -d \
  --name IOSXE-Upgrade-Manager \
  --restart unless-stopped \
  -p 5000:5000 \
  -p 80:80 \
  -v ios-xe-db:/app/app/database \
  -v ios-xe-repo:/app/app/repo \
  -v ios-xe-logs:/app/app/logs \
  co88dy/iosxe-upgrade-manager:latest
```

## 2. Windows Firewall (PowerShell Admin)
If this is a new setup, you must allow traffic on Port 80 (Image Copy) and Port 5000 (Web UI).

```powershell
New-NetFirewallRule -DisplayName "Allow IOS-XE Repo (Port 80)" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Allow IOS-XE App (Port 5000)" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

## Connectivity Troubleshooting (PowerShell)
If the web UI is unreachable from other machines, or if the switch fails to pull images (I/O Error), Docker/WSL networking might be isolated to `localhost`. Run this in **Windows PowerShell (Admin)** to bridge the ports:

```powershell
# 1. Get current WSL IP
$wsl_ip = (wsl hostname -I).Trim().Split(" ")[0]

# 2. Reset Bridges (Clear old rules)
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0

# 3. Create Bridges (Host -> WSL)
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=5000 connectaddress=$wsl_ip
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=$wsl_ip

Write-Host "Bridges Updated!"
Write-Host "Host Port 80   -> $wsl_ip : 5000 (Repo Copy)"
Write-Host "Host Port 5000 -> $wsl_ip : 5000 (Web UI)"
```

*(Note: The internal WSL IP changes after a full Windows reboot, requiring this script to be re-run).*
