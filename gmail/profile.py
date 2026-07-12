"""Reading the Gmail account's own configured display name."""

from typing import Any


def get_display_name(service: Any) -> str:
    """Return the account's "send mail as" display name.

    Reads the `isPrimary` entry from `users.settings.sendAs.list` - the
    same name Gmail already shows in the From field of mail sent from
    this account. Falls back to the local part of that entry's
    `sendAsEmail` (before the `@`) if `displayName` is unset. Raises
    `ValueError` if no `isPrimary` entry is present at all, which would
    mean the API violated its own contract.
    """
    response = service.users().settings().sendAs().list(userId="me").execute()
    primary = next(
        (entry for entry in response.get("sendAs", []) if entry.get("isPrimary")),
        None,
    )
    if primary is None:
        raise ValueError("No isPrimary entry found in sendAs.list response")

    display_name = primary.get("displayName")
    if display_name:
        return str(display_name)
    return str(primary["sendAsEmail"]).split("@")[0]
