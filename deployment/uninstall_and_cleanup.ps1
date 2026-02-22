# Requires "Run as Administrator"

Write-Host "=== IOS-XE Upgrade Manager: Uninstall & Cleanup ==="
Write-Host "---------------------------------------------------"

Write-Host "`n[1/3] Removing Windows Firewall rules..."
Remove-NetFirewallRule -DisplayName "Allow IOS-XE Repo (Port 80)" -ErrorAction SilentlyContinue | Out-Null
Remove-NetFirewallRule -DisplayName "Allow IOS-XE App (Port 5000)" -ErrorAction SilentlyContinue | Out-Null
Write-Host "Firewall rules removed."

Write-Host "`n[2/3] Removing WSL Network Bridges..."
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0 | Out-Null
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0 | Out-Null
Write-Host "Network bridges removed."

Write-Host "`n[3/3] Stopping container and removing image inside WSL..."
wsl -e bash -c "sudo docker stop IOSXE-Upgrade-Manager > /dev/null 2>&1 ; sudo docker rm IOSXE-Upgrade-Manager > /dev/null 2>&1"
Write-Host "Container stopped and removed."

wsl -e bash -c "sudo docker rmi co88dy/iosxe-upgrade-manager:latest-amd64 co88dy/iosxe-upgrade-manager:latest-arm64 co88dy/iosxe-upgrade-manager:latest > /dev/null 2>&1"
Write-Host "Docker images removed."

Write-Host "`n[4/4] Removing Docker Volumes..."
wsl -e bash -c "sudo docker volume rm ios-xe-db ios-xe-repo ios-xe-logs > /dev/null 2>&1"
Write-Host "Volumes (database, repo, logs) removed."

Write-Host "`n=== Cleanup Complete! ===" -ForegroundColor Green
Write-Host "All firewall rules, port bridges, containers, images, and volumes have been wiped."

