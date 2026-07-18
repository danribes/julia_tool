import json
import os
import re
import tempfile

DEFAULTS = {"alert_words": [], "responsible_email": ""}
_KEYS = tuple(DEFAULTS.keys())
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+\Z")


def valid_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s or ""))


def load_settings(path: str) -> dict:
    result = {"alert_words": list(DEFAULTS["alert_words"]),
              "responsible_email": DEFAULTS["responsible_email"]}
    if not path or not os.path.exists(path):
        return result
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return result
    if not isinstance(raw, dict):
        return result
    words = raw.get("alert_words")
    if isinstance(words, list):
        result["alert_words"] = [str(w) for w in words]
    email = raw.get("responsible_email")
    if isinstance(email, str):
        result["responsible_email"] = email
    return result


def save_settings(path: str, data: dict) -> None:
    clean = {k: data.get(k, DEFAULTS[k]) for k in _KEYS}
    dirname = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirname, prefix=".ui-settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
