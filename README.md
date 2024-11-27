# Running the Server

1. Navigate to the `fastapi` folder.
2. Install the required dependencies by running:
   ```bash
   pip install -r requirements.txt
3. Download the OAuth 2.0 credentials file from Google Cloud Console > API & Services > Credentials.
4. Place the credentials file as creds.json in the fastapi folder.
5. Run the server with the following command: `python -m uvicorn app:app --reload`


# Running the client

1. Navigate to streamlit-ui folder 
2. Run `pip install -r requirements.txt`
3. Run `python -m streamlit run app.py`

