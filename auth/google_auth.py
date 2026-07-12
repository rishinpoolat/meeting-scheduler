"""OAuth2 credential loading, caching, and refresh for Gmail + Calendar."""

import os
import stat

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
]

CREDENTIALS_PATH = "credentials.json"
TOKEN_PATH = "token.json"


def get_credentials() -> Credentials:
    """Return valid, refreshed OAuth2 credentials, prompting for consent if needed."""
    creds = _load_cached_credentials()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except RefreshError:
            pass

    creds = _run_interactive_flow()
    _save_token(creds)
    return creds


def _load_cached_credentials() -> Credentials | None:
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except ValueError:
        return None


def _run_interactive_flow() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    return flow.run_local_server(port=0)


def _save_token(creds: Credentials) -> None:
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)
