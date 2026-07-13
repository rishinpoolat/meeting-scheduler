"""Creating threaded Gmail draft replies."""

import base64
from email.message import EmailMessage
from typing import Any

from gmail.read import Message
from llm.draft import DraftBody


def create_draft_reply(service: Any, message: Message, body: DraftBody) -> Any:
    """Create a Gmail draft that replies to `message`, threaded correctly.

    Sent as multipart/alternative (plain text + HTML) so richer clients
    render the boxed/bold HTML version while still degrading gracefully
    to the plain-text part elsewhere.
    """
    subject = message.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    if message.references_header:
        references = f"{message.references_header} {message.message_id_header}"
    else:
        references = message.message_id_header

    reply = EmailMessage()
    reply["To"] = message.from_address
    reply["Subject"] = subject
    reply["In-Reply-To"] = message.message_id_header
    reply["References"] = references
    reply.set_content(body.text)
    reply.add_alternative(body.html, subtype="html")

    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
    draft_body = {"message": {"raw": raw, "threadId": message.thread_id}}
    return service.users().drafts().create(userId="me", body=draft_body).execute()
