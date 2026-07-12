"""Listing unread Gmail messages and fetching their reply-relevant metadata."""

import base64
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


def list_unread_message_ids(
    service: Any, max_results: int = 50, newer_than_days: int | None = None
) -> list[str]:
    """Return up to `max_results` unread inbox message IDs, most recent first.

    `newer_than_days`, if given, restricts to messages Gmail considers
    newer than that many days old (its `newer_than:Nd` search operator)
    on top of the `max_results` cap - the two combine, they don't
    replace each other.
    """
    kwargs: dict[str, Any] = {
        "userId": "me",
        "labelIds": ["INBOX", "UNREAD"],
        "maxResults": max_results,
    }
    if newer_than_days is not None:
        kwargs["q"] = f"newer_than:{newer_than_days}d"
    response = service.users().messages().list(**kwargs).execute()
    return [item["id"] for item in response.get("messages", [])]


def mark_as_read(service: Any, message_id: str) -> None:
    """Remove the UNREAD label so a processed message isn't reclassified next run."""
    service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


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


def get_message_body(service: Any, message_id: str) -> str:
    """Fetch and return the plain-text body of a message.

    Recursively walks payload.parts, returning the first inline (i.e. not
    Content-Disposition: attachment) text/plain leaf found in document
    order. Returns "" for HTML-only emails and for bodies large enough that
    Gmail omits inline data (attachmentId-only parts) — no HTML-to-text
    conversion or attachment fetching is performed.
    """
    response = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    return _find_plain_text(response.get("payload", {})) or ""


def _find_plain_text(payload: dict[str, Any]) -> str | None:
    data = payload.get("body", {}).get("data")
    if payload.get("mimeType") == "text/plain" and data and not _is_attachment(payload):
        return _decode_body_data(data)
    for part in payload.get("parts") or []:
        found = _find_plain_text(part)
        if found is not None:
            return found
    return None


def _is_attachment(payload: dict[str, Any]) -> bool:
    disposition = next(
        (
            header["value"]
            for header in payload.get("headers") or []
            if header["name"].lower() == "content-disposition"
        ),
        "",
    )
    return disposition.lower().startswith("attachment")


def _decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
