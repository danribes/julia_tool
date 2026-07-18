from julia_tool.models import EmailMessage, ClientCred, Classification, FetchResult
from julia_tool.pipeline import process_message

class _Cfg:
    allowed_domains = ["sat.gob.mx"]
    keyword_map = {"URGENT": ["requerimiento"], "ATTENTION": [], "INFO": []}
    portal = {"buzon_url": "https://sat.gob.mx/manual"}

class _Store:
    def __init__(self, cred): self._c = cred
    def get(self, rfc): return self._c

class _State:
    def __init__(self): self.processed = {}; self.audits = []; self.alerts = []
    def mark_processed(self, mid, outcome): self.processed[mid] = outcome
    def log_credential_use(self, rfc, purpose, outcome, ts):
        self.audits.append((rfc, purpose, outcome))
    def record_alert(self, rfc, urgency, ts): self.alerts.append((rfc, urgency))

class _Alerter:
    def __init__(self): self.calls = []
    def send_urgent(self, rfc, name, cls, pdf): self.calls.append(("urgent", rfc)); return "s"
    def send_quarantine(self, s, f, r): self.calls.append(("quarantine", r)); return "s"
    def send_unknown_client(self, s): self.calls.append(("unknown",)); return "s"
    def send_fetch_failed(self, rfc, name, url): self.calls.append(("failed", rfc)); return "s"

class _Fetcher:
    def __init__(self, result): self._r = result
    def fetch(self, cred, headless=True): return self._r

def _msg(frm="no-reply@sat.gob.mx", auth="spf=pass dkim=pass",
         body="Contribuyente XAXX010101000 requerimiento"):
    return EmailMessage("m1", "asunto", frm, auth, body, "2026-07-18T00:00:00Z")

_NOW = lambda: "2026-07-18T00:00:00Z"
_CRED = ClientCred("XAXX010101000", "ACME", "ciec", "pw", None, None, None)

def _classify_ok(_path):
    return Classification("URGENT", "requerimiento", None, ["requerimiento"])

def test_happy_path_sends_urgent():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "alert_sent"
    assert ("urgent", "XAXX010101000") in al.calls
    assert st.processed["m1"] == "alert_sent"
    assert st.audits and st.audits[0][2] == "ok"

def test_phishing_is_quarantined_no_credential_use():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(frm="evil@fake.com"), cfg=_Cfg(), store=_Store(_CRED), state=st,
        alerter=al, fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "quarantined"
    assert st.audits == []          # credentials never touched
    assert al.calls[0][0] == "quarantine"

def test_no_rfc_is_unknown_client():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="sin rfc aqui"), cfg=_Cfg(), store=_Store(None), state=st,
        alerter=al, fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "unknown_client"

def test_fetch_failure_sends_fallback():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(False, None, "boom", "/s.png")),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "fetch_failed"
    assert ("failed", "XAXX010101000") in al.calls
    assert st.audits[0][2] == "fail"

def test_dry_run_does_not_mark_processed():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW, dry_run=True)
    assert out == "alert_sent"
    assert st.processed == {}
