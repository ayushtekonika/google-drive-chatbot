import os
import streamlit as st
from streamlit.components.v1 import html
import requests
from urllib.parse import urlencode
import time
import webbrowser


API_BASE_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")

def redirect_to_google_consent():
    auth_url = f"{API_BASE_URL}/auth"
    webbrowser.open(auth_url)

def open_page():
    url = f"{API_BASE_URL}/auth"
    open_script= """
        <script type="text/javascript">
            window.open('%s', '_blank').focus();
        </script>
    """ % (url)
    html(open_script)
# FastAPI base URL (adjust if hosted elsewhere)

# Streamlit app
st.title("Google Drive Sync")

# Retrieve the URL query parameters
query_params = st.query_params
processing_id = query_params.get("processing_id")

if not processing_id:
    # No processing ID, show the sync button
    st.write("Click the button below to sync files with Google Drive.")
    st.button("Sync with Google Drive", on_click=open_page)
else:
    # Processing ID found, poll the status
    st.write(f"Processing ID: {processing_id}")
    status_placeholder = st.empty()  # Placeholder for status updates

    while True:
        # API call to check status
        status_url = f"{API_BASE_URL}/download_status/{processing_id}"
        try:
            response = requests.get(status_url)
            if response.status_code == 200:
                status = response.json().get("status", "unknown")
                status_placeholder.write(f"Download Status: {status}")

                # Exit the loop if the status is completed or failed
                if status in ["completed", "failed"]:
                    break
            else:
                status_placeholder.error(f"Failed to fetch status: {response.json().get('detail', 'Unknown error')}")
                break
        except Exception as e:
            status_placeholder.error(f"Error fetching download status: {str(e)}")
            break

        time.sleep(1)  # Poll every 1 second

    st.write("Process completed. Refresh the page to start a new sync.")
