import base64
from email import message_from_bytes, policy
from unittest.mock import MagicMock

from gmail.draft import create_draft_reply
from gmail.read import Message


def _service():
    service = MagicMock()
    service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "id": "draft-1"
    }
    return service


def _decode_raw(kwargs):
    raw = kwargs["body"]["message"]["raw"]
    return message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)


def test_create_draft_reply_builds_threaded_mime_with_references():
    service = _service()
    message = Message(
        id="msg-1",
        thread_id="thread-1",
        subject="Meeting request",
        from_address="Jane <jane@example.com>",
        message_id_header="<abc123@mail.gmail.com>",
        references_header="<prev1@mail.gmail.com>",
        snippet="",
    )

    result = create_draft_reply(service, message, "Sure, let's meet Tuesday at 2pm.")

    assert result == {"id": "draft-1"}
    _, kwargs = service.users.return_value.drafts.return_value.create.call_args
    assert kwargs["userId"] == "me"
    assert kwargs["body"]["message"]["threadId"] == "thread-1"

    mime = _decode_raw(kwargs)
    assert mime["To"] == "Jane <jane@example.com>"
    assert mime["Subject"] == "Re: Meeting request"
    assert mime["In-Reply-To"] == "<abc123@mail.gmail.com>"
    assert mime["References"] == "<prev1@mail.gmail.com> <abc123@mail.gmail.com>"
    assert mime.get_content().strip() == "Sure, let's meet Tuesday at 2pm."


def test_create_draft_reply_does_not_double_prefix_re_subject():
    service = _service()
    message = Message(
        id="msg-2",
        thread_id="thread-2",
        subject="Re: Meeting request",
        from_address="jane@example.com",
        message_id_header="<def456@mail.gmail.com>",
        references_header="",
        snippet="",
    )

    create_draft_reply(service, message, "body")

    _, kwargs = service.users.return_value.drafts.return_value.create.call_args
    mime = _decode_raw(kwargs)
    assert mime["Subject"] == "Re: Meeting request"


def test_create_draft_reply_does_not_double_prefix_case_insensitive_re_subject():
    service = _service()
    message = Message(
        id="msg-2b",
        thread_id="thread-2b",
        subject="RE: Meeting request",
        from_address="jane@example.com",
        message_id_header="<def789@mail.gmail.com>",
        references_header="",
        snippet="",
    )

    create_draft_reply(service, message, "body")

    _, kwargs = service.users.return_value.drafts.return_value.create.call_args
    mime = _decode_raw(kwargs)
    assert mime["Subject"] == "RE: Meeting request"


def test_create_draft_reply_handles_no_prior_references():
    service = _service()
    message = Message(
        id="msg-3",
        thread_id="thread-3",
        subject="First contact",
        from_address="bob@example.com",
        message_id_header="<xyz@mail.gmail.com>",
        references_header="",
        snippet="",
    )

    create_draft_reply(service, message, "body")

    _, kwargs = service.users.return_value.drafts.return_value.create.call_args
    mime = _decode_raw(kwargs)
    assert mime["References"] == "<xyz@mail.gmail.com>"
