"""Calendar API service construction."""

from typing import Any

from googleapiclient.discovery import build

from auth.google_auth import get_credentials

CALENDAR_ID = "primary"


def get_service() -> Any:
    """Return an authenticated Calendar API v3 service resource."""
    return build("calendar", "v3", credentials=get_credentials())
