"""Cryptographic feedback token module.

Uses itsdangerous URLSafeTimedSerializer with HMAC signing to generate
and verify tamper-proof, time-limited feedback tokens that embed
user_id, content_id, and rating in a single URL-safe string.
"""

import logging

from itsdangerous import URLSafeTimedSerializer

from app.config import FEEDBACK_TOKEN_SECRET

logger = logging.getLogger(__name__)

# 30 days in seconds
FEEDBACK_TOKEN_MAX_AGE = 30 * 24 * 60 * 60  # 2,592,000 seconds

_serializer = URLSafeTimedSerializer(FEEDBACK_TOKEN_SECRET, salt="briefly-feedback")


def generate_feedback_token(user_id: int, content_id: int, rating: int) -> str:
    """Generate a signed, URL-safe feedback token.

    Args:
        user_id: The subscriber's database ID.
        content_id: The article's database ID.
        rating: +1 (relevant) or -1 (not for me).

    Returns:
        A URL-safe signed token string.
    """
    if rating not in (-1, 1):
        raise ValueError(f"Rating must be -1 or 1, got {rating}")
    payload = {"u": user_id, "c": content_id, "r": rating}
    return _serializer.dumps(payload)


def verify_feedback_token(token: str) -> dict:
    """Verify and decode a feedback token.

    Args:
        token: The URL-safe signed token string.

    Returns:
        Dictionary with keys: user_id, content_id, rating.

    Raises:
        SignatureExpired: If the token is older than 30 days.
        BadSignature: If the token has been tampered with.
    """
    payload = _serializer.loads(token, max_age=FEEDBACK_TOKEN_MAX_AGE)
    return {
        "user_id": payload["u"],
        "content_id": payload["c"],
        "rating": payload["r"],
    }
