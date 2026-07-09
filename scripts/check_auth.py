"""Manual end-to-end check: obtain credentials and confirm they authenticate.

Run this once `credentials.json` (downloaded from the Google Cloud
Console) is in place at the repo root. The first run opens a browser
for one-time consent; subsequent runs should return instantly with no
browser prompt.
"""

from googleapiclient.discovery import build

from auth.google_auth import get_credentials


def main() -> None:
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated as: {profile['emailAddress']}")


if __name__ == "__main__":
    main()
