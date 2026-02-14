"""
Repository blueprint for IOS-XE image management
"""

from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from app.database.models import Database, RepositoryModel
import os
import hashlib
import json

repository_bp = Blueprint('repository', __name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

db = Database(config['database']['path'])
REPO_PATH = config['repository']['path']

# Ensure repository directory exists
os.makedirs(REPO_PATH, exist_ok=True)


def calculate_md5(file_path):
    """Calculate MD5 checksum of file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@repository_bp.route('/api/repository/upload', methods=['POST'])
def upload_image():
    """
    Upload IOS-XE image to repository
    Expects multipart/form-data with 'file' and REQUIRED 'md5_expected'
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    md5_expected = request.form.get('md5_expected', '').strip()
    
    # MD5 is now REQUIRED
    if not md5_expected:
        return jsonify({'error': 'MD5 hash is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Secure the filename
    filename = secure_filename(file.filename)
    file_path = os.path.join(REPO_PATH, filename)
    
    # Save file
    file.save(file_path)
    
    # Calculate MD5
    md5_actual = calculate_md5(file_path)
    
    # Verify MD5 (now required)
    if md5_actual.lower() != md5_expected.lower():
        os.remove(file_path)
        return jsonify({
            'error': 'MD5 mismatch',
            'expected': md5_expected,
            'actual': md5_actual
        }), 400
    
    # Add to database with MD5 hash
    RepositoryModel.add_image(db, filename, md5_expected, file_path)
    
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'md5': md5_actual,
        'size_bytes': os.path.getsize(file_path)
    })


@repository_bp.route('/api/repository/images', methods=['GET'])
def get_images():
    """Get all images in repository"""
    images = RepositoryModel.get_all_images(db)
    
    # Add file size for each image
    for image in images:
        if os.path.exists(image['file_path']):
            image['size_bytes'] = os.path.getsize(image['file_path'])
            image['size_mb'] = round(image['size_bytes'] / (1024**2), 2)
        else:
            image['size_bytes'] = 0
            image['size_mb'] = 0
    
    return jsonify({'images': images})


@repository_bp.route('/api/repository/<filename>', methods=['DELETE'])
def delete_image(filename):
    """Delete image from repository"""
    images = RepositoryModel.get_all_images(db)
    image = next((img for img in images if img['filename'] == filename), None)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    # Delete file
    if os.path.exists(image['file_path']):
        os.remove(image['file_path'])
    
    # Remove from database
    RepositoryModel.delete_image(db, filename)
    
    return jsonify({'message': 'Image deleted successfully'})


@repository_bp.route('/repo/<filename>', methods=['GET'])
def serve_image(filename):
    """
    Serve image file via HTTP for device download
    This endpoint is used by devices to copy images
    """
    return send_from_directory(REPO_PATH, filename)
