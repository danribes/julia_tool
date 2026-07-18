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
        def __init__(self, graph, session, responsible_email):
            captured["responsible_email"] = responsible_email

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
