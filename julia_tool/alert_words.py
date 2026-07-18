import unicodedata


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def parse_words(raw: str) -> list[str]:
    seen = set()
    out = []
    for part in raw.split(","):
        w = part.strip()
        if not w:
            continue
        key = w.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def should_forward(text: str, words: list[str]) -> bool:
    if not words:
        return True
    haystack = normalize(text)
    return any(normalize(w) in haystack for w in words)
