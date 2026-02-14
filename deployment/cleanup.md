# Cleanup Guide (IOSXE-Upgrade-Manager)

Use this guide to completely remove the application, data, and network configurations from your system.

## 1. Remove Docker Resources (Terminal / WSL)
Run these commands in your Jumpbox terminal to delete the container, image, and all data volumes.

```bash
# Stop and remove the container
docker stop IOSXE-Upgrade-Manager
docker rm IOSXE-Upgrade-Manager

# Remove the Docker image
docker rmi iosxe-upgrade-manager:latest

# Remove all data volumes (WARNING: Deletes all database and repo data!)
docker volume rm ios-xe-db ios-xe-repo ios-xe-logs
```

## 2. Remove Network Rules (Windows PowerShell Admin)
Run these commands in **PowerShell as Administrator** to remove the port forwarding and firewall rules.

```powershell
# 1. Remove Port Forwarding Bridges
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0

# 2. Remove Firewall Rules
Remove-NetFirewallRule -DisplayName "Allow IOS-XE Repo (Port 80)" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Allow IOS-XE App (Port 5000)" -ErrorAction SilentlyContinue

Write-Host "✅ Network cleanup complete."
```
