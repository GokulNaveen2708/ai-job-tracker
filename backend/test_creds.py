from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.auth.exceptions
from google.auth.transport.requests import Request

try:
    access_token = "ya29.c.fake_token_that_is_definitely_invalid"
    creds = Credentials(
        token=access_token,
        refresh_token="",  # EMPTY STRING INSTEAD OF NONE
        token_uri="https://oauth2.googleapis.com/token",
        client_id="fake_client_id",
        client_secret="fake_client_secret",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
except google.auth.exceptions.RefreshError as e:
    print(f"RefreshError caught! {e}")
except Exception as e:
    print(f"Other Error: {type(e)} {e}")
