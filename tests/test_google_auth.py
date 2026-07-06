import json
from unittest.mock import MagicMock, mock_open, patch

from google.auth.exceptions import RefreshError

from auth import google_auth


def test_valid_cached_token_is_returned_without_refresh_or_flow():
    cached_creds = MagicMock(valid=True)

    with (
        patch("auth.google_auth.os.path.exists", return_value=True),
        patch(
            "auth.google_auth.Credentials.from_authorized_user_file",
            return_value=cached_creds,
        ),
        patch("auth.google_auth.InstalledAppFlow") as mock_flow,
    ):
        result = google_auth.get_credentials()

    assert result is cached_creds
    cached_creds.refresh.assert_not_called()
    mock_flow.from_client_secrets_file.assert_not_called()


def test_expired_token_with_refresh_token_is_refreshed_and_saved():
    cached_creds = MagicMock(valid=False, expired=True, refresh_token="refresh-me")
    cached_creds.to_json.return_value = '{"refreshed": true}'

    with (
        patch("auth.google_auth.os.path.exists", return_value=True),
        patch(
            "auth.google_auth.Credentials.from_authorized_user_file",
            return_value=cached_creds,
        ),
        patch("auth.google_auth.InstalledAppFlow") as mock_flow,
        patch("builtins.open", mock_open()) as mocked_open,
        patch("auth.google_auth.os.chmod"),
    ):
        result = google_auth.get_credentials()

    assert result is cached_creds
    cached_creds.refresh.assert_called_once()
    mock_flow.from_client_secrets_file.assert_not_called()
    mocked_open().write.assert_called_once_with('{"refreshed": true}')


def test_refresh_failure_falls_back_to_interactive_flow():
    cached_creds = MagicMock(valid=False, expired=True, refresh_token="refresh-me")
    cached_creds.refresh.side_effect = RefreshError("invalid_grant")

    new_creds = MagicMock()
    new_creds.to_json.return_value = '{"new": true}'
    mock_flow_instance = MagicMock()
    mock_flow_instance.run_local_server.return_value = new_creds

    with (
        patch("auth.google_auth.os.path.exists", return_value=True),
        patch(
            "auth.google_auth.Credentials.from_authorized_user_file",
            return_value=cached_creds,
        ),
        patch("auth.google_auth.InstalledAppFlow") as mock_flow,
        patch("builtins.open", mock_open()) as mocked_open,
        patch("auth.google_auth.os.chmod"),
    ):
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        result = google_auth.get_credentials()

    assert result is new_creds
    mock_flow.from_client_secrets_file.assert_called_once_with(
        google_auth.CREDENTIALS_PATH, google_auth.SCOPES
    )
    mocked_open().write.assert_called_once_with('{"new": true}')


def test_missing_token_file_runs_interactive_flow():
    new_creds = MagicMock()
    new_creds.to_json.return_value = '{"new": true}'
    mock_flow_instance = MagicMock()
    mock_flow_instance.run_local_server.return_value = new_creds

    with (
        patch("auth.google_auth.os.path.exists", return_value=False),
        patch(
            "auth.google_auth.Credentials.from_authorized_user_file"
        ) as mock_from_file,
        patch("auth.google_auth.InstalledAppFlow") as mock_flow,
        patch("builtins.open", mock_open()) as mocked_open,
        patch("auth.google_auth.os.chmod"),
    ):
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        result = google_auth.get_credentials()

    mock_from_file.assert_not_called()
    assert result is new_creds
    mocked_open().write.assert_called_once_with('{"new": true}')


def test_corrupt_token_file_is_treated_like_missing():
    new_creds = MagicMock()
    new_creds.to_json.return_value = '{"new": true}'
    mock_flow_instance = MagicMock()
    mock_flow_instance.run_local_server.return_value = new_creds

    with (
        patch("auth.google_auth.os.path.exists", return_value=True),
        patch(
            "auth.google_auth.Credentials.from_authorized_user_file",
            side_effect=json.JSONDecodeError("bad json", "doc", 0),
        ),
        patch("auth.google_auth.InstalledAppFlow") as mock_flow,
        patch("builtins.open", mock_open()) as mocked_open,
        patch("auth.google_auth.os.chmod"),
    ):
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        result = google_auth.get_credentials()

    assert result is new_creds
    mock_flow.from_client_secrets_file.assert_called_once()
    mocked_open().write.assert_called_once_with('{"new": true}')
