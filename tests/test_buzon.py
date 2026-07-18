import pytest
from julia_tool.models import ClientCred
from julia_tool.buzon import BuzonFetcher

def _fetcher(tmp_path):
    portal = {"efirma_login_url": "x", "ciec_login_url": "y",
              "notifications_selector": "tr", "download_link_selector": "a"}
    return BuzonFetcher(portal, str(tmp_path))

def test_download_path_format(tmp_path):
    f = _fetcher(tmp_path)
    p = f._download_path("XAXX010101000")
    assert p.endswith("XAXX010101000_1.pdf")

def test_unknown_auth_type_returns_error(tmp_path):
    f = _fetcher(tmp_path)
    cred = ClientCred("XAXX010101000", "ACME", "unknown",
                      None, None, None, None)
    # inject a fake browser factory that must never be called for unknown type
    res = f.fetch(cred, headless=True, _browser_factory=lambda headless: None)
    assert res.ok is False
    assert "auth_type" in res.error

def test_dispatch_routes_efirma(tmp_path, monkeypatch):
    f = _fetcher(tmp_path)
    called = {}
    monkeypatch.setattr(f, "_fetch_efirma",
                        lambda cred, browser: called.setdefault("efirma", True))
    cred = ClientCred("XAXX010101000", "ACME", "efirma",
                      None, "/c.cer", "/k.key", "pw")
    f.fetch(cred, headless=True, _browser_factory=lambda headless: object())
    assert called.get("efirma") is True
