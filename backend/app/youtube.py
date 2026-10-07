import re

YOUTUBE_PATTERNS = [
    r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    r"[?&]v=([a-zA-Z0-9_-]{11})",
]


def extract_youtube_id(raw: str) -> str | None:
    """
    Extract the 11-character YouTube video ID from various URL formats or return bare ID.
    Returns None if the input is invalid or cannot be parsed.
    """
    if not raw:
        return None
    raw = raw.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", raw):
        return raw
    for pattern in YOUTUBE_PATTERNS:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return None
