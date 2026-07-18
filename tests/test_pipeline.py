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

class _BoomFetcher:
    def fetch(self, cred, headless=True):
        raise AssertionError("dry-run must never call fetch()")

def _msg(frm="no-reply@sat.gob.mx", auth="spf=pass dkim=pass",
         body="Contribuyente XAXX010101000 requerimiento"):
    return EmailMessage("m1", "asunto", frm, auth, body, "2026-07-18T00:00:00Z")

_NOW = lambda: "2026-07-18T00:00:00Z"
_CRED = ClientCred("XAXX010101000", "ACME", "ciec", "pw", None, None, None)

def _classify_ok(_path):
    return Classification("URGENT", "requerimiento", None, ["requerimiento"])

def _classify_boom(_path):
    raise ValueError("corrupt pdf")

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

def test_rfc_found_but_no_credential_is_unknown_client():
    st = _State(); al = _Alerter()

    class _NoFetch:
        def __init__(self):
            self.called = False

        def fetch(self, cred, headless=True):
            self.called = True
            return FetchResult(True, "/x.pdf", None, None)

    nf = _NoFetch()
    out = process_message(
        _msg(body="Contribuyente XAXX010101000 requerimiento"),
        cfg=_Cfg(), store=_Store(None), state=st, alerter=al,
        fetcher=nf, classify_pdf=_classify_ok, now=_NOW)
    assert out == "unknown_client"
    assert ("unknown",) in al.calls
    assert st.audits == []        # RFC known but no credential → no credential use
    assert nf.called is False     # fetch never reached

def test_classify_crash_is_fetch_failed():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_boom, now=_NOW)
    assert out == "fetch_failed"          # corrupt PDF → fallback, not a crash
    assert ("failed", "XAXX010101000") in al.calls
    assert st.audits[0][2] == "ok"        # fetch succeeded; classification failed

def test_dry_run_sends_nothing_and_no_credential_use():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_BoomFetcher(),        # would raise if fetch() were called
        classify_pdf=_classify_ok, now=_NOW, dry_run=True)
    assert out == "alert_sent"
    assert st.processed == {}          # not marked processed
    assert st.alerts == []             # no alert recorded
    assert st.audits == []             # no credential use logged
    assert al.calls == []              # no mail sent

def test_dry_run_quarantine_sends_nothing():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(frm="evil@fake.com"), cfg=_Cfg(), store=_Store(_CRED), state=st,
        alerter=al, fetcher=_BoomFetcher(),
        classify_pdf=_classify_ok, now=_NOW, dry_run=True)
    assert out == "quarantined"
    assert st.processed == {}
    assert al.calls == []              # dry-run does not even send the quarantine notice

def _reader_ok(_path):
    return "cuerpo del documento con multa aplicada"

def test_forward_gate_match_sends():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["multa"], read_pdf_text=_reader_ok)
    assert out == "alert_sent"
    assert ("urgent", "XAXX010101000") in al.calls

def test_forward_gate_no_match_not_forwarded():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="Contribuyente XAXX010101000 texto sin terminos"), cfg=_Cfg(), store=_Store(_CRED),
        state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["embargo"], read_pdf_text=lambda p: "nada relevante")
    assert out == "not_forwarded"
    assert al.calls == []                 # no alert sent
    assert st.processed["m1"] == "not_forwarded"
    assert st.audits and st.audits[0][2] == "ok"   # fetch still audited

def test_forward_gate_empty_words_forwards():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=[], read_pdf_text=lambda p: "nada")
    assert out == "alert_sent"

def test_forward_gate_matches_on_email_when_doc_lacks_it():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="Contribuyente XAXX010101000 con embargo precautorio"),
        cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["embargo"], read_pdf_text=lambda p: "documento sin la palabra")
    assert out == "alert_sent"
