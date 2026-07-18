from julia_tool.classify import classify_text, DEFAULT_KEYWORDS

def test_requerimiento_is_urgent():
    c = classify_text("Se emite REQUERIMIENTO de obligaciones", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"
    assert "requerimiento" in c.matched
    assert c.act_type == "requerimiento"

def test_embargo_is_urgent():
    c = classify_text("notificacion de embargo precautorio", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"

def test_informative_is_info():
    c = classify_text("Acuse de recibo de su declaracion", DEFAULT_KEYWORDS)
    assert c.urgency == "INFO"

def test_highest_severity_wins():
    # contains both an INFO word (acuse) and URGENT word (sancion)
    c = classify_text("acuse y sancion aplicable", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"

def test_no_keyword_is_info_unknown():
    c = classify_text("texto neutro sin terminos", DEFAULT_KEYWORDS)
    assert c.urgency == "INFO"
    assert c.act_type == "desconocido"
