// IOS-XE Upgrade Manager - Frontend JavaScript

// Global variables
// Global variables
let availableImages = [];  // Store available images for dropdowns
let activeJobsMap = new Set(); // Store IPs of devices with active/scheduled jobs

// Navigation Menu Functions
function toggleMenu() {
    const navMenu = document.getElementById('navMenu');
    const navOverlay = document.getElementById('navOverlay');

    navMenu.classList.toggle('open');
    navOverlay.classList.toggle('show');
}

function navigateTo(event, page) {
    event.preventDefault();

    // Update active link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.classList.add('active');

    // Close menu
    toggleMenu();

    // Navigate based on page
    if (page === 'repository') {
        window.location.href = '/repo';
    } else if (page === 'dashboard') {
        window.location.href = '/';
    } else if (page === 'reports') {
        window.location.href = '/reports/prechecks';
    } else if (page === 'models') {
        window.location.href = '/models';
    }
}

// Initialize SSE connection for real-time logs
let eventSource = null;
let confirmModalResolve = null;

// Custom Confirmation Modal Functions
function showConfirmModal(message) {
    return new Promise((resolve) => {
        confirmModalResolve = resolve;
        const modal = document.getElementById('confirmModal');
        const messageEl = document.getElementById('confirmMessage');
        messageEl.textContent = message;
        modal.classList.add('show');
    });
}

function closeConfirmModal(confirmed) {
    const modal = document.getElementById('confirmModal');
    modal.classList.remove('show');
    if (confirmModalResolve) {
        confirmModalResolve(confirmed);
        confirmModalResolve = null;
    }
}

// Notification Modal Functions
function showNotification(title, message, icon = 'ℹ️') {
    const modal = document.getElementById('notificationModal');
    const titleEl = document.getElementById('notificationTitle');
    const messageEl = document.getElementById('notificationMessage');
    const iconEl = document.getElementById('notificationIcon');

    if (!modal || !titleEl || !messageEl || !iconEl) {
        console.warn('Notification elements missing, logging to console:', title, message);
        return;
    }

    titleEl.textContent = title;
    iconEl.textContent = icon;
    messageEl.innerHTML = message;

    modal.classList.add('show');
}

function closeNotificationModal() {
    const modal = document.getElementById('notificationModal');
    modal.classList.remove('show');
}

// Loading Overlay Functions
function showLoading(message = 'Processing...') {
    const overlay = document.getElementById('loadingOverlay');
    const messageEl = document.getElementById('loadingMessage');
    messageEl.textContent = message;
    overlay.classList.add('show');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.remove('show');
}

// Close modals when clicking outside or pressing ESC
document.addEventListener('DOMContentLoaded', () => {
    const confirmModal = document.getElementById('confirmModal');
    const notificationModal = document.getElementById('notificationModal');

    // Click outside to close
    if (confirmModal) {
        confirmModal.addEventListener('click', (e) => {
            if (e.target === confirmModal) {
                closeConfirmModal(false);
            }
        });
    }

    if (notificationModal) {
        notificationModal.addEventListener('click', (e) => {
            if (e.target === notificationModal) {
                closeNotificationModal();
            }
        });
    }

    // ESC key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (confirmModal && confirmModal.classList.contains('show')) {
                closeConfirmModal(false);
            }
            if (notificationModal && notificationModal.classList.contains('show')) {
                closeNotificationModal();
            }
            const rescheduleModal = document.getElementById('rescheduleModal');
            if (rescheduleModal && rescheduleModal.classList.contains('show')) {
                closeRescheduleModal();
            }
        }
    });

    // Initialize Clock and Timezone
    initClockAndTimezone();
});

function initClockAndTimezone() {
    const tzSelect = document.getElementById('globalTimezone');
    const savedTz = localStorage.getItem('iosxe_timezone');

    if (savedTz && tzSelect) {
        tzSelect.value = savedTz;
    }

    if (tzSelect) {
        tzSelect.addEventListener('change', () => {
            localStorage.setItem('iosxe_timezone', tzSelect.value);
            updateClock();
        });
    }

    setInterval(updateClock, 1000);
    updateClock();
}

function updateClock() {
    const clockEl = document.getElementById('serverTime');
    const tzDisplayEl = document.getElementById('serverTimezoneDisplay');
    const tzSelect = document.getElementById('globalTimezone');

    if (!clockEl || !tzSelect) return;

    const timezone = tzSelect.value || 'UTC';

    try {
        const now = new Date();
        const dateString = now.toLocaleDateString('en-US', {
            timeZone: timezone,
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
        const timeString = now.toLocaleTimeString('en-US', {
            timeZone: timezone,
            hour12: true,
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit'
        });

        clockEl.textContent = `${dateString} ${timeString}`;
        if (tzDisplayEl) tzDisplayEl.textContent = timezone;
    } catch (e) {
        console.error('Error updating clock:', e);
        clockEl.textContent = '--:--:--';
    }
}

// Checkbox Selection Functions
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const checkboxes = document.querySelectorAll('.device-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAllCheckbox.checked);
    updateSelectedCount();
}

function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('.device-checkbox:checked');
    const count = checkboxes.length;
    const countEl = document.getElementById('selectedCount');
    const actionsBtn = document.getElementById('actionsDropdownBtn');

    countEl.textContent = `${count} device${count !== 1 ? 's' : ''} selected`;
    actionsBtn.disabled = count === 0;
}

function getSelectedDevices() {
    const checkboxes = document.querySelectorAll('.device-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// Dropdown Toggle
function toggleActionsDropdown() {
    const menu = document.getElementById('actionsDropdownMenu');
    menu.classList.toggle('show');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.querySelector('.dropdown');
    const menu = document.getElementById('actionsDropdownMenu');
    if (menu && !dropdown.contains(e.target)) {
        menu.classList.remove('show');
    }
});

// Bulk Operations
async function runPrechecks() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    showLoading(`Running prechecks on ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/prechecks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: selectedIPs })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Prechecks Complete', 'Prechecks completed successfully. Check the table for results.', '✅');
            loadInventory();
        } else {
            showNotification('Prechecks Failed', data.message || 'An error occurred', '❌');
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error running prechecks: ${error.message}`, '❌');
    }
}

// Helper to get available images from repository
async function getAvailableImages() {
    try {
        const repoResponse = await fetch('/api/repository/images');
        const repoData = await repoResponse.json();
        return repoData.images || [];
    } catch (error) {
        console.error('Error fetching available images:', error);
        return [];
    }
}

// Image Operations
async function copyImageToSelected() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    const availableImages = await getAvailableImages();
    if (availableImages.length === 0) {
        showNotification('No Images', 'No images available in repository', '⚠️');
        return;
    }

    // Determine if we need to select a global image
    // Check if all selected devices have a target image set
    // For now, let's just offer the modal to be safe/flexible

    const modalHtml = `
        <div id="copyImageModal" class="modal show">
            <div class="modal-content">
                <span class="close-btn" onclick="document.getElementById('copyImageModal').remove()">&times;</span>
                <h3>Copy Image to ${selectedIPs.length} Device(s)</h3>
                <div class="form-group">
                    <p>This will copy the <strong>per-device selected target image</strong> to each device.</p>
                    <p style="margin-top: 0.5rem; color: var(--text-muted);">Ensure you have selected the correct target image for each device in the inventory table.</p>
                </div>
                <div class="form-actions" style="justify-content: flex-end; margin-top: 1rem;">
                    <button class="btn btn-secondary" onclick="document.getElementById('copyImageModal').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="confirmCopyImage()">Start Copy</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function confirmCopyImage() {
    const selectedIPs = getSelectedDevices();

    document.getElementById('copyImageModal').remove();
    showLoading(`Starting copy operations for ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/operations/copy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip_list: selectedIPs,
                target_image: null // Enforce per-device setting
            })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Success', `${data.message}`, '✅');
            loadJobs(); // Refresh jobs table
            // Optionally switch to jobs tab or just show notification
        } else {
            showNotification('Error', data.error || 'Failed to start copy jobs', '❌');
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error starting copy: ${error.message}`, '❌');
    }
}

async function verifyImageSelected() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    const confirmed = await showConfirmModal(`Verify image checksums for ${selectedIPs.length} device(s)?\nThis will calculate MD5 on the remote devices.`);
    if (!confirmed) return;

    showLoading(`Starting verification for ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/operations/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip_list: selectedIPs,
                target_image: null // Use per-device by default for plain verification
            })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Success', `${data.message}`, '✅');
            loadJobs();
        } else {
            showNotification('Error', data.error || 'Failed to start verification jobs', '❌');
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error starting verification: ${error.message}`, '❌');
    }
}

async function toggleNetconfBulk() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    const action = await showConfirmModal('Enable or disable NETCONF? (OK = Enable, Cancel = Disable)');
    const actionStr = action ? 'enable' : 'disable';

    showLoading(`${actionStr === 'enable' ? 'Enabling' : 'Disabling'} NETCONF on ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/netconf/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: selectedIPs, action: actionStr })
        });

        const data = await response.json();
        hideLoading();
        showNotification('NETCONF Updated', `NETCONF ${actionStr}d on selected devices`, '✅');
        loadInventory();
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error toggling NETCONF: ${error.message}`, '❌');
    }
}

async function rediscoverSelected() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    showLoading(`Re-discovering ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/rediscover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: selectedIPs })
        });

        const data = await response.json();
        hideLoading();
        showNotification('Re-discovery Complete', `${selectedIPs.length} device(s) re-discovered`, '✅');
        loadInventory();
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error re-discovering devices: ${error.message}`, '❌');
    }
}



function initSSE() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/events');

    eventSource.onmessage = function (event) {
        const data = JSON.parse(event.data);

        // Helper to format timestamp as [YYYY-MM-DD HH:MM:SS]
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        const timeStr = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

        // If viewing a specific job, update its log window
        if (currentViewingJobId) {
            if (data.job_id === currentViewingJobId) {
                const contentArea = document.getElementById('logContentArea');
                const logViewer = document.getElementById('logViewer');

                if (contentArea) {
                    contentArea.innerText += `\n[${timeStr}] ${data.message}`;

                    if (logViewer) {
                        logViewer.scrollTop = logViewer.scrollHeight;
                    }
                }
            }
            // Do not update global log viewer when focused on a job
            return;
        }

        const logViewer = document.getElementById('logViewer');
        logViewer.innerHTML += `<div>[${timeStr}] ${data.message}</div>`;
        logViewer.scrollTop = logViewer.scrollHeight;
    };

    eventSource.onerror = function (error) {
        console.error('SSE Error:', error);
        setTimeout(initSSE, 5000); // Reconnect after 5 seconds
    };
}

// Device Discovery
async function discoverDevices() {
    const ipListText = document.getElementById('ipList').value;
    const ipList = ipListText.split(',').map(ip => ip.trim()).filter(ip => ip);

    if (ipList.length === 0) {
        showNotification('Input Required', 'Please enter at least one IP address', '⚠️');
        return;
    }

    showLoading(`Discovering ${ipList.length} device(s)...`);

    try {
        const response = await fetch('/api/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: ipList })
        });

        const data = await response.json();
        hideLoading();

        // Build results message
        const successful = data.results.filter(r => r.status === 'success');
        const failed = data.results.filter(r => r.status === 'failed');

        let message = `<p><strong>${successful.length} device(s) discovered successfully</strong></p>`;

        if (failed.length > 0) {
            message += `<p style="margin-top: 1rem; color: var(--accent-error);"><strong>${failed.length} device(s) failed:</strong></p><ul style="margin-top: 0.5rem;">`;
            failed.forEach(f => {
                message += `<li>${f.ip}: ${f.error || 'Unknown error'}</li>`;
            });
            message += '</ul>';
        }

        showNotification('Discovery Complete', message, successful.length > 0 ? '✅' : '❌');
        loadInventory();
    } catch (error) {
        hideLoading();
        showNotification('Discovery Error', `Error during discovery: ${error.message}`, '❌');
    }
}

async function loadInventory() {
    try {
        // Load available images first
        const repoResponse = await fetch('/api/repository/images');
        const repoData = await repoResponse.json();
        availableImages = repoData.images || [];

        const response = await fetch('/api/inventory');
        const data = await response.json();

        const tbody = document.getElementById('inventoryBody');
        const deviceSelect = document.getElementById('targetDevice');

        if (data.devices.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13" style="text-align: center; color: var(--text-muted);">No devices discovered yet.</td></tr>';
            if (deviceSelect) deviceSelect.innerHTML = '<option value="">Select a device</option>';
            return;
        }

        tbody.innerHTML = '';
        if (deviceSelect) deviceSelect.innerHTML = '<option value="">Select a device</option>';

        data.devices.forEach(device => {
            // Filter out staged devices
            if (stagedDevices.some(d => d.ip_address === device.ip_address)) {
                return;
            }

            const row = document.createElement('tr');

            // Precheck status badge
            let precheckBadge = '<span class="badge badge-secondary">Not Run</span>';
            if (device.precheck_status === 'Pass') {
                precheckBadge = `<span class="badge badge-success" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Pass</span>`;
            } else if (device.precheck_status === 'Fail') {
                precheckBadge = `<span class="badge badge-error" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Fail</span>`;
            } else if (device.precheck_status === 'Warning') {
                precheckBadge = `<span class="badge badge-warning" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Warning</span>`;
            }


            // Filter available images based on device model support
            let deviceImages = availableImages;
            if (device.image_regex) {
                try {
                    const regex = new RegExp(device.image_regex);
                    deviceImages = availableImages.filter(img => regex.test(img.filename));
                } catch (e) {
                    console.error('Invalid image regex for device:', device.ip_address, e);
                }
            }

            // Create target image dropdown
            const targetImageSelect = `<select class="target-image-select" data-ip="${device.ip_address}" onchange="setTargetImage('${device.ip_address}', this.value)" style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary); font-size: 0.85rem;">
                <option value="">Select Image...</option>
                ${deviceImages.map(img => `<option value="${img.filename}" ${device.target_image === img.filename ? 'selected' : ''}>${img.filename}</option>`).join('')}
            </select>`;

            // Image status badges
            let imageStatus = '<span class="badge badge-secondary" style="font-size: 0.75rem;">Not Selected</span>';

            if (device.image_verified === 'Yes') {
                imageStatus = '<span class="badge badge-success" style="font-size: 0.75rem;">✓ Verified</span>';
            } else if (device.image_verified === 'Failed') {
                imageStatus = '<span class="badge badge-error" style="font-size: 0.75rem;">✕ Verification Failed</span>';
            } else if (device.image_copied === 'Yes') {
                imageStatus = '<span class="badge badge-warning" style="font-size: 0.75rem;">✓ Copied (Unverified)</span>';
            } else if (device.target_image) {
                imageStatus = '<span class="badge badge-secondary" style="font-size: 0.75rem;">Not Copied</span>';
            }

            // Check for active job
            let checkboxDisabled = '';
            let rowStyle = '';
            let statusBadge = `<span class="badge badge-success">${device.status}</span>`;

            if (activeJobsMap.has(device.ip_address)) {
                checkboxDisabled = 'disabled';
                rowStyle = 'opacity: 0.6; background-color: rgba(0,0,0,0.05);';
                statusBadge = `<span class="badge badge-warning">Job Active</span>`;
            }

            row.innerHTML = `
                <td><input type="checkbox" class="device-checkbox" value="${device.ip_address}" onchange="updateSelectedCount()" ${checkboxDisabled}></td>
                <td>${device.ip_address}</td>
                <td>${device.hostname}</td>
                <td>${device.serial_number}</td>
                <td>
                    ${device.model || 'Unknown'}
                    ${device.is_supported === 'No' ? '<span title="Model not officially supported" style="cursor: help;">⚠️</span>' : ''}
                </td>
                <td>
                    ${device.current_version}
                    ${device.rommon_version ? `<div style="font-size: 0.8em; color: var(--text-muted); margin-top: 4px; font-family: monospace;">BootLdr: ${device.rommon_version}</div>` : ''}
                </td>
                <td>${targetImageSelect}</td>
                <td>${imageStatus}</td>
                <td>${statusBadge}</td>
                <td><span class="badge ${device.netconf_state === 'Enabled' ? 'badge-success' : 'badge-warning'}">${device.netconf_state}</span></td>
                <td>${device.boot_variable || 'N/A'}</td>
                <td>${device.free_space_mb !== null && device.free_space_mb !== undefined ? device.free_space_mb.toLocaleString() : 'N/A'}</td>
                <td>${precheckBadge}</td>
            `;
            if (rowStyle) row.style = rowStyle;
            tbody.appendChild(row);

            // Add to device select (if element exists)
            if (deviceSelect) {
                const option = document.createElement('option');
                option.value = device.ip_address;
                option.textContent = `${device.hostname} (${device.ip_address})`;
                option.dataset.version = device.current_version;
                deviceSelect.appendChild(option);
            }
        });

        // Reset select all checkbox
        document.getElementById('selectAllCheckbox').checked = false;
        updateSelectedCount();
    } catch (error) {
        console.error('Error loading inventory:', error);
    }
}

async function toggleNetconf(ip, currentState) {
    const action = currentState === 'Enabled' ? 'disable' : 'enable';

    try {
        const response = await fetch('/api/netconf/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: [ip], action: action })
        });

        const data = await response.json();
        alert(`NETCONF ${action}d successfully`);
        loadInventory();
    } catch (error) {
        alert('Error toggling NETCONF: ' + error.message);
    }
}

async function clearInventory(event) {
    // Prevent any default button behavior
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const confirmed = await showConfirmModal('Are you sure you want to clear all inventory?');
    if (!confirmed) return;

    showLoading('Clearing inventory...');

    try {
        await fetch('/api/inventory/clear', { method: 'DELETE' });
        showNotification('Success', 'Inventory cleared', '✅');
        loadInventory();
        // Also clear staged devices
        stagedDevices = [];
        renderStagedDevices();
    } catch (error) {
        showNotification('Error', 'Failed to clear inventory', '❌');
    } finally {
        hideLoading();
    }
}

// Upgrade Scheduler Logic
let stagedDevices = [];

function stageSelectedDevices() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device to stage for upgrade', '⚠️');
        return;
    }

    // Get current inventory data to find device objects
    // We can rely on the 'data' from loadInventory if we stored it globally, 
    // or just fetch rows from DOM. Better to fetch fresh inventory or store global.
    // Let's rely on a fetch since we don't have global inventory state.
    // Actually, simplest is to grab from DOM or wait for fetch.
    // Let's fetch inventory again to be safe and get full objects.

    fetch('/api/inventory')
        .then(response => response.json())
        .then(data => {
            const devicesToStage = data.devices.filter(d => selectedIPs.includes(d.ip_address));

            // Add to stagedDevices, avoiding duplicates
            let addedCount = 0;
            devicesToStage.forEach(device => {
                if (!stagedDevices.find(d => d.ip_address === device.ip_address)) {
                    // Enrich with default schedule info
                    device.scheduleTime = '';
                    // device.timezone  removed, using global
                    stagedDevices.push(device);
                    addedCount++;
                }
            });

            if (addedCount > 0) {
                renderStagedDevices();
                // We need to 'hide' them from the main table. 
                // The requirements said "completely remove them from the Device table".
                // Since loadInventory refills the table, we need to filter them out there too.
                loadInventory();

                // Show the scheduler section
                document.getElementById('upgradeScheduler').style.display = 'block';
                showNotification('Staged', `${addedCount} device(s) moved to Upgrade Scheduler`, '📋');
            } else {
                showNotification('Info', 'Selected devices are already staged', 'ℹ️');
            }
        })
        .catch(err => console.error('Error staging devices:', err));
}

function renderStagedDevices() {
    const tbody = document.getElementById('stagedDevicesBody');
    const container = document.getElementById('upgradeScheduler');

    if (stagedDevices.length === 0) {
        tbody.innerHTML = '';
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    tbody.innerHTML = '';

    stagedDevices.forEach((device, index) => {
        const row = document.createElement('tr');

        // Precheck status badge logic (reused)
        let precheckBadge = '<span class="badge badge-secondary">Not Run</span>';
        if (device.precheck_status === 'Pass') {
            precheckBadge = `<span class="badge badge-success" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Pass</span>`;
        } else if (device.precheck_status === 'Fail') {
            precheckBadge = `<span class="badge badge-error" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Fail</span>`;
        } else if (device.precheck_status === 'Warning') {
            precheckBadge = `<span class="badge badge-warning" style="cursor: pointer;" onclick="viewPrechecks('${device.ip_address}', '${device.hostname}')">Warning</span>`;
        }

        row.innerHTML = `
            <td>
                <input type="checkbox" class="staged-checkbox" value="${device.ip_address}">
            </td>
            <td>${device.hostname}</td>
            <td>${device.ip_address}</td>
            <td>${device.target_image || '<span class="text-warning">Not Set</span>'}</td>
            <td>${precheckBadge}</td>
            <td>
                <input type="datetime-local" class="form-control" 
                       value="${device.scheduleTime}" 
                       onchange="updateDeviceSchedule('${device.ip_address}', 'scheduleTime', this.value)">
            </td>
        `;
        tbody.appendChild(row);
    });
}

function toggleSelectAllStaged() {
    const selectAllCheck = document.getElementById('selectAllStaged');
    const checkboxes = document.querySelectorAll('.staged-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAllCheck.checked);
}

function getSelectedStaged() {
    const checkboxes = document.querySelectorAll('.staged-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function updateDeviceSchedule(ip, field, value) {
    const device = stagedDevices.find(d => d.ip_address === ip);
    if (device) {
        device[field] = value;
    }
}

function removeFromStage(ip) {
    stagedDevices = stagedDevices.filter(d => d.ip_address !== ip);
    renderStagedDevices();
    loadInventory(); // They will reappear in main table
}

function removeFromStageSelected() {
    const selectedIPs = getSelectedStaged();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select devices to remove from stage', '⚠️');
        return;
    }

    stagedDevices = stagedDevices.filter(d => !selectedIPs.includes(d.ip_address));
    renderStagedDevices();
    loadInventory();

    // Hide scheduler if empty
    if (stagedDevices.length === 0) {
        document.getElementById('upgradeScheduler').style.display = 'none';
    }

    showNotification('Removed', `${selectedIPs.length} device(s) removed from stage`, '🗑️');
}

function toggleSchedulerDropdown() {
    const menu = document.getElementById('schedulerDropdownMenu');
    menu.classList.toggle('show');
}

// Close scheduler dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdownBtn = document.querySelector('button[onclick="toggleSchedulerDropdown()"]');
    const menu = document.getElementById('schedulerDropdownMenu');
    if (menu && dropdownBtn && !dropdownBtn.contains(e.target) && !menu.contains(e.target)) {
        menu.classList.remove('show');
    }
});

async function runStagedPrechecks() {
    const selectedIPs = getSelectedStaged();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select devices to run pre-checks on', '⚠️');
        return;
    }

    showLoading(`Running prechecks for ${selectedIPs.length} staged device(s)...`);

    try {
        const response = await fetch('/api/prechecks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: selectedIPs })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Prechecks Complete', 'Prechecks completed. Updating status...', '✅');
            // We need to refresh the status of staged devices
            await refreshStagedDevicesStatus();
        } else {
            showNotification('Prechecks Failed', data.message || 'An error occurred', '❌');
            await refreshStagedDevicesStatus(); // Update anyway in case some finished
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error running prechecks: ${error.message}`, '❌');
    }
}

async function refreshStagedDevicesStatus() {
    try {
        const response = await fetch('/api/inventory');
        const data = await response.json();

        stagedDevices.forEach(staged => {
            const fresh = data.devices.find(d => d.ip_address === staged.ip_address);
            if (fresh) {
                staged.precheck_status = fresh.precheck_status;
            }
        });
        renderStagedDevices();
    } catch (e) {
        console.error("Failed to refresh staged status", e);
    }
}

function clearStagedDevices() {
    stagedDevices = [];
    renderStagedDevices();
    loadInventory();
}

async function processImmediateUpgrades() {
    const selectedIPs = getSelectedStaged();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select devices to upgrade now', '⚠️');
        return;
    }

    // Filter stagedDevices to only selected ones
    const devicesToUpgrade = stagedDevices.filter(d => selectedIPs.includes(d.ip_address));

    // Check pre-checks
    const failedPrechecks = devicesToUpgrade.filter(d => d.precheck_status !== 'Pass');
    let confirmMessage = `IMMEDIATELY upgrade ${devicesToUpgrade.length} selected device(s)?`;

    if (failedPrechecks.length > 0) {
        confirmMessage = `⚠️ WARNING: ${failedPrechecks.length} device(s) have NOT passed pre-checks.\n\nAre you sure you want to proceed?`;
    }

    const confirmed = await showConfirmModal(confirmMessage);
    if (!confirmed) return;

    // Force scheduleTime to empty string for immediate execution
    devicesToUpgrade.forEach(d => d.scheduleTime = '');

    // Use the same batch execution function which now has error handling
    await executeUpgradeBatch(devicesToUpgrade);
}

async function processStagedUpgrades() {
    const selectedIPs = getSelectedStaged();

    // Fallback: if none selected, warn user? Or do all? 
    // User requirement: "when confirm and schedule is clicked it will tag the device as scheduled" (implying selection)
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select devices to schedule', '⚠️');
        return;
    }

    const devicesToUpgrade = stagedDevices.filter(d => selectedIPs.includes(d.ip_address));

    // Check if any devices have missing images
    const missingImage = devicesToUpgrade.find(d => !d.target_image);
    if (missingImage) {
        showNotification('Error', `Device ${missingImage.hostname} has no Target Image set.`, '❌');
        return;
    }

    // Check for pre-checks
    const failedPrechecks = devicesToUpgrade.filter(d => d.precheck_status !== 'Pass');
    let confirmMessage = `Schedule/Run upgrades for ${devicesToUpgrade.length} selected device(s)?`;

    if (failedPrechecks.length > 0) {
        confirmMessage = `⚠️ WARNING: ${failedPrechecks.length} device(s) have NOT passed pre-checks.\n\nAre you sure you want to proceed?`;
    }

    const confirmed = await showConfirmModal(confirmMessage);
    if (!confirmed) return;

    await executeUpgradeBatch(devicesToUpgrade);
}

async function executeUpgradeBatch(devices) {
    showLoading('Processing upgrades...');

    let successCount = 0;
    let failCount = 0;

    for (const device of devices) {
        try {
            const payload = {
                ip_address: device.ip_address,
                target_version: device.target_image,
                image_filename: device.target_image,
                schedule_time: device.scheduleTime || null,
                timezone: localStorage.getItem('iosxe_timezone') || 'UTC'
            };

            const response = await fetch('/api/upgrade/schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                successCount++;
            } else {
                const errorData = await response.json();
                console.error(`Failed to schedule ${device.ip_address}:`, errorData);
                showNotification('Error', `Failed ${device.ip_address}: ${errorData.error || 'Unknown error'}`, '❌');
                failCount++;
            }
        } catch (e) {
            failCount++;
            console.error(e);
            showNotification('Error', `Exception for ${device.ip_address}: ${e.message}`, '❌');
        }
    }

    hideLoading();

    if (successCount > 0) {
        showNotification('Success', `Successfully scheduled/started ${successCount} upgrades.`, '✅');
        // Clear successfull staged devices
        // We need to identify which succeeded. 
        // For now, let's reload inventory to be safe.
        // Ideally we remove only success ones from stagedDevices.
        // But since we loop, we can't easily filter in-place without tracking.
        // Let's just clear all if all success, or let user remove failed ones.
        // Simple approach: unstage all? No, failed ones should stay.

        // Since we didn't track individual success in the array, let's just refresh.
        // Future improvement: track status per row.

        // If all succeeded, clear stage
        if (failCount === 0) {
            stagedDevices = [];
            renderStagedDevices();
            loadInventory();
        }
    }

    // REMOVED generic warning block here to avoid masking errors
}

// Repository Management
async function uploadImage() {
    const fileInput = document.getElementById('fileInput');
    const md5Input = document.getElementById('md5Input');
    const file = fileInput.files[0];

    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    if (md5Input.value) {
        formData.append('md5_expected', md5Input.value);
    }

    try {
        const response = await fetch('/api/repository/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Image uploaded successfully!\nMD5: ${data.md5}`);
            md5Input.value = '';
            fileInput.value = '';
            refreshRepository();
        } else {
            alert('Upload failed: ' + data.error);
        }
    } catch (error) {
        alert('Error uploading image: ' + error.message);
    }
}

async function refreshRepository() {
    try {
        const response = await fetch('/api/repository/images');
        const data = await response.json();

        const repoList = document.getElementById('repositoryList');
        const imageSelect = document.getElementById('targetImage');

        if (data.images.length === 0) {
            repoList.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No images uploaded yet.</p>';
            imageSelect.innerHTML = '<option value="">Select an image</option>';
            return;
        }

        repoList.innerHTML = '';
        imageSelect.innerHTML = '<option value="">Select an image</option>';

        data.images.forEach(image => {
            const div = document.createElement('div');
            div.style.cssText = 'padding: 1rem; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;';
            div.innerHTML = `
                <div>
                    <strong>${image.filename}</strong><br>
                    <small style="color: var(--text-muted);">MD5: ${image.md5_expected} | Size: ${image.size_mb} MB</small>
                </div>
                <button class="btn btn-danger" onclick="deleteImage('${image.filename}')">Delete</button>
            `;
            repoList.appendChild(div);

            // Add to image select
            const option = document.createElement('option');
            option.value = image.filename;
            option.textContent = image.filename;
            imageSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading repository:', error);
    }
}

async function deleteImage(filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
        await fetch(`/api/repository/${filename}`, { method: 'DELETE' });
        alert('Image deleted');
        refreshRepository();
    } catch (error) {
        alert('Error deleting image: ' + error.message);
    }
}

// Pre-Checks
async function viewPrechecks(ip, hostname) {
    const modal = document.getElementById('precheckModal');
    const title = document.getElementById('precheckModalTitle');
    const body = document.getElementById('precheckModalBody');

    title.textContent = `Pre-Checks for ${hostname} (${ip})`;
    body.innerHTML = '<div class="spinner"></div> Loading results...';
    modal.classList.add('show');

    try {
        const response = await fetch(`/api/prechecks/${ip}`);
        const data = await response.json();

        let contentHtml = '';

        // Add Device Info Summary
        if (data.device) {
            const dev = data.device;
            let statusBadge = '<span class="badge badge-secondary">Unknown</span>';

            if (dev.image_verified === 'Yes') {
                statusBadge = '<span class="badge badge-success">✓ Verified</span>';
            } else if (dev.image_verified === 'Failed') {
                statusBadge = '<span class="badge badge-error">✕ Verification Failed</span>';
            } else if (dev.image_copied === 'Yes') {
                statusBadge = '<span class="badge badge-warning">✓ Copied (Unverified)</span>';
            } else {
                statusBadge = '<span class="badge badge-secondary">Not Copied</span>';
            }

            contentHtml += `
                <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; border: 1px solid var(--border-color);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="color: var(--text-muted); font-size: 0.85em;">Target Image</span><br>
                            <span style="font-family: monospace; font-weight: bold;">${dev.target_image || 'None Selected'}</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="color: var(--text-muted); font-size: 0.85em;">Status</span><br>
                            ${statusBadge}
                        </div>
                    </div>
                </div>
            `;
        }

        if (data.checks && data.checks.length > 0) {
            let html = '<table class="info-table" style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr><th>Check Name</th><th>Result</th><th>Message</th></tr></thead><tbody>';

            data.checks.forEach(check => {
                const badgeClass = check.result === 'PASS' ? 'badge-success' :
                    check.result === 'FAIL' ? 'badge-error' : 'badge-warning';

                html += `
                    <tr style="border-bottom: 1px solid #333;">
                        <td style="padding: 8px;">${check.check_name}</td>
                        <td style="padding: 8px;"><span class="badge ${badgeClass}">${check.result}</span></td>
                        <td style="padding: 8px; white-space: pre-wrap; font-family: monospace; font-size: 0.9em; max-height: 300px; overflow-y: auto; display: block;">${check.message || '-'}</td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            contentHtml += html;
        } else {
            contentHtml += '<p>No pre-check results found.</p>';
        }

        body.innerHTML = contentHtml;
    } catch (error) {
        body.innerHTML = `<p style="color: var(--accent-error);">Error loading pre-checks: ${error.message}</p>`;
    }
}

function closePrecheckModal() {
    document.getElementById('precheckModal').classList.remove('show');
}

// Close modal when clicking outside
window.onclick = function (event) {
    const modal = document.getElementById('precheckModal');
    if (event.target === modal) {
        closePrecheckModal();
    }
}
async function runPreChecks() {
    const deviceIP = document.getElementById('targetDevice').value;
    const targetVersion = document.getElementById('targetVersion').value;

    if (!deviceIP || !targetVersion) {
        alert('Please select a device and enter target version');
        return;
    }

    try {
        const response = await fetch('/api/precheck', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip_address: deviceIP,
                target_version: targetVersion
            })
        });

        const data = await response.json();

        const resultsDiv = document.getElementById('precheckResults');
        resultsDiv.innerHTML = '<h4 style="margin-bottom: 0.5rem;">Pre-Check Results:</h4>';

        data.results.forEach(result => {
            const badgeClass = result.result === 'PASS' ? 'badge-success' :
                result.result === 'WARN' ? 'badge-warning' : 'badge-error';

            resultsDiv.innerHTML += `
                <div style="padding: 0.75rem; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 0.5rem;">
                    <strong>${result.check_name}</strong>
                    <span class="badge ${badgeClass}" style="float: right;">${result.result}</span>
                    <br>
                    <small style="color: var(--text-secondary);">${result.message}</small>
                </div>
            `;
        });

        // Enable upgrade button if all checks passed
        const upgradeBtn = document.getElementById('upgradeBtn');
        upgradeBtn.disabled = !data.all_passed;

        if (data.all_passed) {
            upgradeBtn.classList.remove('btn-secondary');
            upgradeBtn.classList.add('btn-primary');
        }
    } catch (error) {
        alert('Error running pre-checks: ' + error.message);
    }
}

// Upgrade Scheduling
async function scheduleUpgrade() {
    const deviceIP = document.getElementById('targetDevice').value;
    const targetVersion = document.getElementById('targetVersion').value;
    const imageFilename = document.getElementById('targetImage').value;

    if (!deviceIP || !targetVersion || !imageFilename) {
        alert('Please fill all fields');
        return;
    }

    if (!confirm(`Start upgrade for ${deviceIP} to version ${targetVersion}?`)) return;

    try {
        const response = await fetch('/api/upgrade/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip_address: deviceIP,
                target_version: targetVersion,
                image_filename: imageFilename
            })
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Upgrade job created! Job ID: ${data.job_id}`);
            loadJobs();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error scheduling upgrade: ' + error.message);
    }
}

// Jobs Management
async function loadJobs() {
    try {
        const response = await fetch('/api/jobs');
        const data = await response.json();

        const tbody = document.getElementById('jobsBody');
        if (!tbody) return; // Exit if not on dashboard

        if (data.jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No jobs scheduled yet.</td></tr>';
            return;
        }

        tbody.innerHTML = '';

        activeJobsMap.clear();

        data.jobs.forEach(job => {
            // Update active jobs map
            if (job.status === 'Pending' || job.status === 'Running' || job.status === 'Scheduled') {
                activeJobsMap.add(job.target_ip);
            }

            const row = document.createElement('tr');
            const badgeClass = job.status === 'Success' ? 'badge-success' :
                job.status === 'Failed' ? 'badge-error' :
                    job.status === 'Running' ? 'badge-warning' : 'badge-info';

            row.innerHTML = `
                <td>
                    <a href="#" onclick="viewJobLogs('${job.job_id}'); return false;" style="color: var(--accent-primary); text-decoration: none; font-family: monospace;">
                        ${job.job_id.substring(0, 8)}...
                    </a>
                </td>
                <td><span class="badge badge-info">${job.job_type || 'UPGRADE'}</span></td>
                <td>${job.hostname || 'N/A'}</td>
                <td>${job.target_ip}</td>
                <td>${job.target_version}</td>
                <td><span class="badge ${badgeClass}">${job.status}</span></td>
                <td>${new Date(job.created_at).toLocaleString()}</td>
                <td>${job.end_time ? new Date(job.end_time).toLocaleString() : '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // Split jobs for Scheduled Table
        renderScheduledJobs(data.jobs);
    } catch (error) {
        console.error('Error loading jobs:', error);
    }
}

async function pollJobLogs() {
    if (!currentViewingJobId) return;

    try {
        const response = await fetch(`/api/jobs/${currentViewingJobId}`);
        const data = await response.json();

        if (data.success) {
            const job = data.job;
            const contentArea = document.getElementById('logContentArea');
            const statusBadge = document.getElementById('jobStatusBadge');
            const logViewer = document.getElementById('logViewer');

            if (contentArea) {
                // Only update if content changed to avoid jitter, or just update
                if (contentArea.innerText !== (job.log_content || 'No logs available.')) {
                    contentArea.innerText = job.log_content || 'No logs available.';
                    // Auto-scroll to bottom
                    logViewer.scrollTop = logViewer.scrollHeight;
                }
            }

            if (statusBadge) {
                statusBadge.textContent = job.status;
                statusBadge.className = `badge ${job.status === 'RUNNING' ? 'badge-warning' :
                    job.status === 'COMPLETED' ? 'badge-success' :
                        job.status === 'FAILED' ? 'badge-error' : 'badge-info'}`;
            }

            // Stop polling if done
            if (job.status !== 'RUNNING' && job.status !== 'PENDING') {
                if (logPollingInterval) {
                    clearInterval(logPollingInterval);
                    logPollingInterval = null;
                }
            }
        }
    } catch (error) {
        console.error('Error polling logs:', error);
    }
}

// Settings - Load and Save Credentials
async function loadCredentials() {
    try {
        const response = await fetch('/api/settings/credentials');
        const data = await response.json();

        document.getElementById('username').value = data.username || '';
        document.getElementById('netconfPort').value = data.netconf_port || 830;
        // Don't populate passwords for security
    } catch (error) {
        console.error('Error loading credentials:', error);
    }
}

async function saveCredentials() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const enablePassword = document.getElementById('enablePassword').value;
    const netconfPort = document.getElementById('netconfPort').value;

    if (!username || !password) {
        showStatus('settingsStatus', 'Please enter both username and password', 'error');
        return;
    }

    try {
        const response = await fetch('/api/settings/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                password: password,
                enable_password: enablePassword,
                netconf_port: parseInt(netconfPort)
            })
        });

        const data = await response.json();

        if (response.ok) {
            showStatus('settingsStatus', '✅ Credentials saved successfully', 'success');
            // Clear password fields after saving
            document.getElementById('password').value = '';
            document.getElementById('enablePassword').value = '';
        } else {
            showStatus('settingsStatus', `❌ Error: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus('settingsStatus', `❌ Error saving credentials: ${error.message}`, 'error');
    }
}

function showStatus(elementId, message, type) {
    const statusDiv = document.getElementById(elementId);
    statusDiv.textContent = message;
    statusDiv.style.color = type === 'success' ? '#10b981' : '#ef4444';

    // Clear after 5 seconds
    setTimeout(() => {
        statusDiv.textContent = '';
    }, 5000);
}

// Job Management Globals

let currentViewingJobId = null;
let logPollingInterval = null;

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    loadCredentials();
    loadInventory();
    refreshRepository();
    loadJobs();
    initSSE();

    // Refresh jobs every 5 seconds
    setInterval(loadJobs, 5000);


});



// Log Viewer Functions
function viewJobLogs(jobId) {
    currentViewingJobId = jobId;
    const logViewer = document.getElementById('logViewer');

    // Clear current content if it's a new job or just append header
    logViewer.innerHTML = `<div style="color: var(--accent-primary); border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 5px;">
        Viewing Logs for Job: ${jobId} <span id="jobStatusBadge" class="badge badge-info">LOADING</span>
    </div><div id="logContentArea" style="white-space: pre-wrap; font-family: monospace;">Loading logs...</div>`;

    // Scroll to bottom
    logViewer.scrollTop = logViewer.scrollHeight;

    // Start polling logs
    if (logPollingInterval) clearInterval(logPollingInterval);
    pollJobLogs(); // Immediate call
    logPollingInterval = setInterval(pollJobLogs, 2000);
}

// Alias for backward compatibility if needed, or update call sites
const showJob = viewJobLogs;

async function pollJobLogs() {
    if (!currentViewingJobId) return;

    try {
        const response = await fetch(`/api/jobs/${currentViewingJobId}`);
        const data = await response.json();

        if (data.success) {
            const job = data.job;
            const contentArea = document.getElementById('logContentArea');
            const statusBadge = document.getElementById('jobStatusBadge');

            if (contentArea) {
                contentArea.innerText = job.log_content || 'No logs available.';
            }

            if (statusBadge) {
                statusBadge.textContent = job.status;
                statusBadge.className = `badge ${job.status === 'RUNNING' ? 'badge-warning' :
                    job.status === 'COMPLETED' ? 'badge-success' :
                        job.status === 'FAILED' ? 'badge-error' : 'badge-info'}`;
            }

            // Stop polling if done
            if (job.status !== 'RUNNING' && job.status !== 'PENDING') {
                if (logPollingInterval) {
                    clearInterval(logPollingInterval);
                    logPollingInterval = null;
                }
            }
        }
    } catch (error) {
        console.error('Error polling logs:', error);
    }
}

// No longer using modal for logs, but keeping close function just in case
function closeLogModal() {
    // Stop polling
    if (logPollingInterval) {
        clearInterval(logPollingInterval);
        logPollingInterval = null;
    }
    currentViewingJobId = null;
}


// Updated installRemoveInactive to support async jobs
async function installRemoveInactive() {
    const selectedIPs = getSelectedDevices();
    if (selectedIPs.length === 0) {
        showNotification('No Selection', 'Please select at least one device', '⚠️');
        return;
    }

    const confirmed = await showConfirmModal(`Run "install remove inactive" on ${selectedIPs.length} device(s)?`);
    if (!confirmed) return;

    showLoading(`Starting job on ${selectedIPs.length} device(s)...`);

    try {
        const response = await fetch('/api/install-remove-inactive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_list: selectedIPs })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Jobs Started', `Started ${data.results.length} jobs. Check "Active Job" column or Logs.`, '✅');
            // Immediate update

            loadJobs();
        } else {
            showNotification('Error', data.message || 'Failed to start jobs', '❌');
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error starting command: ${error.message}`, '❌');
    }
}

// Set target image for a device
async function setTargetImage(ip, targetImage) {
    if (!targetImage) {
        // User selected "Select Image..." - clear target
        targetImage = '';
    }

    try {
        const response = await fetch(`/api/devices/${ip}/set-target`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_image: targetImage })
        });

        const data = await response.json();

        if (response.ok) {
            showNotification('Success', `Target image ${targetImage ? 'set' : 'cleared'} for ${ip}`, '✅');
            loadInventory();  // Refresh to show updated status
        } else {
            showNotification('Error', data.error || 'Failed to set target image', '❌');
        }
    } catch (error) {
        console.error('Error setting target image:', error);
        showNotification('Error', 'Failed to set target image', '❌');
    }
}

// Scheduled Jobs Logic
function renderScheduledJobs(allJobs) {
    const container = document.getElementById('scheduledJobsContainer');
    const tbody = document.getElementById('scheduledJobsBody');

    if (!container || !tbody) return;

    // Filter for scheduled/pending jobs
    const scheduledJobs = allJobs.filter(job => job.status === 'Pending' || job.status === 'Scheduled');

    if (scheduledJobs.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    tbody.innerHTML = '';

    scheduledJobs.forEach(job => {
        const row = document.createElement('tr');
        // Format date for display
        const scheduleDate = job.schedule_time ? new Date(job.schedule_time).toLocaleString() : 'Not Set';

        row.innerHTML = `
            <td><span style="font-family: monospace;">${job.job_id.substring(0, 8)}...</span></td>
            <td><span class="badge badge-info">${job.job_type || 'UPGRADE'}</span></td>
            <td>${job.hostname || 'N/A'}</td>
            <td>${job.target_ip}</td>
            <td>${job.target_version}</td>
            <td><span class="badge badge-warning">${job.status}</span></td>
            <td>${scheduleDate}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="rescheduleJob('${job.job_id}', '${job.schedule_time}')" title="Edit Schedule">📅 Edit</button>
                <button class="btn btn-sm btn-danger" onclick="cancelJob('${job.job_id}')" title="Cancel Job">❌ Cancel</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function cancelJob(jobId) {
    const confirmed = await showConfirmModal('Are you sure you want to CANCEL this scheduled job?');
    if (!confirmed) return;

    try {
        const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showNotification('Success', 'Job cancelled successfully', '✅');
            loadJobs(); // Refresh
        } else {
            showNotification('Error', data.message || 'Failed to cancel job', '❌');
        }
    } catch (error) {
        showNotification('Error', `Error cancelling job: ${error.message}`, '❌');
    }
}

function rescheduleJob(jobId, currentSchedule) {
    const modal = document.getElementById('rescheduleModal');
    const input = document.getElementById('rescheduleTimeInput');
    const idInput = document.getElementById('rescheduleJobId');

    if (!modal || !input || !idInput) return;

    idInput.value = jobId;

    // Format current schedule for datetime-local input (YYYY-MM-DDTHH:MM)
    if (currentSchedule && currentSchedule !== 'null') {
        try {
            // Assume currentSchedule is ISO-like or from DB
            const date = new Date(currentSchedule);
            // specific format for datetime-local needing local ISO
            const iso = new Date(date.getTime() - (date.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
            input.value = iso;
        } catch (e) {
            input.value = '';
        }
    } else {
        input.value = '';
    }

    modal.classList.add('show');
}

function closeRescheduleModal() {
    const modal = document.getElementById('rescheduleModal');
    if (modal) modal.classList.remove('show');
}

async function saveReschedule() {
    const jobId = document.getElementById('rescheduleJobId').value;
    const newTime = document.getElementById('rescheduleTimeInput').value;

    if (!jobId || !newTime) {
        showNotification('Input Error', 'Please select a valid time', '⚠️');
        return;
    }

    showLoading('Updating schedule...');

    try {
        const response = await fetch(`/api/jobs/${jobId}/reschedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                schedule_time: newTime,
                timezone: localStorage.getItem('iosxe_timezone') || 'UTC'
            })
        });
        const data = await response.json();
        hideLoading();

        if (data.success) {
            showNotification('Success', 'Job rescheduled successfully', '✅');
            closeRescheduleModal();
            loadJobs();
        } else {
            showNotification('Error', data.message || 'Failed to reschedule job', '❌');
        }
    } catch (error) {
        hideLoading();
        showNotification('Error', `Error rescheduling job: ${error.message}`, '❌');
    }
}

/**
 * Download the Prechecks PDF Report
 */
async function downloadPrechecksReport() {
    showLoading('Generating Prechecks Report...');

    try {
        const response = await fetch('/api/reports/prechecks/pdf');

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to generate report');
        }

        // Get the binary data
        const blob = await response.blob();

        // Create a temporary link and trigger download
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        // Extract filename from header if possible, or use default
        // Generate a fallback filename with timestamp
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '_');
        let filename = `Precheck_Report_${timestamp}.pdf`;
        const contentDisposition = response.headers.get('Content-Disposition');

        console.log('Content-Disposition header:', contentDisposition);

        if (contentDisposition) {
            // regex to extract filename with handling for potentially quoted or parameter-rich values
            const match = contentDisposition.match(/filename\*?=['"]?(?:UTF-8'')?([^'"]+)['"]?/i);
            if (match && match[1]) {
                try {
                    filename = decodeURIComponent(match[1]);
                } catch (e) {
                    filename = match[1];
                }
            }
        }

        // Clean up filename and ensure .pdf extension
        filename = filename.replace(/["']/g, '').split(/[\\/]/).pop();
        if (!filename.toLowerCase().endsWith('.pdf')) {
            filename += '.pdf';
        }

        console.log('Triggering download for:', filename);
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        // Wait 3 seconds before revoking URL to be safe
        setTimeout(() => {
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }, 3000);

        hideLoading();
        showNotification('Success', 'Report downloaded successfully', '✅');
    } catch (error) {
        hideLoading();
        console.error('Error downloading report:', error);
        showNotification('Error', `Failed to download report: ${error.message}`, '❌');
    }
}
