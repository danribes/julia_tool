"""WhatsApp alerts through Meta's WhatsApp Cloud API.

Each alert is sent as a pre-approved *template* message (business-initiated
messages outside a 24-hour customer window must use a template). The template
body has two variables:

    {{1}} = what happened  (e.g. "URGENTE — requerimiento")
    {{2}} = which client   (e.g. "ACME (XAXX010101000)")

The access token is never read from config.yaml; main.py takes it from the
JULIA_WA_TOKEN environment variable.
"""
import re

import requests

_GRAPH_FB = "https://graph.facebook.com"
_MAX_PARAM = 300  # keep template parameters short; WhatsApp rejects very long ones
_PLACEHOLDER = "—"


class WhatsAppError(RuntimeError):
    """The Cloud API refused or failed to accept a message."""


def clean_param(value) -> str:
    """WhatsApp template parameters may not contain newlines, tabs or long runs of
    spaces, and may not be empty."""
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    return text[:_MAX_PARAM] if text else _PLACEHOLDER


def normalize_number(raw: str) -> str:
    """International number as digits only, e.g. '+52 81 1234 5678' -> '528112345678'."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if not 10 <= len(digits) <= 15:
        raise ValueError(f"not an international phone number: {raw!r}")
    return digits


class WhatsAppCloudClient:
    def __init__(self, phone_number_id: str, access_token: str, api_version: str = "v21.0",
                 http=None, timeout: float = 15):
        self.phone_number_id = str(phone_number_id)
        self._token = access_token
        self.api_version = api_version
        self.http = http or requests.Session()
        self.timeout = timeout

    def send_template(self, to: str, template: str, lang_code: str, params) -> str:
        url = f"{_GRAPH_FB}/{self.api_version}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": lang_code},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": clean_param(p)} for p in params],
                }],
            },
        }
        resp = self.http.post(url, json=payload,
                              headers={"Authorization": f"Bearer {self._token}"},
                              timeout=self.timeout)
        if resp.status_code >= 300:
            try:
                err = resp.json().get("error", {})
                detail = f"{err.get('code')} {err.get('message')}"
            except Exception:
                detail = (resp.text or "")[:200]
            raise WhatsAppError(f"WhatsApp API HTTP {resp.status_code}: {detail}")
        try:
            return resp.json()["messages"][0]["id"]
        except Exception as exc:
            raise WhatsAppError(f"unexpected WhatsApp API response: {exc}") from exc


class WhatsAppNotifier:
    """Sends one template message per recipient. Never raises: a WhatsApp problem
    must not stop the e-mail alert or the processing of the SAT notice."""

    def __init__(self, client, recipients, template: str = "julia_aviso_sat",
                 lang_code: str = "es_MX", include_client_details: bool = True, log=print):
        self.recipients = [normalize_number(r) for r in (recipients or [])]
        if not self.recipients:
            raise ValueError("WhatsApp alerts need at least one recipient number")
        self.client = client
        self.template = template
        self.lang_code = lang_code
        self.include_client_details = include_client_details
        self.log = log

    def notify(self, event: str, client_text: str) -> dict:
        params = [clean_param(event),
                  clean_param(client_text) if self.include_client_details else _PLACEHOLDER]
        outcomes = {}
        for to in self.recipients:
            try:
                self.client.send_template(to, self.template, self.lang_code, params)
                outcomes[to] = "sent"
            except Exception as exc:  # report and carry on with the next recipient
                outcomes[to] = "failed"
                self.log(f"WhatsApp alert to {to} failed: {exc}")
        return outcomes
