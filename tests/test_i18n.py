from julia_tool.i18n import t, resolve_lang, urgency_label, MESSAGES, URGENCY_LABELS


def test_resolve_lang_normalizes_and_defaults():
    assert resolve_lang("EN") == "en"
    assert resolve_lang(" es ") == "es"
    assert resolve_lang(None) == "es"
    assert resolve_lang("fr") == "es"


def test_t_formats_placeholders():
    assert t("cli.added", "en", rfc="XAXX") == "added XAXX"
    assert t("cli.added", "es", rfc="XAXX") == "agregado XAXX"


def test_t_unknown_key_raises():
    import pytest
    with pytest.raises(KeyError):
        t("nope.nope", "es")


def test_urgency_label_localized():
    assert urgency_label("URGENT", "es") == "URGENTE"
    assert urgency_label("URGENT", "en") == "URGENT"
    assert urgency_label("WEIRD", "es") == "WEIRD"


def test_catalogs_have_identical_keys():
    assert set(MESSAGES["es"]) == set(MESSAGES["en"])
    assert set(URGENCY_LABELS["es"]) == set(URGENCY_LABELS["en"])
