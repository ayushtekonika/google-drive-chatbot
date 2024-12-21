import os
import re
import io
import logging
from typing import Callable
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
    ROOT_FOLDER_NAME = "Mridu Tiwari (RFP Overall Master - New)"
    FOLDER_LIST = ["new", "submitted"]

    def __init__(self):
        self.service = None
        self.total_files_downloaded = 0

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

    def get_folder_id(self, folder_name, parent_id=None):
        """Find the ID of a folder by its name."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        if not folders:
            raise HTTPException(status_code=404, detail=f"Folder '{folder_name}' not found.")
        return folders[0]['id']

    def list_files_in_folder(self, folder_id):
        """List all files in a folder by its ID."""
        results = self.service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name, mimeType)"
        ).execute()
        return results.get('files', [])
    
    def get_total_files(self):
        """Get the total number of files in ROOT_FOLDER_NAME/{folders in FOLDER_LIST}."""
        total_files = 0
        root_folder_id = self.get_folder_id(self.ROOT_FOLDER_NAME)

        for subfolder in self.FOLDER_LIST:
            try:
                subfolder_id = self.get_folder_id(subfolder, parent_id=root_folder_id)
                files = self.list_files_in_folder(subfolder_id)
                total_files += len([file for file in files if file['mimeType'] != 'application/vnd.google-apps.folder'])
            except HTTPException as e:
                logger.error(f"Failed to process folder '{subfolder}': {e.detail}")

        return total_files



    def download_file(self, file_id, file_name, parent_folder_name):
        """Download a file by its ID and append its parent folder name to the file name."""
        if not file_name.lower().endswith(('.docx', '.pdf')):
            logger.info(f"Skipping download for '{file_name}': Unsupported file type.")
            return

        # Append the parent folder name to the file name
        modified_file_name = f"{parent_folder_name}_{file_name}"
        sanitized_file_name = self.sanitize_filename(modified_file_name)
        file_path = os.path.join(self.DOWNLOAD_DIR, sanitized_file_name)

        if os.path.exists(file_path):
            logger.info(f"File '{sanitized_file_name}' already exists at {file_path}. Skipping download.")
            return

        request = self.service.files().get_media(fileId=file_id)

        with io.FileIO(file_path, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Downloading {sanitized_file_name}: {int(status.progress() * 100)}% complete")

        logger.info(f"Downloaded: {sanitized_file_name} to {file_path}")


    def download_files_in_folder(self, folder_id, folder_name: str, processing_id: str, progress_callback: Callable[[str, int, int, str], None]):
        """Download all files in a folder."""
        files = self.list_files_in_folder(folder_id)
        total_files = self.get_total_files()
        # downloaded_count = 0
        for file in files:
            if file['mimeType'] != 'application/vnd.google-apps.folder':  # Skip subfolders
                self.download_file(file['id'], file['name'], folder_name)
                self.total_files_downloaded += 1
                progress_callback(processing_id, self.total_files_downloaded, total_files, "Downloading Documents")

    def download_all(self, processing_id: str, progress_callback: Callable[[str, int, int, str], None]):
        """Download files from ROOT_FOLDER_NAME and its specified subfolders."""
        self.ensure_download_directory()
        self.initialize_service()

        # Get the ID of the root folder
        root_folder_id = self.get_folder_id(self.ROOT_FOLDER_NAME)

        for subfolder in self.FOLDER_LIST:
            try:
                subfolder_id = self.get_folder_id(subfolder, parent_id=root_folder_id)
                logger.info(f"Downloading files from folder: {self.ROOT_FOLDER_NAME}/{subfolder}")
                self.download_files_in_folder(subfolder_id, subfolder, processing_id, progress_callback)
            except HTTPException as e:
                logger.error(f"Failed to process folder '{subfolder}': {e.detail}")
