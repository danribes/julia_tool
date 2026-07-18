from julia_tool.alert import Alerter
from julia_tool.models import Classification

class _FakeGraph:
    def __init__(self): self.sent = []
    def send_mail(self, session, to, subject, html_body, attachments):
        self.sent.append((to, subject, html_body, attachments))

def _alerter(lang="es"):
    return Alerter(_FakeGraph(), session=None, responsible_email="boss@firm.mx", lang=lang)

def test_urgent_subject_es_localizes_urgency_tag():
    a = _alerter("es")
    cls = Classification("URGENT", "requerimiento", "2026-08-01", ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, ("doc.pdf", b"%PDF-1.4"))
    assert subj == "[URGENTE][XAXX010101000] requerimiento"
    to, sent_subj, body, att = a.graph.sent[0]
    assert to == "boss@firm.mx"
    assert att and att[0][0] == "doc.pdf"
    assert "ACME" in body
    assert "Cliente" in body and "Tipo de acto" in body

def test_urgent_subject_en_localizes():
    a = _alerter("en")
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, None)
    assert subj == "[URGENT][XAXX010101000] requerimiento"
    body = a.graph.sent[0][2]
    assert "Client" in body and "Act type" in body and "not detected" in body

def test_quarantine_es_and_en():
    es = _alerter("es"); es.send_quarantine("Falso SAT", "e@evil.com", "domain")
    assert "CUARENTENA" in es.graph.sent[0][1]
    assert es.graph.sent[0][3] is None
    en = _alerter("en"); en.send_quarantine("Fake SAT", "e@evil.com", "domain")
    assert "QUARANTINE" in en.graph.sent[0][1]

def test_unknown_client_en():
    a = _alerter("en"); subj = a.send_unknown_client("hola")
    assert "NO CLIENT" in subj
    assert "no identified client" in a.graph.sent[0][2]

def test_fetch_failed_includes_url_both_langs():
    a = _alerter("es"); a.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    assert "https://sat.gob.mx/manual" in a.graph.sent[0][2]
    b = _alerter("en"); b.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    assert "manual review required" in b.graph.sent[0][1]

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
