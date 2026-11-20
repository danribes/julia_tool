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


# ---- WhatsApp channel (in addition to e-mail) ----

class _FakeWA:
    def __init__(self, raise_exc=False):
        self.calls = []
        self.raise_exc = raise_exc

    def notify(self, event, client):
        self.calls.append((event, client))
        if self.raise_exc:
            raise RuntimeError("whatsapp down")
        return {"528100000002": "sent"}


def _alerter_wa(lang="es", wa=None):
    return Alerter(_FakeGraph(), session=None, responsible_email="boss@firm.mx", lang=lang,
                   whatsapp=wa)


def test_urgent_also_sends_whatsapp_after_email():
    wa = _FakeWA()
    a = _alerter_wa("es", wa)
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    a.send_urgent("XAXX010101000", "ACME", cls, None)
    assert len(a.graph.sent) == 1                       # e-mail still sent
    event, client = wa.calls[0]
    assert "URGENTE" in event and "requerimiento" in event
    assert client == "ACME (XAXX010101000)"


def test_whatsapp_failure_never_breaks_email_alert():
    a = _alerter_wa("es", _FakeWA(raise_exc=True))
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, None)
    assert subj.startswith("[URGENTE]")
    assert len(a.graph.sent) == 1


def test_other_alerts_also_reach_whatsapp_in_both_languages():
    wa = _FakeWA()
    es = _alerter_wa("es", wa)
    es.send_quarantine("Falso SAT", "e@evil.com", "domain")
    es.send_unknown_client("hola")
    es.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    events = [c[0] for c in wa.calls]
    assert "cuarentena" in events[0].lower()
    assert "sin cliente" in events[1].lower()
    assert "revisión manual" in events[2].lower()
    assert wa.calls[2][1] == "ACME (XAXX010101000)"
    wa_en = _FakeWA()
    en = _alerter_wa("en", wa_en)
    en.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    assert "manual review" in wa_en.calls[0][0].lower()


def test_no_whatsapp_configured_is_email_only():
    a = _alerter("es")
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    a.send_urgent("XAXX010101000", "ACME", cls, None)
    assert len(a.graph.sent) == 1
