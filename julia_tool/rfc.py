import re

_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")

def extract_rfc(text: str) -> str | None:
    m = _RFC_RE.search(text.upper())
    return m.group(0) if m else None
