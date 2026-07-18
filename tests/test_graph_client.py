import base64

from julia_tool.graph_client import GraphClient

RAW = {
    "id": "AAA",
    "subject": "Tiene una notificacion",
    "from": {"emailAddress": {"address": "no-reply@sat.gob.mx"}},
    "body": {"content": "Contribuyente XAXX010101000"},
    "receivedDateTime": "2026-07-18T10:00:00Z",
    "internetMessageHeaders": [
        {"name": "Authentication-Results", "value": "spf=pass; dkim=pass"},
        {"name": "X-Other", "value": "z"},
    ],
}

def _client():
    return GraphClient("t", "c", "office@firm.mx")

def test_parse_message_maps_fields():
    m = _client()._parse_message(RAW)
    assert m.id == "AAA"
    assert m.from_address == "no-reply@sat.gob.mx"
    assert "spf=pass" in m.auth_results
    assert "XAXX010101000" in m.body

def test_extract_auth_results_missing_is_empty():
    assert _client()._extract_auth_results([]) == ""

class _FakeResp:
    def __init__(self, payload): self._p = payload; self.status_code = 200
    def raise_for_status(self): pass
    def json(self): return self._p

class _FakeSession:
    def __init__(self, payload): self._p = payload; self.posted = []
    def get(self, url, headers=None, params=None): return _FakeResp(self._p)
    def post(self, url, headers=None, json=None):
        self.posted.append(json); return _FakeResp({})

def test_list_messages_uses_session():
    sess = _FakeSession({"value": [RAW]})
    msgs = _client().list_messages(sess)
    assert len(msgs) == 1 and msgs[0].id == "AAA"

def test_send_mail_posts_payload():
    sess = _FakeSession({})
    _client().send_mail(sess, "boss@firm.mx", "S", "<p>hi</p>", None)
    assert sess.posted and sess.posted[0]["message"]["subject"] == "S"

def test_parse_message_null_email_address_safe():
    raw = {"id": "B", "from": {"emailAddress": None},
           "body": {"content": "x"}, "receivedDateTime": "t"}
    m = _client()._parse_message(raw)
    assert m.from_address == ""

def test_send_mail_encodes_attachment():
    sess = _FakeSession({})
    _client().send_mail(sess, "boss@firm.mx", "S", "<p>hi</p>",
                        [("doc.pdf", b"%PDF-1.4 data")])
    att = sess.posted[0]["message"]["attachments"][0]
    assert att["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert att["name"] == "doc.pdf"
    assert base64.b64decode(att["contentBytes"]) == b"%PDF-1.4 data"
