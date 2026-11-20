import pytest
from julia_tool.config import load_config

_MIN = """
tenant_id: t
client_id: c
mailbox: office@firm.mx
responsible_email: boss@firm.mx
"""

def test_loads_defaults(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    cfg = load_config(str(p))
    assert cfg.poll_interval_s == 300
    assert cfg.use_claude is False
    assert "sat.gob.mx" in cfg.allowed_domains
    assert cfg.keyword_map["URGENT"]

def test_missing_required_raises(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("tenant_id: t\n")
    with pytest.raises(ValueError):
        load_config(str(p))

def test_language_defaults_to_es(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    assert load_config(str(p)).language == "es"

def test_language_invalid_falls_back_to_es(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN + "language: fr\n")
    assert load_config(str(p)).language == "es"

def test_language_en_respected(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN + "language: EN\n")
    assert load_config(str(p)).language == "en"

def test_settings_path_default(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    assert load_config(str(p)).settings_path == "ui_settings.json"


def test_whatsapp_section_defaults_to_empty(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    assert load_config(str(p)).whatsapp == {}


def test_whatsapp_section_is_loaded(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN + "whatsapp:\n  enabled: true\n  phone_number_id: '123'\n"
                 "  recipients: ['528112345678']\n")
    wa = load_config(str(p)).whatsapp
    assert wa["enabled"] is True
    assert wa["phone_number_id"] == "123"
    assert wa["recipients"] == ["528112345678"]
