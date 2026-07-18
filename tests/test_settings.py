import os
import stat
from julia_tool.settings import load_settings, save_settings, valid_email, DEFAULTS


def test_load_missing_returns_defaults(tmp_path):
    s = load_settings(str(tmp_path / "nope.json"))
    assert s == DEFAULTS
    assert s is not DEFAULTS  # a copy, not the shared default


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, {"alert_words": ["multa"], "responsible_email": "a@b.mx"})
    s = load_settings(p)
    assert s["alert_words"] == ["multa"]
    assert s["responsible_email"] == "a@b.mx"


def test_save_ignores_unknown_keys(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, {"alert_words": [], "responsible_email": "", "evil": "x"})
    assert "evil" not in load_settings(p)


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    with open(p, "w") as f:
        f.write("{not json")
    assert load_settings(p) == DEFAULTS


def test_save_file_permissions_owner_only(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, dict(DEFAULTS))
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_valid_email():
    assert valid_email("jefe@despacho.mx") is True
    assert valid_email("bad") is False
    assert valid_email("") is False
    assert valid_email("a@b") is False
