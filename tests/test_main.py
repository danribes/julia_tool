from julia_tool import main as main_mod


class _FakeGraph:
    def list_messages(self, session):
        return []


class _FakeCfg:
    responsible_email = "default@example.com"
    allowed_domains = ["sat.gob.mx"]
    keyword_map = {}
    portal = {}


def _capture_alerter(monkeypatch):
    captured = {}

    class _FakeAlerter:
        def __init__(self, graph, session, responsible_email, lang="es"):
            captured["responsible_email"] = responsible_email
            captured["lang"] = lang

    monkeypatch.setattr(main_mod, "Alerter", _FakeAlerter)
    return captured


def test_run_once_uses_responsible_override_when_given(monkeypatch):
    captured = _capture_alerter(monkeypatch)

    tally = main_mod.run_once(
        _FakeCfg(), store=None, state=None, graph=_FakeGraph(), session=None,
        fetcher=None, responsible="override@example.com")

    assert captured["responsible_email"] == "override@example.com"
    assert tally == {}


def test_run_once_falls_back_to_cfg_responsible_email_when_no_override(monkeypatch):
    captured = _capture_alerter(monkeypatch)

    tally = main_mod.run_once(
        _FakeCfg(), store=None, state=None, graph=_FakeGraph(), session=None,
        fetcher=None)

    assert captured["responsible_email"] == "default@example.com"
    assert tally == {}


def test_parser_default_responsible_is_none():
    ns = main_mod._build_parser().parse_args(["--once"])
    assert ns.responsible is None


def test_parser_accepts_responsible_override():
    ns = main_mod._build_parser().parse_args(
        ["--responsible", "cli@example.com", "--once"])
    assert ns.responsible == "cli@example.com"


def test_main_resolves_responsible_or_falls_back_to_cfg(monkeypatch):
    # Exercise the exact resolution expression used inside main():
    # `ns.responsible or cfg.responsible_email`.
    ns = main_mod._build_parser().parse_args(
        ["--responsible", "override@example.com", "--once"])
    cfg = _FakeCfg()
    assert (ns.responsible or cfg.responsible_email) == "override@example.com"

    ns2 = main_mod._build_parser().parse_args(["--once"])
    assert (ns2.responsible or cfg.responsible_email) == "default@example.com"


def test_run_once_skips_duplicates_without_processing():
    from types import SimpleNamespace
    from julia_tool.models import EmailMessage
    from julia_tool.main import run_once

    def _mk(mid):
        return EmailMessage(id=mid, subject="s", from_address="x@sat.gob.mx",
                            auth_results="spf=pass; dkim=pass", body="b", received="t")

    class _Graph:
        def list_messages(self, session, top=25):
            return [_mk("m1"), _mk("m2")]

        def send_mail(self, *a, **k):
            raise AssertionError("must not send mail for duplicates")

    class _State:
        def is_processed(self, mid):
            return True

        def mark_processed(self, *a, **k):
            raise AssertionError("must not re-mark duplicates")

    class _Store:
        def get(self, rfc):
            raise AssertionError("must not access credentials for duplicates")

    cfg = SimpleNamespace(responsible_email="boss@firm.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={})
    tally = run_once(cfg, _Store(), _State(), _Graph(), None, None)
    assert tally == {"skipped_duplicate": 2}


def test_run_once_passes_lang_to_alerter():
    from types import SimpleNamespace
    from julia_tool.models import EmailMessage
    from julia_tool.main import run_once

    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["subject"] = subject

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="boss@firm.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={})
    run_once(cfg, None, _State(), _Graph(), None, None, lang="en")
    assert "QUARANTINE" in captured["subject"]   # English alert emitted

def test_parser_accepts_lang():
    from julia_tool.main import _build_parser
    ns = _build_parser().parse_args(["--lang", "en", "--once"])
    assert ns.lang == "en"


def test_run_once_recipient_precedence_settings_over_config(tmp_path):
    from types import SimpleNamespace
    from julia_tool.main import run_once
    from julia_tool.settings import save_settings
    from julia_tool.models import EmailMessage

    sp = str(tmp_path / "ui_settings.json")
    save_settings(sp, {"alert_words": [], "responsible_email": "ui@x.mx"})
    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["to"] = to

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="cfg@x.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={},
                          settings_path=sp)
    run_once(cfg, None, _State(), _Graph(), None, None)
    assert captured["to"] == "ui@x.mx"  # settings beat config; not overridden by flag


def test_run_once_flag_beats_settings(tmp_path):
    from types import SimpleNamespace
    from julia_tool.main import run_once
    from julia_tool.settings import save_settings
    from julia_tool.models import EmailMessage

    sp = str(tmp_path / "ui_settings.json")
    save_settings(sp, {"alert_words": [], "responsible_email": "ui@x.mx"})
    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["to"] = to

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="cfg@x.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={},
                          settings_path=sp)
    run_once(cfg, None, _State(), _Graph(), None, None, responsible="flag@x.mx")
    assert captured["to"] == "flag@x.mx"


def test_parser_accepts_port():
    from julia_tool.main import _build_parser
    ns = _build_parser().parse_args(["--port", "9001", "--once"])
    assert ns.port == 9001


def test_main_end_to_end_honors_settings_recipient(tmp_path, monkeypatch):
    import julia_tool.main as M
    from types import SimpleNamespace
    from julia_tool.settings import save_settings
    from julia_tool.models import EmailMessage, ClientCred, FetchResult, Classification

    sp = str(tmp_path / "ui_settings.json")
    save_settings(sp, {"alert_words": [], "responsible_email": "ui@despacho.mx"})

    cfg = SimpleNamespace(
        tenant_id="t", client_id="c", mailbox="m@x",
        responsible_email="cfg@despacho.mx", allowed_domains=["sat.gob.mx"],
        keyword_map={"URGENT": ["requerimiento"], "ATTENTION": [], "INFO": []},
        portal={"buzon_url": "https://sat.gob.mx"}, settings_path=sp,
        secrets_path="x", state_path="y", download_dir="z", language="es",
        poll_interval_s=1)
    monkeypatch.setattr(M, "load_config", lambda path: cfg)

    sent = {}

    class _Graph:
        def __init__(self, *a): pass
        def acquire_token(self, prompt=True): return "tok"
        def session(self, token): return None
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "asunto", "no-reply@sat.gob.mx",
                                 "spf=pass dkim=pass",
                                 "Contribuyente XAXX010101000", "t")]
        def send_mail(self, session, to, subject, body, att):
            sent["to"] = to

    class _Store:
        def __init__(self, *a): pass
        def get(self, rfc):
            return ClientCred("XAXX010101000", "ACME", "ciec", "pw",
                              None, None, None)

    class _State:
        def __init__(self, *a): pass
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass
        def log_credential_use(self, *a, **k): pass
        def record_alert(self, *a, **k): pass

    class _Fetcher:
        def __init__(self, *a): pass
        def fetch(self, cred, headless=True):
            return FetchResult(True, "/x.pdf", None, None)

    monkeypatch.setattr(M, "GraphClient", _Graph)
    monkeypatch.setattr(M, "SecretsStore", _Store)
    monkeypatch.setattr(M, "State", _State)
    monkeypatch.setattr(M, "BuzonFetcher", _Fetcher)
    monkeypatch.setattr(M, "extract_pdf_text", lambda p: "documento")
    monkeypatch.setattr(M, "classify_text",
                        lambda text, km: Classification("URGENT", "requerimiento",
                                                        None, ["requerimiento"]))
    monkeypatch.setenv("JULIA_MASTER_PW", "x")

    rc = M.main(["--once"])
    assert rc == 0
    assert sent.get("to") == "ui@despacho.mx"   # settings recipient wins, NOT cfg@


# ---- WhatsApp wiring ----

def _wa_cfg(**wa):
    from types import SimpleNamespace
    return SimpleNamespace(whatsapp=wa, language="es")


def test_build_whatsapp_disabled_returns_none():
    assert main_mod.build_whatsapp(_wa_cfg(), env={}) is None
    assert main_mod.build_whatsapp(_wa_cfg(enabled=False, phone_number_id="1",
                                           recipients=["528112345678"]), env={"JULIA_WA_TOKEN": "x"}) is None


def test_build_whatsapp_without_token_returns_none_and_warns():
    logs = []
    n = main_mod.build_whatsapp(_wa_cfg(enabled=True, phone_number_id="1", recipients=["528112345678"]),
                                env={}, log=logs.append)
    assert n is None
    assert any("JULIA_WA_TOKEN" in line for line in logs)


def test_build_whatsapp_configured_returns_notifier_with_defaults():
    from julia_tool.whatsapp import WhatsAppNotifier
    n = main_mod.build_whatsapp(_wa_cfg(enabled=True, phone_number_id="1",
                                        recipients=["+52 81 1234 5678"]),
                                env={"JULIA_WA_TOKEN": "tok"})
    assert isinstance(n, WhatsAppNotifier)
    assert n.recipients == ["528112345678"]
    assert n.template == "julia_aviso_sat"
    assert n.lang_code == "es_MX"


def test_run_once_passes_whatsapp_to_alerter(monkeypatch):
    captured = {}

    class _FakeAlerter:
        def __init__(self, graph, session, responsible_email, lang="es", whatsapp=None):
            captured["whatsapp"] = whatsapp

    monkeypatch.setattr(main_mod, "Alerter", _FakeAlerter)
    from types import SimpleNamespace
    cfg = SimpleNamespace(responsible_email="b@x.mx", keyword_map={}, allowed_domains=["sat.gob.mx"],
                          portal={})
    sentinel = object()
    main_mod.run_once(cfg, None, None, _FakeGraph(), None, None, whatsapp=sentinel)
    assert captured["whatsapp"] is sentinel


def test_build_whatsapp_incomplete_or_invalid_config_warns_and_returns_none():
    logs = []
    assert main_mod.build_whatsapp(_wa_cfg(enabled=True), env={"JULIA_WA_TOKEN": "x"},
                                   log=logs.append) is None
    assert main_mod.build_whatsapp(_wa_cfg(enabled=True, phone_number_id="1", recipients=["123"]),
                                   env={"JULIA_WA_TOKEN": "x"}, log=logs.append) is None
    assert len(logs) == 2 and all("WhatsApp" in line for line in logs)
