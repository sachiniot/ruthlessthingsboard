import os
import pickle
import zipfile
import datetime
import schedule
import time
import threading
import logging
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Google Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveBackup:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        self.backup_folder_name = "Solar_Server_Backups"
        
        # Define what to backup from your server
        self.backup_paths = [
            'data/',           # Your data directory
            'logs/',           # Log files
            'config/',         # Configuration files
            'uploads/'         # User uploads (if any)
        ]
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging for backup operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('backup.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self):
        """Authenticate with Google Drive API"""
        try:
            creds = None
            
            # The file token.pickle stores the user's access and refresh tokens
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no valid credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Check if credentials.json exists
                    if not os.path.exists('credentials.json'):
                        self.logger.error("❌ credentials.json file not found")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            self.service = build('drive', 'v3', credentials=creds)
            self.logger.info("✅ Google Drive authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Google Drive authentication failed: {e}")
            return False
    
    def find_or_create_backup_folder(self):
        """Find or create the backup folder in Google Drive"""
        try:
            # Search for existing folder
            query = f"name='{self.backup_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            folders = results.get('files', [])
            
            if folders:
                self.backup_folder_id = folders[0]['id']
                self.logger.info(f"✅ Found existing backup folder: {self.backup_folder_name}")
            else:
                # Create new folder
                file_metadata = {
                    'name': self.backup_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=file_metadata, fields='id').execute()
                self.backup_folder_id = folder.get('id')
                self.logger.info(f"✅ Created new backup folder: {self.backup_folder_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error finding/creating backup folder: {e}")
            return False
    
    def create_backup_zip(self, backup_name=None):
        """Create a zip file of specified paths"""
        try:
            if backup_name is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"solar_server_backup_{timestamp}.zip"
            
            # Filter out paths that don't exist
            existing_paths = [path for path in self.backup_paths if os.path.exists(path)]
            
            if not existing_paths:
                self.logger.warning("⚠️ No backup paths exist")
                return None
            
            with zipfile.ZipFile(backup_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for path in existing_paths:
                    if os.path.isfile(path):
                        zipf.write(path, os.path.basename(path))
                        self.logger.info(f"📄 Added file to backup: {path}")
                    elif os.path.isdir(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(path))
                                zipf.write(file_path, arcname)
                        self.logger.info(f"📁 Added directory to backup: {path}")
            
            self.logger.info(f"✅ Created backup zip: {backup_name}")
            return backup_name
            
        except Exception as e:
            self.logger.error(f"❌ Error creating backup zip: {e}")
            return None
    
    def upload_to_drive(self, file_path):
        """Upload file to Google Drive"""
        try:
            file_metadata = {
                'name': os.path.basename(file_path),
                'mimeType': 'application/zip'
            }
            
            if self.backup_folder_id:
                file_metadata['parents'] = [self.backup_folder_id]
            
            media = MediaFileUpload(file_path, mimetype='application/zip')
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size'
            ).execute()
            
            self.logger.info(f"✅ Uploaded to Google Drive: {file.get('name')} (ID: {file.get('id')})")
            return file.get('id')
            
        except Exception as e:
            self.logger.error(f"❌ Error uploading to Google Drive: {e}")
            return None
    
    def perform_backup(self):
        """Perform the complete backup process"""
        try:
            self.logger.info("🔄 Starting backup process...")
            
            # Authenticate if not already done
            if not self.service:
                if not self.authenticate():
                    return False
            
            # Ensure backup folder exists
            if not self.backup_folder_id:
                if not self.find_or_create_backup_folder():
                    return False
            
            # Create backup zip
            backup_file = self.create_backup_zip()
            if not backup_file:
                return False
            
            # Upload to Google Drive
            file_id = self.upload_to_drive(backup_file)
            
            # Clean up local zip file
            if os.path.exists(backup_file):
                os.remove(backup_file)
                self.logger.info(f"🧹 Cleaned up local file: {backup_file}")
            
            if file_id:
                self.logger.info("✅ Backup completed successfully!")
                return True
            else:
                self.logger.error("❌ Backup failed during upload")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Backup process failed: {e}")
            return False
    
    def schedule_backups(self):
        """Schedule automatic backups"""
        # Daily backup at 2 AM
        schedule.every().day.at("02:00").do(self.perform_backup)
        
        # Weekly backup on Sunday at 3 AM
        schedule.every().sunday.at("03:00").do(self.perform_backup)
        
        self.logger.info("⏰ Backup scheduler started")
        
        # Run scheduler in a separate thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

# Global backup instance
backup_manager = GoogleDriveBackup()

def initialize_backup_system():
    """Initialize the backup system"""
    try:
        # Try to authenticate on startup
        if backup_manager.authenticate():
            backup_manager.find_or_create_backup_folder()
            backup_manager.schedule_backups()
            return True
        return False
    except Exception as e:
        backup_manager.logger.error(f"❌ Backup system initialization failed: {e}")
        return False
