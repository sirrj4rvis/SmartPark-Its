"""validators.py — small shared input validators used by web + API blueprints."""
import re

# Pragmatic email check: one local part, an "@", then a dotted domain with a
# non-empty label on each side of the dot. Rejects things like "user@.com".
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))
