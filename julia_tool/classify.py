from julia_tool.models import Classification

DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "URGENT": [
        "requerimiento", "multa", "sancion", "sanción", "embargo",
        "credito fiscal", "crédito fiscal", "pama", "visita domiciliaria",
        "69-b", "presuncion", "presunción", "determinacion", "determinación",
    ],
    "ATTENTION": [
        "invitacion", "invitación", "carta invitacion", "aclaracion",
        "aclaración", "revision", "revisión", "plazo", "vencimiento",
    ],
    "INFO": [
        "acuse", "constancia", "aviso", "notificacion", "notificación",
        "informativo",
    ],
}

_ORDER = ["URGENT", "ATTENTION", "INFO"]

def classify_text(text: str, keyword_map: dict[str, list[str]]) -> Classification:
    low = text.lower()
    for level in _ORDER:
        matched = [kw for kw in keyword_map.get(level, []) if kw in low]
        if matched:
            return Classification(
                urgency=level, act_type=matched[0],
                deadline=None, matched=matched,
            )
    return Classification(
        urgency="INFO", act_type="desconocido", deadline=None, matched=[])


def extract_pdf_text(pdf_path: str) -> str:
    import fitz  # PyMuPDF
    parts = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts)
