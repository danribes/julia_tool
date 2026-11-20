import pytest

from julia_tool.whatsapp import (
    WhatsAppCloudClient, WhatsAppError, WhatsAppNotifier, normalize_number, clean_param,
)


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return self.responses.pop(0)


_OK = _Resp(200, {"messages": [{"id": "wamid.ABC"}]})


def test_send_template_posts_cloud_api_payload_with_bearer_token():
    http = _FakeHttp([_OK])
    client = WhatsAppCloudClient("1234567890", "SECRET-TOKEN", api_version="v21.0", http=http)
    mid = client.send_template("528112345678", "julia_aviso_sat", "es_MX", ["URGENTE", "ACME (XAXX010101000)"])
    assert mid == "wamid.ABC"
    call = http.calls[0]
    assert call["url"] == "https://graph.facebook.com/v21.0/1234567890/messages"
    assert call["headers"]["Authorization"] == "Bearer SECRET-TOKEN"
    body = call["json"]
    assert body["messaging_product"] == "whatsapp"
    assert body["to"] == "528112345678"
    assert body["type"] == "template"
    assert body["template"]["name"] == "julia_aviso_sat"
    assert body["template"]["language"] == {"code": "es_MX"}
    params = body["template"]["components"][0]["parameters"]
    assert body["template"]["components"][0]["type"] == "body"
    assert [p["text"] for p in params] == ["URGENTE", "ACME (XAXX010101000)"]
    assert all(p["type"] == "text" for p in params)
    assert call["timeout"]


def test_http_error_raises_without_leaking_token():
    err = _Resp(401, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
    client = WhatsAppCloudClient("1234567890", "SECRET-TOKEN", http=_FakeHttp([err]))
    with pytest.raises(WhatsAppError) as exc:
        client.send_template("528112345678", "t", "es_MX", ["a"])
    assert "401" in str(exc.value)
    assert "190" in str(exc.value)
    assert "SECRET-TOKEN" not in str(exc.value)


def test_clean_param_collapses_whitespace_and_never_empty():
    assert clean_param("a\n\tb    c") == "a b c"
    assert clean_param("") == "—"
    assert clean_param(None) == "—"
    assert len(clean_param("x" * 2000)) <= 300


def test_normalize_number_keeps_digits_only():
    assert normalize_number("+52 81 8280 1418") == "528182801418"
    assert normalize_number("0052-81-1234-5678") == "528112345678"
    with pytest.raises(ValueError):
        normalize_number("12345")
    with pytest.raises(ValueError):
        normalize_number("")


class _FakeClient:
    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def send_template(self, to, template, lang_code, params):
        if to in self.fail_for:
            raise WhatsAppError("boom")
        self.sent.append((to, template, lang_code, list(params)))
        return f"wamid.{to}"


def test_notifier_sends_to_every_recipient_and_never_raises():
    client = _FakeClient(fail_for={"528100000001"})
    logs = []
    n = WhatsAppNotifier(client, ["+52 81 0000 0001", "528100000002"], "julia_aviso_sat", "es_MX",
                         log=logs.append)
    out = n.notify("URGENTE — requerimiento", "ACME (XAXX010101000)")
    assert out == {"528100000001": "failed", "528100000002": "sent"}
    assert client.sent == [("528100000002", "julia_aviso_sat", "es_MX",
                            ["URGENTE — requerimiento", "ACME (XAXX010101000)"])]
    assert any("528100000001" in line for line in logs)


def test_notifier_can_hide_client_details():
    client = _FakeClient()
    n = WhatsAppNotifier(client, ["528100000002"], "t", "es_MX", include_client_details=False,
                         log=lambda *_: None)
    n.notify("URGENTE", "ACME (XAXX010101000)")
    assert client.sent[0][3] == ["URGENTE", "—"]


def test_notifier_requires_a_recipient():
    with pytest.raises(ValueError):
        WhatsAppNotifier(_FakeClient(), [], "t", "es_MX")
