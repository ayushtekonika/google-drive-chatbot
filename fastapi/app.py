import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from asyncio import create_task, Lock, Queue, to_thread, sleep
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google.auth.exceptions import GoogleAuthError
from google_drive_downloader import GoogleDriveDownloader
from google_auth_oauthlib.flow import Flow 

env_path = Path('.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from qdrant import initialiseVectorDatabase
from file_embedding import process_and_add_embeddings

app = FastAPI()
STREAMLIT_UI_URL = os.getenv("STREAMLIT_UI_URL", "http://localhost:8501")
status_lock = Lock()
download_statuses = {}

flow = Flow.from_client_secrets_file(
    GoogleDriveDownloader.CREDENTIALS_FILE,
    scopes=GoogleDriveDownloader.SCOPES,
    redirect_uri=f"{os.getenv('APP_URL', 'http://127.0.0.1:8000')}/callback",
)

processing_progress_queue = Queue()
initialiseVectorDatabase()

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
        if not os.path.exists(GoogleDriveDownloader.TOKEN_FILE):            
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
    while True:
        while not processing_progress_queue.empty():
            progress = await processing_progress_queue.get()
            if progress["processing_id"] == processing_id:
                return progress
        # If no update is available yet, yield control to the event loop
        await sleep(0.5)

def download_progress_callback(processing_id: str, processed: int, total: int, current_process: str):
    status = {
        "processing_id": processing_id,
        "status": "in_progress",
        "current_process": current_process,
        "processed": processed,
        "total": total
    }
    # Push the status update to the queue
    processing_progress_queue.put_nowait(status)


async def download_files_task(processing_id: str, downloader: GoogleDriveDownloader):
    try:
        # Initialize with in-progress status
        status = {
            "processing_id": processing_id,
            "status": "in_progress",
            "current_process": "Downloading Documents",
            "processed": 0,
            "total": 1
        }
        await processing_progress_queue.put(status)

        # Start downloading (make the downloader function asynchronous)
        await to_thread(downloader.download_all, processing_id, download_progress_callback)
        await to_thread(process_and_add_embeddings, processing_id, download_progress_callback)

        total = downloader.get_total_files()
        # When download is complete, update status to completed
        status = {
            "processing_id": processing_id,
            "status": "completed",
            "current_process": "",
            "processed": total,
            "total": total
        }
        await processing_progress_queue.put(status)
    except Exception as e:
        # If something fails, push the failure status
        status = {
            "processing_id": processing_id,
            "status": f"failed: {str(e)}"
        }
        await processing_progress_queue.put(status)


