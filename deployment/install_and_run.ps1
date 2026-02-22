# Requires "Run as Administrator"

Write-Host "=== IOS-XE Upgrade Manager: Install & Run ==="
Write-Host "---------------------------------------------"

Write-Host "`n[1/3] Configuring Windows Firewall..."
# Add Firewall rules (ignore errors if they already exist)
New-NetFirewallRule -DisplayName "Allow IOS-XE Repo (Port 80)" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Allow IOS-XE App (Port 5000)" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue | Out-Null
Write-Host "Firewall rules created."

Write-Host "`n[2/3] Configuring WSL Network Bridges..."
# Get current WSL IP
$wsl_ip = (wsl hostname -I).Trim().Split(" ")[0]

if (-not $wsl_ip) {
    Write-Host "Error: Could not determine WSL IP address. Is WSL running?" -ForegroundColor Red
    exit 1
}

# Reset Bridges (Clear old rules)
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0 | Out-Null
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0 | Out-Null

# Create Bridges (Host -> WSL)
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=5000 connectaddress=$wsl_ip
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=$wsl_ip

Write-Host "Bridges Updated!"
Write-Host "  -> Host Port 80   -> $wsl_ip : 5000 (Repo Copy)"
Write-Host "  -> Host Port 5000 -> $wsl_ip : 5000 (Web UI)"

Write-Host "`n[3/3] Pulling and running Docker image inside WSL..."
# Execute docker commands inside WSL
wsl -e bash -c "docker pull co88dy/iosxe-upgrade-manager:latest"
wsl -e bash -c "docker stop IOSXE-Upgrade-Manager > /dev/null 2>&1 ; docker rm IOSXE-Upgrade-Manager > /dev/null 2>&1"
wsl -e bash -c "docker run -d --name IOSXE-Upgrade-Manager --restart unless-stopped -p 5000:5000 -p 80:80 -v ios-xe-db:/app/app/database -v ios-xe-repo:/app/app/repo -v ios-xe-logs:/app/app/logs co88dy/iosxe-upgrade-manager:latest"

Write-Host "`n=== Deployment Complete! ===" -ForegroundColor Green
Write-Host "Access the app at http://localhost:5000 (or the host machine IP)"
Write-Host "Note: If you reboot Windows, you will need to re-run this script to update the WSL network bridge."
