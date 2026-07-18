from julia_tool.alert import Alerter
from julia_tool.models import Classification

class _FakeGraph:
    def __init__(self): self.sent = []
    def send_mail(self, session, to, subject, html_body, attachments):
        self.sent.append((to, subject, html_body, attachments))

def _alerter():
    return Alerter(_FakeGraph(), session=None, responsible_email="boss@firm.mx")

def test_urgent_subject_and_attachment():
    a = _alerter()
    cls = Classification("URGENT", "requerimiento", "2026-08-01", ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, ("doc.pdf", b"%PDF-1.4"))
    assert subj == "[URGENT][XAXX010101000] requerimiento"
    to, sent_subj, body, att = a.graph.sent[0]
    assert to == "boss@firm.mx"
    assert att and att[0][0] == "doc.pdf"
    assert "ACME" in body

def test_quarantine_names_reason():
    a = _alerter()
    subj = a.send_quarantine("Falso SAT", "evil@fake.com", "domain")
    assert "CUARENTENA" in subj
    assert a.graph.sent[0][3] is None  # no attachment

def test_fetch_failed_includes_url():
    a = _alerter()
    a.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    body = a.graph.sent[0][2]
    assert "https://sat.gob.mx/manual" in body

def test_quarantine_escapes_from_address():
    a = _alerter()
    a.send_quarantine("subj", "<img src=x onerror=alert(1)>@evil.com", "domain")
    body = a.graph.sent[0][2]
    assert "<img" not in body
    assert "&lt;img" in body


def test_urgent_escapes_client_name():
    a = _alerter()
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    a.send_urgent("XAXX010101000", "<b>Evil</b>", cls, None)
    body = a.graph.sent[0][2]
    assert "<b>Evil</b>" not in body
    assert "&lt;b&gt;Evil" in body
