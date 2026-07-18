from julia_tool.alert_words import parse_words, normalize, should_forward


def test_parse_words_splits_trims_dedupes():
    assert parse_words("multa,  sanción ,multa,, requerimiento ") == \
        ["multa", "sanción", "requerimiento"]
    assert parse_words("") == []
    assert parse_words("   ") == []


def test_normalize_strips_accents_and_case():
    assert normalize("Sanción") == normalize("sancion")
    assert normalize("REQUERIMIENTO") == "requerimiento"


def test_should_forward_empty_words_forwards_all():
    assert should_forward("cualquier texto", []) is True


def test_should_forward_matches_accent_insensitive():
    assert should_forward("Se emite una SANCIÓN", ["sancion"]) is True
    assert should_forward("aviso informativo", ["sancion"]) is False


def test_should_forward_substring_match():
    assert should_forward("acuse de requerimiento fiscal", ["requerimiento"]) is True
