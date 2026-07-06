"""Listing unread Gmail messages and fetching their reply-relevant metadata."""

from dataclasses import dataclass
from typing import Any

METADATA_HEADERS = ["From", "Subject", "Message-Id", "References"]


@dataclass
class Message:
    id: str
    thread_id: str
    subject: str
    from_address: str
    message_id_header: str
    references_header: str
    snippet: str


def list_unread_message_ids(service: Any, max_results: int = 50) -> list[str]:
    """Return up to `max_results` unread inbox message IDs, most recent first."""
    response = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
        .execute()
    )
    return [item["id"] for item in response.get("messages", [])]


def get_message(service: Any, message_id: str) -> Message:
    """Fetch header metadata + snippet for one message (no body parsing)."""
    response = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=METADATA_HEADERS,
        )
        .execute()
    )
    headers = {
        header["name"].lower(): header["value"]
        for header in response.get("payload", {}).get("headers", [])
    }
    return Message(
        id=response["id"],
        thread_id=response["threadId"],
        subject=headers.get("subject", ""),
        from_address=headers.get("from", ""),
        message_id_header=headers.get("message-id", ""),
        references_header=headers.get("references", ""),
        snippet=response.get("snippet", ""),
    )
