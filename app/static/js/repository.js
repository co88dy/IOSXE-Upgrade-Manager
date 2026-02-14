// Repository Page JavaScript

let selectedFile = null;
let httpServerIP = '';

// Load configuration and repository on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRepoConfig();
    refreshRepository();
});

// Load repository configuration
async function loadRepoConfig() {
    try {
        const response = await fetch('/api/settings/get');
        if (response.ok) {
            const data = await response.json();
            if (data.http_server_ip) {
                document.getElementById('httpServerIP').value = data.http_server_ip;
                httpServerIP = data.http_server_ip;
            }
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Save repository configuration
async function saveRepoConfig() {
    const ip = document.getElementById('httpServerIP').value.trim();

    if (!ip) {
        showNotification('Error', 'Please enter an HTTP server IP address', '⚠️');
        return;
    }

    // Basic IP validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(ip)) {
        showNotification('Error', 'Please enter a valid IP address', '⚠️');
        return;
    }

    try {
        const response = await fetch('/api/settings/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ http_server_ip: ip })
        });

        if (response.ok) {
            httpServerIP = ip;
            showNotification('Success', 'Configuration saved successfully', '✅');
        } else {
            showNotification('Error', 'Failed to save configuration', '⚠️');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showNotification('Error', 'Failed to save configuration', '⚠️');
    }
}

// Handle file selection - Show filename inline
function handleFileSelect() {
    const fileInput = document.getElementById('fileInput');
    selectedFile = fileInput.files[0];

    if (selectedFile) {
        console.log('File selected:', selectedFile.name);

        // Show filename inline in the upload box
        const fileNameDisplay = document.getElementById('selectedFileName');
        const fileNameText = document.getElementById('fileName');
        const fileSizeText = document.getElementById('fileSize');

        if (fileNameDisplay && fileNameText && fileSizeText) {
            fileNameText.textContent = selectedFile.name;
            fileSizeText.textContent = (selectedFile.size / (1024 ** 2)).toFixed(2);
            fileNameDisplay.style.display = 'block';
        }
    }
}

// Upload image
async function uploadImage() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files || fileInput.files.length === 0) {
        showNotification('Error', 'Please select a file first', '⚠️');
        return;
    }

    const file = fileInput.files[0];
    const md5 = document.getElementById('md5Input').value.trim();

    if (!md5) {
        showNotification('Error', 'MD5 checksum is required', '⚠️');
        return;
    }

    if (md5.length !== 32) {
        showNotification('Error', 'MD5 hash must be exactly 32 characters', '⚠️');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('md5_expected', md5);

    showLoading('Uploading image and verifying MD5...');

    try {
        const response = await fetch('/api/repository/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        hideLoading();

        if (response.ok) {
            showNotification('Success', `Image uploaded successfully!<br><br>
                <strong>Filename:</strong> ${data.filename}<br>
                <strong>MD5:</strong> ${data.md5}<br>
                <strong>Size:</strong> ${(data.size_bytes / (1024 ** 2)).toFixed(2)} MB`, '✅');

            // Clear form
            document.getElementById('fileInput').value = '';
            document.getElementById('md5Input').value = '';
            selectedFile = null;

            // Hide filename display
            const fileNameDisplay = document.getElementById('selectedFileName');
            if (fileNameDisplay) {
                fileNameDisplay.style.display = 'none';
            }

            // Refresh repository list
            refreshRepository();
        } else {
            if (data.error === 'MD5 mismatch') {
                showNotification('MD5 Verification Failed', `
                    The calculated MD5 hash does not match the provided hash.<br><br>
                    <strong>Expected:</strong> ${data.expected}<br>
                    <strong>Actual:</strong> ${data.actual}<br><br>
                    Please verify the MD5 hash from Cisco's download page and try again.
                `, '❌');
            } else {
                showNotification('Error', data.error || 'Upload failed', '❌');
            }
        }
    } catch (error) {
        hideLoading();
        console.error('Upload error:', error);
        showNotification('Error', 'Failed to upload image', '❌');
    }
}

// Refresh repository list
async function refreshRepository() {
    const listEl = document.getElementById('repositoryList');
    listEl.innerHTML = '<p style="color: var(--text-muted); text-align: center;">Loading images...</p>';

    try {
        const response = await fetch('/api/repository/images');
        const data = await response.json();

        if (data.images && data.images.length > 0) {
            let html = '<div class="table-wrapper"><table class="data-table"><thead><tr>';
            html += '<th>Filename</th>';
            html += '<th>MD5 Hash</th>';
            html += '<th>Size</th>';
            html += '<th>Upload Date</th>';
            html += '<th>Actions</th>';
            html += '</tr></thead><tbody>';

            data.images.forEach(image => {
                html += '<tr>';
                html += `<td style="font-family: var(--font-mono); color: var(--accent-primary);">${image.filename}</td>`;
                html += `<td style="font-family: var(--font-mono); font-size: 0.85rem;">${image.md5_expected || image.md5_hash || 'N/A'}</td>`;
                html += `<td>${image.size_mb} MB</td>`;
                html += `<td>${new Date(image.upload_date).toLocaleString()}</td>`;
                html += `<td><button class="btn btn-error btn-sm" onclick="deleteImage('${image.filename}')">🗑️ Delete</button></td>`;
                html += '</tr>';
            });

            html += '</tbody></table></div>';

            // Show HTTP server info if configured
            if (httpServerIP) {
                html += `<div style="margin-top: 1rem; padding: 1rem; background: var(--bg-tertiary); border-radius: 8px; border: 1px solid var(--border-color);">`;
                html += `<p style="color: var(--text-secondary); margin-bottom: 0.5rem;"><strong>📡 HTTP Download URL Format:</strong></p>`;
                html += `<code style="color: var(--accent-primary); font-family: var(--font-mono);">http://${httpServerIP}/repo/&lt;filename&gt;</code>`;
                html += `</div>`;
            }

            listEl.innerHTML = html;
        } else {
            listEl.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No images uploaded yet.</p>';
        }
    } catch (error) {
        console.error('Error loading repository:', error);
        listEl.innerHTML = '<p style="color: var(--accent-error); text-align: center;">Failed to load images</p>';
    }
}

//Delete image
async function deleteImage(filename) {
    // Use custom confirmation modal from app.js
    const confirmed = await showConfirmModal(`Are you sure you want to delete ${filename}?`);

    if (!confirmed) {
        return;
    }

    showLoading('Deleting image...');

    try {
        const response = await fetch(`/api/repository/${filename}`, {
            method: 'DELETE'
        });

        hideLoading();

        if (response.ok) {
            showNotification('Success', 'Image deleted successfully', '✅');
            refreshRepository();
        } else {
            const data = await response.json();
            showNotification('Error', data.error || 'Failed to delete image', '❌');
        }
    } catch (error) {
        hideLoading();
        console.error('Delete error:', error);
        showNotification('Error', 'Failed to delete image', '❌');
    }
}
