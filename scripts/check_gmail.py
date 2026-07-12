"""Manual end-to-end check: list unread messages and draft a reply to one.

Run this against a real Gmail inbox once auth is set up (see
check_auth.py). Lists up to 50 unread inbox messages, then creates a
placeholder draft reply to the first one so you can confirm it threads
correctly in Gmail's UI. Real reply content comes later (Feature 4).
"""

from gmail.client import get_service
from gmail.draft import create_draft_reply
from gmail.profile import get_display_name
from gmail.read import get_message, list_unread_message_ids

PLACEHOLDER_BODY = (
    "Thanks for your message! This is a placeholder reply from the "
    "meeting-scheduler agent — automatic scheduling logic isn't wired "
    "up yet."
)


def main() -> None:
    service = get_service()

    print(f"Account display name: {get_display_name(service)}")

    message_ids = list_unread_message_ids(service)
    print(f"{len(message_ids)} unread message(s):")
    messages = [get_message(service, message_id) for message_id in message_ids]
    for message in messages:
        print(f"- [{message.id}] {message.from_address} — {message.subject}")
        print(f"    {message.snippet}")

    if not messages:
        print("No unread messages to draft a reply to.")
        return

    draft = create_draft_reply(service, messages[0], PLACEHOLDER_BODY)
    print(f"\nCreated draft id={draft['id']} replying to: {messages[0].subject}")


if __name__ == "__main__":
    main()
