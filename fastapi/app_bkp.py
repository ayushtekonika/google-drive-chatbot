import os
import io
import re
import uuid
import logging
from asyncio import to_thread, create_task, Lock

from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import FastAPI, HTTPException, Request

from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request as GoogleRequest

from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

# Global dictionary to track processing statuses
download_statuses = {}
status_lock = Lock()  # Ensure thread-safe access

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CREDENTIALS_FILE = "creds.json"
TOKEN_FILE = "token.json"
DOWNLOAD_DIR = "./assets"  # Directory to save downloaded files
ROOT_FOLDER_NAME = "Mridu Tiwari (RFP Overall Master - New)"
STREAMLIT_UI_URL = os.getenv("STREAMLIT_UI_URL", "http://localhost:8501")

# Initialize Flow globally for the app
flow = Flow.from_client_secrets_file(
    CREDENTIALS_FILE,
    scopes=SCOPES,
    redirect_uri=f"{os.getenv('APP_URL', 'http://127.0.0.1:8000')}/callback",
)

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def get_folder_id(service, folder_name):
    """
    Finds the ID of a folder by its name.
    """
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    if not folders:
        raise HTTPException(status_code=404, detail=f"Folder '{folder_name}' not found.")
    return folders[0]['id']

def ensure_download_directory():
    """Ensure the download directory exists."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

def list_files_in_folder(service, folder_id):
    """
    Lists all files in a folder by its ID.
    """
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

def download_file(service, file_id, file_name):
    """
    Downloads a file by its ID and saves it locally.
    """
    if not file_name.lower().endswith(('.docx', '.pdf')):
        logger.info(f"Skipping download for '{file_name}': Unsupported file type.")
        return
    
    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(DOWNLOAD_DIR, sanitize_filename(file_name))

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

def download_files_in_folder(service, folder_name):
    """
    Downloads all files in a folder with the given name.
    """
    print('triggered download_files_in_folder')
    ensure_download_directory()

    # Get the folder ID
    folder_id = get_folder_id(service, folder_name)
    print(folder_id)
    if not folder_id:
        return

    # List files in the folder
    files = list_files_in_folder(service, folder_id)
    if not files:
        print(f"The folder '{folder_name}' is empty or contains no files.")
        return

    # Download each file
    for file in files:
        if file['mimeType'] != 'application/vnd.google-apps.folder':  # Skip subfolders
            download_file(service, file['id'], file['name'])

async def download_files_from_google_drive(service):
    """
    Downloads files from Google Drive in the specified root folder.
    """
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Refresh credentials if expired

        # Ensure this returns an awaitable that is awaited
        await to_thread(download_files_in_folder, service, ROOT_FOLDER_NAME)
        return {"message": "Files downloaded successfully."}

    except GoogleAuthError as auth_err:
        return JSONResponse(
            status_code=401,
            content={"error": "Authentication failed", "details": str(auth_err)},
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to download files", "details": str(e)},
        )

async def download_files_task(processing_id, service):
    """
    Asynchronous task to download files and update the status.
    """
    try:
        async with status_lock:
            download_statuses[processing_id] = "in_progress"

        await download_files_from_google_drive(service)

        async with status_lock:
            download_statuses[processing_id] = "completed"

    except Exception as e:
        async with status_lock:
            download_statuses[processing_id] = f"failed: {str(e)}"

def load_or_refresh_credentials():
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        print(creds)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
            return creds
    print('just none')
    return None

@app.get("/auth")
async def authenticate():
    """
    Redirect to Google Consent screen for OAuth2 authentication.
    """
    try:
        # Generate the authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",  # For refresh tokens
            include_granted_scopes="true"  # Use previously granted scopes
        )
        return RedirectResponse(url=auth_url)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to generate authorization URL", "details": str(e)},
        )

@app.get("/callback")
async def callback(request: Request):
    """
    Handle the redirect from Google after user consents.
    """
    try:
        query_params = request.query_params
        code = query_params.get("code")
        creds = load_or_refresh_credentials()
        if creds:
            processing_id = str(uuid.uuid4())
            service = build('drive', 'v3', credentials=creds)
            create_task(download_files_task(processing_id, service))
            url_with_processing_id = f"{STREAMLIT_UI_URL}?processing_id={processing_id}"
            return RedirectResponse(url=url_with_processing_id)

        # If no valid token exists, proceed with OAuth flow
        if not code:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing authorization code in the request"},
            )

        # Fetch the token using the code
        print('fetch token')
        flow.fetch_token(code=code)

        # Save the new token
        credentials = flow.credentials
        with open(TOKEN_FILE, "w") as token_file:
            print(credentials.to_json())
            token_file.write(credentials.to_json())

        # Create a processing ID and start the download task
        processing_id = str(uuid.uuid4())
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        service = build('drive', 'v3', credentials=creds)
        create_task(download_files_task(processing_id, service))

        url_with_processing_id = f"{STREAMLIT_UI_URL}?processing_id={processing_id}"
        return RedirectResponse(url=url_with_processing_id)
    
    except RefreshError as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Refresh token error", "details": str(e)},
        )

    except GoogleAuthError as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Authentication error", "details": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Unexpected error", "details": str(e)},
        )
    
@app.get("/download_status/{processing_id}")
async def download_status(processing_id: str):
    """
    Get the status of a file download operation by processing_id.
    """
    async with status_lock:
        status = download_statuses.get(processing_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Processing ID not found")

    return {"processing_id": processing_id, "status": status}