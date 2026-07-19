from unittest.mock import MagicMock

import pytest

from gmail.profile import get_display_name


def _service_returning(send_as_response):
    service = MagicMock()
    (
        service.users.return_value.settings.return_value.sendAs.return_value.list.return_value.execute.return_value
    ) = send_as_response
    return service


def test_returns_display_name_of_primary_entry():
    service = _service_returning(
        {
            "sendAs": [
                {
                    "sendAsEmail": "alias@example.com",
                    "displayName": "Alias Name",
                    "isPrimary": False,
                },
                {
                    "sendAsEmail": "user@example.com",
                    "displayName": "Example User",
                    "isPrimary": True,
                },
            ]
        }
    )

    assert get_display_name(service) == "Example User"
    service.users.return_value.settings.return_value.sendAs.return_value.list.assert_called_once_with(
        userId="me"
    )


def test_falls_back_to_local_part_of_email_when_display_name_is_empty():
    service = _service_returning(
        {
            "sendAs": [
                {
                    "sendAsEmail": "user@example.com",
                    "displayName": "",
                    "isPrimary": True,
                }
            ]
        }
    )

    assert get_display_name(service) == "user"


def test_raises_when_no_primary_entry_is_present():
    service = _service_returning(
        {
            "sendAs": [
                {
                    "sendAsEmail": "alias@example.com",
                    "displayName": "Alias Name",
                    "isPrimary": False,
                }
            ]
        }
    )

    with pytest.raises(ValueError):
        get_display_name(service)


def test_raises_when_send_as_list_is_empty():
    service = _service_returning({"sendAs": []})

    with pytest.raises(ValueError):
        get_display_name(service)
