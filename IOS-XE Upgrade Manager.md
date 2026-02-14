# **Technical Specification: Model-Driven IOS-XE Upgrade Manager**

This document provides a detailed project plan for an automated Cisco IOS-XE software management web application. The tool is designed to manage the software lifecycle for IOS-XE devices (v17.0+) using a 1-step "one-shot" install process, integrated pre-checks, and a model-driven communication backend.

## **1\. Core Architectural Strategy**

### **Backend Framework**

* **Framework:** Flask with modular Blueprints (Discovery, Repository, Upgrade, Dashboard).  
* **Concurrency:** APScheduler for task scheduling and threading for non-blocking device communication.  
* **Database:** **SQLite**. Selected for its lightweight, zero-configuration persistence across app restarts.  
* **Real-time Feedback:** **Server-Sent Events (SSE)**. SSE is the recommended choice over WebSockets for this application because upgrade logging is unidirectional (Server to Client). SSE offers built-in automatic reconnection, which is critical when tracking a device through a reload where management sessions may drop and resume.1

### **Communication Layer**

1. **SSH (Netmiko/Paramiko):** Used exclusively for bootstrapping the environment (Enabling/Disabling Netconf) and for fallback "show romvar" checks if YANG coverage is thin on certain platforms.  
2. **NETCONF (ncclient):** Primary driver for discovery and pre-checks. Leverages get operations on operational models to retrieve structured hardware and filesystem data.  
3. **HTTP (Native):** App hosts a local repository on **Port 80**. Devices pull images using copy http://\<server\>/image flash: to maximize transfer speed over XML-based alternatives.

## ---

**2\. Database Schema (SQLite)**

| Table | Fields |
| :---- | :---- |
| **Inventory** | ip\_address, hostname, serial\_number, device\_role (Switch/Router), current\_version, rommon\_version, status (Online/Offline), netconf\_state (Enabled/Disabled) |
| **Repository** | filename, md5\_expected, file\_path, upload\_date |
| **Jobs** | job\_id, target\_ip, target\_version, schedule\_time, status (Pending/Running/Success/Failed), log\_output |
| **PreChecks** | ip\_address, check\_name, result (Pass/Fail/Warn), message |

## ---

**3\. Workflow Logic: Role-Based Differentiation**

The application must automatically tag devices as **Switch** or **Router** during discovery to determine the correct filesystem and command syntax.

### **Device Identification**

* **Logic:** Query Cisco-IOS-XE-device-hardware-oper:device-hardware/device-inventory.3  
* **Switches:** Tagged if PID contains "C9" (9000s) or "C3" (3850/3650).  
  * Filesystem: flash:  
  * Stack Check: Must iterate through q-filesystem to verify space on all members (e.g., flash-1:, flash-2:).4  
* **Routers:** Tagged if PID contains "ASR", "ISR", or "C8" (8000 series).  
  * Filesystem: bootflash:.5

## ---

**4\. Pre-Check Engine Requirements**

Before the "Upgrade" button is enabled, the app must run and display the following validations:

1. **Version Comparison:** Check if target image version\!= current version.6  
2. **Boot Variable Integrity:** Ensure boot system points to packages.conf for devices currently in Install Mode.  
3. **Disk Space Thresholds:**  
   * **Error:** \< 1 GB available on target filesystem (flash: or bootflash:).  
   * **Warning:** \< 2 GB available.  
   * *Note:* Switches must pass this check for **every member** in the stack using the Cisco-IOS-XE-platform-software-oper model.4  
4. **ROMMON Flag Validation:**  
   * **Error:** If SWITCH\_IGNORE\_STARTUP\_CFG=1 is detected in ROMMON variables.7 This flag causes devices to ignore their configuration upon reboot, leading to an unmanaged state.

## ---

**5\. Upgrade Orchestration (The "1-Step" Process)**

The application implements the **One-Step Workflow** as described in Cisco documentation.8 This eliminates the need for manual Add/Activate/Commit triggers.

### **Command Execution**

The app will push the following sequence via RPC or SSH:

Bash

install add file \<filesystem\>:\<filename\> activate commit prompt-level none

### **Scheduling Logic**

* Users select a date/time in the UI.  
* **APScheduler** triggers the background thread at the designated computer time.  
* The job status updates to "Running," and the SSE log stream starts capturing the device output.

## ---

**6\. Implementation Checklist for AI Agents**

### **Functional Components**

* **Discovery Button:** Triggers a sweep of the IP list; populates SQLite with hardware/version data.  
* **Netconf Toggle:** Multi-select devices in UI to push netconf-yang or no netconf-yang via Netmiko.  
* **Clear Job/Clear All:** Resets the Jobs table or purges the entire Inventory/PreCheck DB.  
* **HTTP Repo Manager:** Handles file uploads to a local folder and serves them via Flask's static path or a dedicated http.server on port 80\.

### **Directory Structure**

/ios-xe-manager

├── app/

│ ├── blueprints/

│ │ ├── discovery.py \# Netconf discovery logic

│ │ ├── repository.py \# File upload & MD5 verification

│ │ └── upgrade.py \# Installation orchestration & scheduling

│ ├── static/ \# UI Assets

│ ├── templates/ \# HTML Templates (SSE log window)

│ ├── database/ \# network\_inventory.db

│ └── repo/ \#.bin image storage

├── deployment/

│ ├── install\_wsl.sh \# Bash script for venv/requirements

│ ├── flake.nix \# Nix environment config

│ └── docker-compose.yml \# Docker definition

├── config.json \# App-wide credentials

├── requirements.txt

└── main.py \# App entry point

## ---

**7\. Deployment Assets**

### **WSL Install Script (install\_wsl.sh)**

Bash

\#\!/bin/bash  
python3 \-m venv venv  
source venv/bin/activate  
pip install \--upgrade pip  
pip install flask flask-apscheduler ncclient netmiko xmltodict sqlite3  
export FLASK\_APP=main.py  
echo "Installation complete. Run 'flask run' to start."

### **Nix/Docker Integration**

* Use pkgs.dockerTools.buildLayeredImage to package the Python environment and Flask app into a minimal OCI-compliant container.9  
* Provide a nix config file to ensure the Python interpreter version is pinned (3.11+ recommended for ncclient stability).

#### **Works cited**

1. Streaming HTTP vs. WebSocket vs. SSE: A Comparison for Real-Time Data, accessed February 11, 2026, [https://dev.to/mechcloud\_academy/streaming-http-vs-websocket-vs-sse-a-comparison-for-real-time-data-1geo](https://dev.to/mechcloud_academy/streaming-http-vs-websocket-vs-sse-a-comparison-for-real-time-data-1geo)  
2. Implementing Server-Sent Events (SSE)Using Python Flask & React \- Ajackus, accessed February 11, 2026, [https://www.ajackus.com/blog/implement-sse-using-python-flask-and-react/](https://www.ajackus.com/blog/implement-sse-using-python-flask-and-react/)  
3. Cisco-IOS-XE-device-hardware-oper.yang \- GitHub, accessed February 11, 2026, [https://github.com/YangModels/yang/blob/main/vendor/cisco/xe/1681/Cisco-IOS-XE-device-hardware-oper.yang](https://github.com/YangModels/yang/blob/main/vendor/cisco/xe/1681/Cisco-IOS-XE-device-hardware-oper.yang)  
4. YANG Tree Cisco-IOS-XE-platform-software-oper@2022-07-01, accessed February 11, 2026, [https://www.yangcatalog.org/api/services/tree/Cisco-IOS-XE-platform-software-oper@2022-07-01.yang](https://www.yangcatalog.org/api/services/tree/Cisco-IOS-XE-platform-software-oper@2022-07-01.yang)  
5. Cisco IOS XE Upgrade 17.x | PDF \- Scribd, accessed February 11, 2026, [https://www.scribd.com/document/827144590/Cisco-IOS-XE-Upgrade-17-x](https://www.scribd.com/document/827144590/Cisco-IOS-XE-Upgrade-17-x)  
6. Current State of the Art for Declarative Cisco IOS-XE Upgrades? : r/networking \- Reddit, accessed February 11, 2026, [https://www.reddit.com/r/networking/comments/1m3854n/current\_state\_of\_the\_art\_for\_declarative\_cisco/](https://www.reddit.com/r/networking/comments/1m3854n/current_state_of_the_art_for_declarative_cisco/)  
7. cisco 3850 set to ignore startup config unable to remove SOLVED, accessed February 11, 2026, [https://community.cisco.com/t5/switching/cisco-3850-set-to-ignore-startup-config-unable-to-remove-solved/td-p/3943001](https://community.cisco.com/t5/switching/cisco-3850-set-to-ignore-startup-config-unable-to-remove-solved/td-p/3943001)  
8. Cisco IOS 26 \- IOS XE upgrade \- standalone switch, stack and ISSU \- SAMURAJ-cz.com, accessed February 11, 2026, [https://www.samuraj-cz.com/en/article/cisco-ios-26-ios-xe-upgrade-standalone-switch-stack-and-issu/](https://www.samuraj-cz.com/en/article/cisco-ios-26-ios-xe-upgrade-standalone-switch-stack-and-issu/)  
9. pkgs.dockerTools | nixpkgs, accessed February 11, 2026, [https://ryantm.github.io/nixpkgs/builders/images/dockertools/](https://ryantm.github.io/nixpkgs/builders/images/dockertools/)