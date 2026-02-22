"""
Reports blueprint for generating downloadable PDF reports
"""

from flask import Blueprint, send_file, request, jsonify, render_template
from app.database.models import InventoryModel, PreChecksModel
from app.extensions import db, get_config
from fpdf import FPDF
import json
import os
import io
from datetime import datetime

reports_bp = Blueprint('reports', __name__)

# Load config
config = get_config()

@reports_bp.route('/reports/prechecks')
def view_prechecks_report():
    """
    Render the web view for prechecks report
    """
    return render_template('reports_prechecks.html')

@reports_bp.route('/reports/detailed')
def view_detailed_report():
    """
    Render the web view for the detailed device report
    """
    return render_template('report.html')

@reports_bp.route('/api/reports/prechecks/data')
def get_prechecks_report_data():
    """
    Get all prechecks data for all devices as JSON
    """
    try:
        devices = InventoryModel.get_all_devices(db)
        report_data = []
        
        for device in devices:
            ip = device.get('ip_address')
            checks = PreChecksModel.get_checks_for_device(db, ip)
            report_data.append({
                'hostname': device.get('hostname', 'Unknown'),
                'ip_address': ip,
                'status': device.get('status', 'Unknown'),
                'role': device.get('role', 'Unknown'),
                'image_verified': device.get('image_verified', 'No'),
                'target_image': device.get('target_image', 'N/A'),
                'checks': checks
            })
            
        return jsonify(report_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

class PrecheckPDF(FPDF):
    def header(self):
        # Logo placeholder (if any)
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'IOS-XE Upgrade Manager - Pre-Check Report', border=True, ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C')

def sanitize_text(text):
    """
    Remove characters that are not supported by standard PDF fonts (like emojis)
    """
    if not text:
        return ""
    # Standard fonts only support a limited set of characters (Latin-1/WinAnsi)
    # We'll encode/decode with ignore to strip everything else
    try:
        return text.encode('latin-1', 'ignore').decode('latin-1')
    except Exception:
        return "".join(c for c in text if ord(c) < 256)

@reports_bp.route('/api/reports/prechecks/pdf', methods=['GET'])
def download_prechecks_pdf():
    """
    Generate and download a PDF report of all device pre-checks
    """
    try:
        devices = InventoryModel.get_all_devices(db)
        
        pdf = PrecheckPDF()
        pdf.add_page()
        
        if not devices:
            pdf.set_font('helvetica', '', 12)
            pdf.cell(0, 10, 'No devices found in inventory.', ln=True)
        else:
            for device in devices:
                ip = sanitize_text(device.get('ip_address'))
                hostname = sanitize_text(device.get('hostname', 'Unknown'))
                
                # Device Header
                pdf.set_font('helvetica', 'B', 12)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(0, 10, f'Device: {hostname} ({ip})', ln=True, fill=True)
                
                # Check results
                checks = PreChecksModel.get_checks_for_device(db, ip)
                
                # Add Image Verification Row as the first custom check if target image exists
                target_img = sanitize_text(device.get('target_image', 'N/A'))
                is_verified = device.get('image_verified', 'No')
                
                # Table Header
                pdf.set_font('helvetica', 'B', 10)
                pdf.cell(60, 8, 'Check Name', border=1)
                pdf.cell(30, 8, 'Result', border=1)
                pdf.cell(100, 8, 'Message', border=1, ln=True)
                
                # Image Verification Row
                pdf.set_font('helvetica', '', 9)
                pdf.cell(60, 7, 'Image Verification', border=1)
                
                res_color = (0, 128, 0) if is_verified == 'Yes' else (165, 42, 42)
                pdf.set_text_color(*res_color)
                pdf.cell(30, 7, 'PASS' if is_verified == 'Yes' else 'WARN', border=1)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(100, 7, f'Target Image: {target_img}', border=1, ln=True)
                
                if not checks:
                    # Message if no other checks
                    pdf.set_font('helvetica', 'I', 9)
                    pdf.cell(0, 7, '   No additional pre-check results available.', ln=True)
                else:
                    # Table Body (Remaining Checks)
                    pdf.set_font('helvetica', '', 9)
                    for check in checks:
                        name = sanitize_text(check.get('check_name', ''))
                        result = sanitize_text(check.get('result', ''))
                        message = sanitize_text(check.get('message', '')).replace('\n', ' ')
                        
                        if len(message) > 60:
                            message = message[:57] + "..."
                            
                        pdf.cell(60, 7, name, border=1)
                        
                        if result == 'PASS':
                            pdf.set_text_color(0, 128, 0)
                        elif result in ['FAIL', 'ERROR']:
                            pdf.set_text_color(255, 0, 0)
                        else:
                            pdf.set_text_color(165, 42, 42)
                            
                        pdf.cell(30, 7, result, border=1)
                        pdf.set_text_color(0, 0, 0)
                        pdf.cell(100, 7, message, border=1, ln=True)
                
                pdf.ln(10)
                
                # Check for page break
                if pdf.get_y() > 250:
                    pdf.add_page()

        # Output to buffer (fpdf2 returns bytes by default)
        pdf_output = pdf.output()
        if isinstance(pdf_output, str):
            pdf_output = pdf_output.encode('latin-1')
        buffer = io.BytesIO(pdf_output)
        buffer.seek(0)
        
        filename = f"Precheck_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        response = send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        # Force the header to be extra explicit
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({'error': str(e)}), 500
