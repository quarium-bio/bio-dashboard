import os
import io
import json
import threading
import sys
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    from unittest.mock import MagicMock
    GOOGLE_API_AVAILABLE = False
    Credentials = MagicMock()
    InstalledAppFlow = MagicMock()
    Request = MagicMock()
    RefreshError = Exception
    build = MagicMock()
    MediaIoBaseDownload = MagicMock()
    MediaFileUpload = MagicMock()
    MediaIoBaseUpload = MagicMock()

SCOPES = ['https://www.googleapis.com/auth/drive.appdata']

class DriveSyncManager:
    def __init__(self):
        self.creds = None
        self.service = None
        self.file_versions = {}
        self.api_lock = threading.RLock()
        if not GOOGLE_API_AVAILABLE:
            raise ImportError("Google API client libraries are not installed. Please install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        self.sync_state_path = os.path.join(BASE_DIR, 'sync_state.json')
        self._load_sync_state()
        self.authenticate()

    def _load_sync_state(self):
        if os.path.exists(self.sync_state_path):
            try:
                with open(self.sync_state_path, 'r') as f:
                    self.file_versions = json.load(f)
            except Exception: pass
            
    def _save_sync_state(self):
        try:
            with open(self.sync_state_path, 'w') as f:
                json.dump(self.file_versions, f)
        except Exception: pass

    def authenticate(self):
        token_path = os.path.join(BASE_DIR, 'token.json')
        creds_path = os.path.join(BASE_DIR, 'credentials.json')
        with self.api_lock:
            if os.path.exists(token_path):
                self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        self.creds.refresh(Request())
                    except RefreshError:
                        self.creds = None
                        if os.path.exists(token_path):
                            os.remove(token_path)
                
                if not self.creds or not self.creds.valid:
                    if not os.path.exists(creds_path):
                        raise FileNotFoundError(f"{creds_path} not found. Please obtain OAuth 2.0 client ID from Google Cloud Console.")
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    with open(token_path, 'w') as token:
                        token.write(self.creds.to_json())
            self.service = build('drive', 'v3', credentials=self.creds)

    def list_appdata_files(self):
        results = self.service.files().list(  # type: ignore
            spaces='appDataFolder', fields='nextPageToken, files(id, name, modifiedTime)').execute()
        return {f['name']: {'id': f['id'], 'modifiedTime': f.get('modifiedTime')} for f in results.get('files', [])}

    def list_conflict_files(self):
        with self.api_lock:
            files = self.list_appdata_files()
            return {name: data for name, data in files.items() if '_conflict_' in name}
            
    def delete_file(self, file_id):
        with self.api_lock:
            try: self.service.files().delete(fileId=file_id).execute()  # type: ignore
            except Exception as e: print("Delete file error:", e)

    def read_lock(self):
        with self.api_lock:
            try:
                files = self.list_appdata_files()
                if 'lock.json' in files:
                    file_id = files['lock.json']['id'] if isinstance(files['lock.json'], dict) else files['lock.json']
                    request = self.service.files().get_media(fileId=file_id)  # type: ignore
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done: _, done = downloader.next_chunk()
                    return json.loads(fh.getvalue().decode('utf-8'))
            except Exception as e: print("Read lock error:", e)
            return None

    def write_lock(self, lock_data):
        with self.api_lock:
            try:
                lock_bytes = json.dumps(lock_data).encode('utf-8')
                fh = io.BytesIO(lock_bytes)
                files = self.list_appdata_files()
                media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
                if 'lock.json' in files:
                    file_id = files['lock.json']['id'] if isinstance(files['lock.json'], dict) else files['lock.json']
                    self.service.files().update(fileId=file_id, media_body=media).execute()  # type: ignore
                else:
                    file_metadata = {'name': 'lock.json', 'parents': ['appDataFolder']}
                    self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()  # type: ignore
            except Exception as e: print("Write lock error:", e)

    def download_file(self, file_id, file_path):
        request = self.service.files().get_media(fileId=file_id)  # type: ignore
        with io.FileIO(file_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    def upload_file(self, file_path, file_name, file_id=None):
        media = MediaFileUpload(file_path, resumable=True)
        if file_id:
            res = self.service.files().update(fileId=file_id, media_body=media, fields='id, modifiedTime').execute()  # type: ignore
        else:
            file_metadata = {'name': file_name, 'parents': ['appDataFolder']}
            res = self.service.files().create(body=file_metadata, media_body=media, fields='id, modifiedTime').execute()  # type: ignore
        return res.get('modifiedTime')

    def sync_down(self, filenames):
        with self.api_lock:
            files_in_drive = self.list_appdata_files()
            changed = False
            for name in filenames:
                if name in files_in_drive:
                    file_path = os.path.join(BASE_DIR, name)
                    cloud_time = files_in_drive[name].get('modifiedTime')
                    if os.path.exists(file_path) and self.file_versions.get(name) == cloud_time:
                        continue # Skip download if already up to date
                    self.download_file(files_in_drive[name]['id'], file_path)
                    self.file_versions[name] = cloud_time
                    changed = True
            if changed:
                self._save_sync_state()

    def sync_up(self, filenames, current_user="Unknown"):
        with self.api_lock:
            files_in_drive = self.list_appdata_files()
            conflicts = []
            changed = False
            for name in filenames:
                file_path = os.path.join(BASE_DIR, name)
                if os.path.exists(file_path):
                    drive_file = files_in_drive.get(name)
                    if drive_file:
                        cloud_time = drive_file.get('modifiedTime')
                        known_time = self.file_versions.get(name)
                        if known_time and cloud_time and cloud_time != known_time:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            clean_user = "".join(c for c in current_user if c.isalnum()) or "Unknown"
                            conflict_name = f"{name.split('.')[0]}_conflict_{clean_user}_{timestamp}.{name.split('.')[-1]}"
                            self.upload_file(file_path, conflict_name, None)
                            conflicts.append(name)
                            continue
                        new_time = self.upload_file(file_path, name, drive_file['id'])
                        self.file_versions[name] = new_time
                        changed = True
                    else:
                        new_time = self.upload_file(file_path, name, None)
                        self.file_versions[name] = new_time
                        changed = True
            if changed:
                self._save_sync_state()
            return conflicts