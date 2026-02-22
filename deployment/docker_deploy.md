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
  -p 80:5000 \
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
  -p 80:5000 \
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
If the switch fails to connect (I/O Error), run this in **Windows PowerShell (Admin)** to fix the network bridge:

```powershell
# Get current WSL IP
$wsl_ip = (wsl hostname -I).Trim().Split(" ")[0]

# Reset Bridge (Host 80 -> WSL 5000)
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=5000 connectaddress=$wsl_ip

Write-Host "Bridge Updated: Host 80 -> $wsl_ip : 5000"
```
