from fastapi import Request
from fastapi.responses import RedirectResponse
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import google.oauth2.credentials
import config
import os

def login(request: Request):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        config.GOOGLE_CLIENT_SECRET,
        scopes=config.SCOPES
    )
    flow.redirect_uri = config.REDIRECT_URI

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )
    request.session["state"] = state
    return RedirectResponse(authorization_url)


def callback(request: Request):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # if local dev only!

    state = request.session.get("state")
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        config.GOOGLE_CLIENT_SECRET,
        scopes=config.SCOPES,
        state=state
    )
    flow.redirect_uri = config.REDIRECT_URI

    flow.fetch_token(authorization_response=str(request.url))

    credentials = flow.credentials
    request.session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    return RedirectResponse(config.FRONTEND_URL)


def list_drive_files(credentials_dict):
    # Rebuild Credentials object
    credentials = google.oauth2.credentials.Credentials(
        token=credentials_dict["token"],
        refresh_token=credentials_dict.get("refresh_token"),
        token_uri=credentials_dict.get("token_uri"),
        client_id=credentials_dict.get("client_id"),
        client_secret=credentials_dict.get("client_secret"),
        scopes=credentials_dict.get("scopes")
    )

    drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=credentials)

    files = []
    page_token = None
    try:
        while True:
            response = drive_service.files().list(
                q="trashed = false",
                spaces='drive',
                fields="nextPageToken, files(id, name, mimeType, parents)",
                pageToken=page_token
            ).execute()

            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
    except Exception as e:
        raise Exception(f"Failed to fetch drive files: {e}")

    # Optionally: build a hierarchical structure (folders + files grouped)
    # For simplicity, return flat file list here
    return {"files": files}
