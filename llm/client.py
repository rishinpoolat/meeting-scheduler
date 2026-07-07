"""Anthropic API client construction."""

from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY


def get_client() -> Any:
    """Return an authenticated Anthropic API client."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set - add it to .env or the environment"
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
