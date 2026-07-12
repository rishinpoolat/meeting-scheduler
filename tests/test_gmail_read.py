import base64
from unittest.mock import MagicMock

from gmail.read import (
    get_message,
    get_message_body,
    list_unread_message_ids,
    mark_as_read,
)


def _b64url_nopad(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _service_returning(list_response=None, get_response=None):
    service = MagicMock()
    if list_response is not None:
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = list_response
    if get_response is not None:
        service.users.return_value.messages.return_value.get.return_value.execute.return_value = get_response
    return service


def test_list_unread_message_ids_uses_correct_query_and_cap():
    service = _service_returning(
        list_response={
            "messages": [{"id": "a", "threadId": "t1"}, {"id": "b", "threadId": "t2"}]
        }
    )

    result = list_unread_message_ids(service, max_results=50)

    assert result == ["a", "b"]
    service.users.return_value.messages.return_value.list.assert_called_once_with(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=50
    )


def test_list_unread_message_ids_handles_empty_inbox():
    service = _service_returning(list_response={})

    result = list_unread_message_ids(service)

    assert result == []


def test_list_unread_message_ids_adds_newer_than_query_when_given():
    service = _service_returning(list_response={"messages": [{"id": "a"}]})

    result = list_unread_message_ids(service, max_results=5, newer_than_days=2)

    assert result == ["a"]
    service.users.return_value.messages.return_value.list.assert_called_once_with(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=5, q="newer_than:2d"
    )


def test_list_unread_message_ids_omits_query_when_newer_than_days_is_none():
    service = _service_returning(list_response={"messages": []})

    list_unread_message_ids(service, max_results=50, newer_than_days=None)

    call_kwargs = service.users.return_value.messages.return_value.list.call_args.kwargs
    assert "q" not in call_kwargs


def test_mark_as_read_removes_unread_label():
    service = MagicMock()

    mark_as_read(service, "msg-1")

    service.users.return_value.messages.return_value.modify.assert_called_once_with(
        userId="me", id="msg-1", body={"removeLabelIds": ["UNREAD"]}
    )


def test_get_message_parses_headers_case_insensitively():
    service = _service_returning(
        get_response={
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "Hey, are you free Tuesday?",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Meeting request"},
                    {"name": "From", "value": "Jane <jane@example.com>"},
                    {"name": "Message-ID", "value": "<abc123@mail.gmail.com>"},
                    {"name": "References", "value": "<prev1@mail.gmail.com>"},
                ]
            },
        }
    )

    message = get_message(service, "msg-1")

    assert message.id == "msg-1"
    assert message.thread_id == "thread-1"
    assert message.subject == "Meeting request"
    assert message.from_address == "Jane <jane@example.com>"
    assert message.message_id_header == "<abc123@mail.gmail.com>"
    assert message.references_header == "<prev1@mail.gmail.com>"
    assert message.snippet == "Hey, are you free Tuesday?"
    service.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me",
        id="msg-1",
        format="metadata",
        metadataHeaders=["From", "Subject", "Message-Id", "References"],
    )


def test_get_message_handles_missing_references_header():
    service = _service_returning(
        get_response={
            "id": "msg-2",
            "threadId": "thread-2",
            "snippet": "",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "First contact"},
                    {"name": "From", "value": "bob@example.com"},
                    {"name": "Message-Id", "value": "<xyz@mail.gmail.com>"},
                ]
            },
        }
    )

    message = get_message(service, "msg-2")

    assert message.references_header == ""
    assert message.message_id_header == "<xyz@mail.gmail.com>"


def test_get_message_body_single_part_plain_text():
    service = _service_returning(
        get_response={
            "payload": {
                "mimeType": "text/plain",
                "body": {"data": _b64url_nopad("Hello there")},
            }
        }
    )

    assert get_message_body(service, "msg-1") == "Hello there"


def test_get_message_body_multipart_mixed_prefers_plain_text_over_attachment():
    service = _service_returning(
        get_response={
            "payload": {
                "mimeType": "multipart/mixed",
                "parts": [
                    {"mimeType": "application/pdf", "body": {"attachmentId": "att-1"}},
                    {
                        "mimeType": "text/plain",
                        "body": {"data": _b64url_nopad("Body text")},
                    },
                ],
            }
        }
    )

    assert get_message_body(service, "msg-2") == "Body text"


def test_get_message_body_skips_text_plain_attachment_for_real_body():
    service = _service_returning(
        get_response={
            "payload": {
                "mimeType": "multipart/mixed",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "headers": [
                            {
                                "name": "Content-Disposition",
                                "value": 'attachment; filename="notes.txt"',
                            }
                        ],
                        "body": {"data": _b64url_nopad("Attachment contents")},
                    },
                    {
                        "mimeType": "text/plain",
                        "body": {"data": _b64url_nopad("Real body text")},
                    },
                ],
            }
        }
    )

    assert get_message_body(service, "msg-8") == "Real body text"


def test_get_message_body_nested_multipart_alternative_prefers_plain_over_html():
    service = _service_returning(
        get_response={
            "payload": {
                "mimeType": "multipart/mixed",
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _b64url_nopad("Plain version")},
                            },
                            {
                                "mimeType": "text/html",
                                "body": {"data": _b64url_nopad("<p>HTML version</p>")},
                            },
                        ],
                    }
                ],
            }
        }
    )

    assert get_message_body(service, "msg-3") == "Plain version"


def test_get_message_body_returns_empty_string_for_html_only_email():
    service = _service_returning(
        get_response={
            "payload": {
                "mimeType": "text/html",
                "body": {"data": _b64url_nopad("<p>Only HTML</p>")},
            }
        }
    )

    assert get_message_body(service, "msg-4") == ""


def test_get_message_body_decodes_unpadded_base64url():
    service = _service_returning(
        get_response={
            "payload": {"mimeType": "text/plain", "body": {"data": _b64url_nopad("A")}}
        }
    )

    assert get_message_body(service, "msg-5") == "A"


def test_get_message_body_requests_format_full():
    service = _service_returning(get_response={"payload": {}})

    get_message_body(service, "msg-6")

    service.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me", id="msg-6", format="full"
    )


def test_get_message_body_handles_payload_with_no_body_and_no_parts():
    service = _service_returning(get_response={"payload": {}})

    assert get_message_body(service, "msg-7") == ""
