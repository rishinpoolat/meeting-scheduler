"""Gmail API service construction."""

from typing import Any

from googleapiclient.discovery import build

from auth.google_auth import get_credentials


def get_service() -> Any:
    """Return an authenticated Gmail API v1 service resource."""
    return build("gmail", "v1", credentials=get_credentials())
