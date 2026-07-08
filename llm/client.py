"""Gemini API client construction."""

from typing import Any

from google import genai

from config import GEMINI_API_KEY


def get_client() -> Any:
    """Return an authenticated Gemini API client."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set - add it to .env or the environment"
        )
    return genai.Client(api_key=GEMINI_API_KEY)
