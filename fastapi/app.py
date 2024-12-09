import os
import uuid
from asyncio import create_task, Lock
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google.auth.exceptions import GoogleAuthError
from google_drive_downloader import GoogleDriveDownloader
from google_auth_oauthlib.flow import Flow

app = FastAPI()

STREAMLIT_UI_URL = os.getenv("STREAMLIT_UI_URL", "http://localhost:8501")
ROOT_FOLDER_NAME = "Mridu Tiwari (RFP Overall Master - New)"
status_lock = Lock()
download_statuses = {}

flow = Flow.from_client_secrets_file(
    GoogleDriveDownloader.CREDENTIALS_FILE,
    scopes=GoogleDriveDownloader.SCOPES,
    redirect_uri=f"{os.getenv('APP_URL', 'http://127.0.0.1:8000')}/callback",
)

@app.get("/auth")
async def authenticate():
    try:
        auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/callback")
async def callback(request: Request):
    try:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        flow.fetch_token(code=code)
        with open(GoogleDriveDownloader.TOKEN_FILE, "w") as token_file:
            token_file.write(flow.credentials.to_json())

        processing_id = str(uuid.uuid4())
        downloader = GoogleDriveDownloader()
        downloader.initialize_service()

        create_task(download_files_task(processing_id, downloader))
        return RedirectResponse(url=f"{STREAMLIT_UI_URL}?processing_id={processing_id}")
    except GoogleAuthError as e:
        return JSONResponse(status_code=401, content={"error": str(e)})

@app.get("/download_status/{processing_id}")
async def download_status(processing_id: str):
    async with status_lock:
        status = download_statuses.get(processing_id)
    if not status:
        raise HTTPException(status_code=404, detail="Processing ID not found")
    return {"processing_id": processing_id, "status": status}

async def download_files_task(processing_id: str, downloader: GoogleDriveDownloader):
    try:
        async with status_lock:
            download_statuses[processing_id] = "in_progress"

        downloader.download_files_in_folder(ROOT_FOLDER_NAME)

        async with status_lock:
            download_statuses[processing_id] = "completed"
    except Exception as e:
        async with status_lock:
            download_statuses[processing_id] = f"failed: {str(e)}"
