"""
Migration script to transfer files from local uploads folder to S3.
Run this script BEFORE the first run of the application with S3.

This script will:
1. Read all files from the local uploads folder
2. Upload them to S3 bucket
3. Optionally update database records to point to S3 URLs
"""

import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from urllib.parse import quote_plus
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Load environment variables
load_dotenv()

# Initialize Flask app for SQLAlchemy (if needed for database updates)
app = Flask(__name__)

# MySQL Database Configuration from environment variables
mysql_host = os.getenv('MYSQL_HOST')
mysql_port = os.getenv('MYSQL_PORT')
mysql_user = os.getenv('MYSQL_USER')
mysql_password = os.getenv('MYSQL_PASSWORD')
mysql_database = os.getenv('MYSQL_DATABASE')

# URL-encode password to handle special characters like @, #, etc.
encoded_password = quote_plus(mysql_password) if mysql_password else ''
# Configure MySQL connection (only if updating database)
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{mysql_user}:{encoded_password}@{mysql_host}:{mysql_port}/{mysql_database}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models (for updating URLs)
class Observation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projectCode = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    raisedBy = db.Column(db.String(100), nullable=False)
    issueType = db.Column(db.String(50), nullable=False)
    safetyCategory = db.Column(db.String(50), nullable=False)
    observation = db.Column(db.Text, nullable=False)
    observationPhoto = db.Column(db.Text)
    contractor = db.Column(db.String(100), nullable=False, default='SIL')
    subContractor = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Open')
    compliance = db.Column(db.Text)
    complianceDate = db.Column(db.String(20))
    compliancePhoto = db.Column(db.Text)


def get_s3_client():
    """Initialize and return S3 client"""
    s3_bucket = os.getenv('S3_BUCKET_NAME', '')
    s3_region = os.getenv('S3_REGION', 'us-east-1')
    s3_access_key = os.getenv('S3_ACCESS_KEY', '')
    s3_secret_key = os.getenv('S3_SECRET_KEY', '')
    s3_endpoint_url = os.getenv('S3_ENDPOINT_URL', None)
    s3_folder_prefix = os.getenv('S3_FOLDER_PREFIX', 'uploads').strip().rstrip('/')
    s3_folder_prefix = s3_folder_prefix if s3_folder_prefix else 'uploads'
    
    if not s3_bucket or not s3_access_key or not s3_secret_key:
        print("ERROR: S3 credentials not found in .env file")
        print("Required environment variables:")
        print("  - S3_BUCKET_NAME")
        print("  - S3_ACCESS_KEY")
        print("  - S3_SECRET_KEY")
        print("  - S3_REGION (optional, defaults to us-east-1)")
        print("  - S3_FOLDER_PREFIX (optional, defaults to 'uploads')")
        print("  - S3_ENDPOINT_URL (optional, for S3-compatible services)")
        return None, None, s3_folder_prefix
    
    s3_config = {
        'aws_access_key_id': s3_access_key,
        'aws_secret_access_key': s3_secret_key,
        'region_name': s3_region
    }
    if s3_endpoint_url:
        s3_config['endpoint_url'] = s3_endpoint_url
    
    try:
        s3_client = boto3.client('s3', **s3_config)
        # Test connection by checking if bucket exists
        s3_client.head_bucket(Bucket=s3_bucket)
        print(f"Successfully connected to S3 bucket: {s3_bucket}")
        print(f"S3 folder prefix: {s3_folder_prefix}")
        return s3_client, s3_bucket, s3_folder_prefix
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"ERROR: S3 bucket '{s3_bucket}' not found")
        elif error_code == '403':
            print(f"ERROR: Access denied to S3 bucket '{s3_bucket}'")
        else:
            print(f"ERROR connecting to S3: {str(e)}")
        return None, None, s3_folder_prefix
    except Exception as e:
        print(f"ERROR initializing S3 client: {str(e)}")
        return None, None, s3_folder_prefix


def get_s3_url(s3_bucket, s3_key, s3_region, s3_endpoint_url):
    """Generate S3 URL for a file"""
    if s3_endpoint_url:
        return f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
    else:
        return f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"


def upload_file_to_s3(s3_client, bucket_name, local_file_path, s3_key):
    """Upload a file to S3"""
    try:
        # Determine content type
        content_type = 'application/octet-stream'
        ext = os.path.splitext(local_file_path)[1].lower()
        content_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
        }
        content_type = content_type_map.get(ext, content_type)
        
        s3_client.upload_file(
            local_file_path,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )
        return True
    except Exception as e:
        print(f"  ERROR uploading {os.path.basename(local_file_path)}: {str(e)}")
        return False


def migrate_files():
    """Migrate files from local uploads folder to S3"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    uploads_folder = os.path.join(basedir, 'uploads')
    
    # Check if uploads folder exists
    if not os.path.exists(uploads_folder):
        print(f"WARNING: Uploads folder not found at {uploads_folder}")
        print("No files to migrate.")
        return True
    
    # Get S3 client
    s3_client, s3_bucket, s3_folder_prefix = get_s3_client()
    if not s3_client:
        return False
    
    s3_region = os.getenv('S3_REGION', 'us-east-1')
    s3_endpoint_url = os.getenv('S3_ENDPOINT_URL', None)
    
    # Get all files from uploads folder
    files = [f for f in os.listdir(uploads_folder) if os.path.isfile(os.path.join(uploads_folder, f))]
    
    if not files:
        print("No files found in uploads folder.")
        return True
    
    print(f"\nFound {len(files)} files to migrate.")
    
    # Upload files to S3
    uploaded_count = 0
    failed_count = 0
    file_url_mapping = {}  # Map local filename to S3 URL
    
    for filename in files:
        local_file_path = os.path.join(uploads_folder, filename)
        s3_key = f"{s3_folder_prefix}/{filename}"
        
        print(f"Uploading: {filename}...", end=' ')
        
        # Check if file already exists in S3
        try:
            s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
            print("SKIPPED (already exists in S3)")
            s3_url = get_s3_url(s3_bucket, s3_key, s3_region, s3_endpoint_url)
            file_url_mapping[filename] = s3_url
            continue
        except ClientError:
            # File doesn't exist, proceed with upload
            pass
        
        if upload_file_to_s3(s3_client, s3_bucket, local_file_path, s3_key):
            print("SUCCESS")
            uploaded_count += 1
            s3_url = get_s3_url(s3_bucket, s3_key, s3_region, s3_endpoint_url)
            file_url_mapping[filename] = s3_url
        else:
            print("FAILED")
            failed_count += 1
    
    print(f"\nUpload Summary:")
    print(f"  - Successfully uploaded: {uploaded_count}")
    print(f"  - Failed: {failed_count}")
    print(f"  - Already existed: {len(files) - uploaded_count - failed_count}")
    
    # Optionally update database records
    update_db = input("\nUpdate database records to use S3 URLs? (yes/no): ")
    if update_db.lower() == 'yes':
        update_database_urls(file_url_mapping, s3_region, s3_endpoint_url)
    
    return failed_count == 0


def update_database_urls(file_url_mapping, s3_region, s3_endpoint_url):
    """Update database records to point to S3 URLs"""
    try:
        with app.app_context():
            observations = Observation.query.all()
            updated_count = 0
            
            for obs in observations:
                updated = False
                
                # Update observationPhoto
                if obs.observationPhoto:
                    # Extract filename from local path
                    if obs.observationPhoto.startswith('/uploads/'):
                        filename = obs.observationPhoto.replace('/uploads/', '')
                        if filename in file_url_mapping:
                            obs.observationPhoto = file_url_mapping[filename]
                            updated = True
                    elif not obs.observationPhoto.startswith('http'):
                        # Try to find matching file
                        for local_filename, s3_url in file_url_mapping.items():
                            if local_filename in obs.observationPhoto or obs.observationPhoto in local_filename:
                                obs.observationPhoto = s3_url
                                updated = True
                                break
                
                # Update compliancePhoto
                if obs.compliancePhoto:
                    # Extract filename from local path
                    if obs.compliancePhoto.startswith('/uploads/'):
                        filename = obs.compliancePhoto.replace('/uploads/', '')
                        if filename in file_url_mapping:
                            obs.compliancePhoto = file_url_mapping[filename]
                            updated = True
                    elif not obs.compliancePhoto.startswith('http'):
                        # Try to find matching file
                        for local_filename, s3_url in file_url_mapping.items():
                            if local_filename in obs.compliancePhoto or obs.compliancePhoto in local_filename:
                                obs.compliancePhoto = s3_url
                                updated = True
                                break
                
                if updated:
                    updated_count += 1
            
            if updated_count > 0:
                db.session.commit()
                print(f"\nUpdated {updated_count} observation records with S3 URLs.")
            else:
                print("\nNo database records needed updating.")
                
    except Exception as e:
        print(f"\nERROR updating database: {str(e)}")
        import traceback
        traceback.print_exc()
        with app.app_context():
            db.session.rollback()


if __name__ == '__main__':
    print("="*50)
    print("Local Files to S3 Migration Script")
    print("="*50)
    print("\nThis script will migrate all files from local uploads folder to S3.")
    print("Make sure you have:")
    print("  1. Set up .env file with S3 credentials")
    print("  2. Created the S3 bucket")
    print("  3. Installed required packages (boto3, python-dotenv)")
    
    s3_bucket = os.getenv('S3_BUCKET_NAME', '')
    s3_region = os.getenv('S3_REGION', 'us-east-1')
    s3_endpoint_url = os.getenv('S3_ENDPOINT_URL', None)
    s3_folder_prefix = os.getenv('S3_FOLDER_PREFIX', 'uploads').strip().rstrip('/')
    s3_folder_prefix = s3_folder_prefix if s3_folder_prefix else 'uploads'
    
    print("\nS3 Configuration:")
    print(f"  Bucket: {s3_bucket}")
    print(f"  Region: {s3_region}")
    print(f"  Folder Prefix: {s3_folder_prefix}")
    print(f"  Full Path: s3://{s3_bucket}/{s3_folder_prefix}/")
    if s3_endpoint_url:
        print(f"  Endpoint: {s3_endpoint_url}")
    else:
        print("  Endpoint: AWS S3 (default)")
    
    response = input("\nContinue with file migration? (yes/no): ")
    if response.lower() == 'yes':
        success = migrate_files()
        if success:
            print("\n" + "="*50)
            print("File migration completed successfully!")
            print("="*50)
        else:
            print("\n" + "="*50)
            print("File migration completed with errors.")
            print("="*50)
            exit(1)
    else:
        print("Migration cancelled.")
        exit(0)

