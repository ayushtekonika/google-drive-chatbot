import os
import re
import io
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from fastapi import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleDriveDownloader:
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    CREDENTIALS_FILE = "creds.json"
    TOKEN_FILE = "token.json"
    DOWNLOAD_DIR = "./assets"

    def __init__(self):
        self.service = None

    def load_credentials(self):
        """Load or refresh credentials."""
        if os.path.exists(self.TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(self.TOKEN_FILE)
            if creds.valid:
                return creds
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(self.TOKEN_FILE, "w") as token_file:
                    token_file.write(creds.to_json())
                return creds
        raise HTTPException(status_code=401, detail="Authentication required")

    def initialize_service(self):
        """Initialize the Google Drive service."""
        creds = self.load_credentials()
        self.service = build('drive', 'v3', credentials=creds)

    @staticmethod
    def sanitize_filename(filename):
        return re.sub(r'[<>:"/\\|?*]', '_', filename)

    def ensure_download_directory(self):
        """Ensure the download directory exists."""
        if not os.path.exists(self.DOWNLOAD_DIR):
            os.makedirs(self.DOWNLOAD_DIR)

    def get_folder_id(self, folder_name):
        """Find the ID of a folder by its name."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        if not folders:
            raise HTTPException(status_code=404, detail=f"Folder '{folder_name}' not found.")
        return folders[0]['id']

    def list_files_in_folder(self, folder_id):
        """List all files in a folder by its ID."""
        results = self.service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name, mimeType)"
        ).execute()
        return results.get('files', [])

    def download_file(self, file_id, file_name):
        """Download a file by its ID."""
        if not file_name.lower().endswith(('.docx', '.pdf')):
            logger.info(f"Skipping download for '{file_name}': Unsupported file type.")
            return

        request = self.service.files().get_media(fileId=file_id)
        file_path = os.path.join(self.DOWNLOAD_DIR, self.sanitize_filename(file_name))

        if os.path.exists(file_path):
            logger.info(f"File '{file_name}' already exists at {file_path}. Skipping download.")
            return

        with io.FileIO(file_path, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Downloading {file_name}: {int(status.progress() * 100)}% complete")

        logger.info(f"Downloaded: {file_name} to {file_path}")

    def download_files_in_folder(self, folder_name):
        """Download all files in a folder."""
        self.ensure_download_directory()
        folder_id = self.get_folder_id(folder_name)
        files = self.list_files_in_folder(folder_id)
        for file in files:
            if file['mimeType'] != 'application/vnd.google-apps.folder':  # Skip subfolders
                self.download_file(file['id'], file['name'])
