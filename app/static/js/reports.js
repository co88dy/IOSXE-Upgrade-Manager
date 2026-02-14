/**
 * Reports JavaScript logic
 */

document.addEventListener('DOMContentLoaded', function () {
    loadReportData();

    // Set generation time
    const now = new Date();
    document.getElementById('reportGenerationTime').textContent = `Generated on: ${now.toLocaleString()}`;
});

async function loadReportData() {
    const reportContent = document.getElementById('reportContent');

    try {
        const response = await fetch('/api/reports/prechecks/data');
        if (!response.ok) throw new Error('Failed to fetch report data');

        const data = await response.json();

        if (!data || data.length === 0) {
            reportContent.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
                    <p>No device data found in inventory.</p>
                </div>
            `;
            return;
        }

        reportContent.innerHTML = '';

        data.forEach(device => {
            const card = document.createElement('div');
            card.className = 'card device-card fade-in';

            let checksHtml = '';

            // Add Image Verification status as the first row
            const verifyResult = device.image_verified || 'No';
            const verifyStatusClass = verifyResult === 'Yes' ? 'status-pass' : 'status-warn';
            const verifyLabel = verifyResult === 'Yes' ? 'PASS' : 'WARN';
            const targetImageName = device.target_image || 'N/A';

            checksHtml += `
                <tr>
                    <td style="font-weight: 500;">Image Verification</td>
                    <td><span class="result-badge ${verifyStatusClass}">${verifyLabel}</span></td>
                    <td style="color: var(--text-secondary); font-size: 0.9rem;">Target Image: ${targetImageName}</td>
                </tr>
            `;

            if (device.checks && device.checks.length > 0) {
                device.checks.forEach(check => {
                    const statusClass = `status-${check.result.toLowerCase()}`;
                    checksHtml += `
                        <tr>
                            <td style="font-weight: 500;">${check.check_name}</td>
                            <td><span class="result-badge ${statusClass}">${check.result}</span></td>
                            <td style="color: var(--text-secondary); font-size: 0.9rem;">${check.message || ''}</td>
                        </tr>
                    `;
                });
            }

            card.innerHTML = `
                <div class="device-info">
                    <div class="device-name">🖥️ ${device.hostname} <span style="font-weight: 400; color: var(--text-muted); margin-left: 0.5rem;">(${device.ip_address})</span></div>
                    <div class="badge badge-primary">${device.role}</div>
                </div>
                <div style="padding: 0;">
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th style="width: 30%">Check</th>
                                <th style="width: 15%">Result</th>
                                <th style="width: 55%">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${checksHtml}
                        </tbody>
                    </table>
                </div>
            `;

            reportContent.appendChild(card);
        });

    } catch (error) {
        console.error('Error loading report:', error);
        reportContent.innerHTML = `
            <div style="text-align: center; padding: 3rem; color: var(--accent-error);">
                <p>⚠️ Error loading report data: ${error.message}</p>
                <button class="btn btn-secondary" onclick="loadReportData()" style="margin-top: 1rem;">Try Again</button>
            </div>
        `;
    }
}
