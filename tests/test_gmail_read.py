from unittest.mock import MagicMock

from gmail.read import get_message, list_unread_message_ids


def _service_returning(list_response=None, get_response=None):
    service = MagicMock()
    if list_response is not None:
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = (
            list_response
        )
    if get_response is not None:
        service.users.return_value.messages.return_value.get.return_value.execute.return_value = (
            get_response
        )
    return service


def test_list_unread_message_ids_uses_correct_query_and_cap():
    service = _service_returning(
        list_response={"messages": [{"id": "a", "threadId": "t1"}, {"id": "b", "threadId": "t2"}]}
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
