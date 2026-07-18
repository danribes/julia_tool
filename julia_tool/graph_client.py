import base64
import os
import msal
import requests
from julia_tool.models import EmailMessage

_GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPES = ["Mail.Read.Shared", "Mail.Send.Shared"]

class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, mailbox: str,
                 token_cache_path: str = ".token_cache.bin"):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.mailbox = mailbox
        self.token_cache_path = token_cache_path

    # ---- auth ----
    def _cache(self) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache_path):
            with open(self.token_cache_path) as f:
                cache.deserialize(f.read())
        return cache

    def _save_cache(self, cache: msal.SerializableTokenCache) -> None:
        if cache.has_state_changed:
            fd = os.open(self.token_cache_path,
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(cache.serialize())
            os.chmod(self.token_cache_path, 0o600)

    def acquire_token(self, prompt: bool = True) -> str:
        cache = self._cache()
        app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            token_cache=cache)
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(_SCOPES, account=accounts[0])
        if not result and prompt:
            flow = app.initiate_device_flow(scopes=_SCOPES)
            print(flow["message"], flush=True)
            result = app.acquire_token_by_device_flow(flow)
        self._save_cache(cache)
        if not result or "access_token" not in result:
            raise RuntimeError(f"token acquisition failed: {result}")
        return result["access_token"]

    def session(self, token: str) -> requests.Session:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s

    # ---- pure mappers (unit-tested) ----
    @staticmethod
    def _extract_auth_results(headers: list[dict]) -> str:
        for h in headers or []:
            if h.get("name", "").lower() == "authentication-results":
                return h.get("value", "")
        return ""

    def _parse_message(self, raw: dict) -> EmailMessage:
        return EmailMessage(
            id=raw.get("id", ""),
            subject=raw.get("subject", "") or "",
            from_address=(((raw.get("from") or {}).get("emailAddress") or {})
                          .get("address") or ""),
            auth_results=self._extract_auth_results(
                raw.get("internetMessageHeaders", [])),
            body=(raw.get("body", {}) or {}).get("content", "") or "",
            received=raw.get("receivedDateTime", ""),
        )

    # ---- REST ----
    def list_messages(self, session, top: int = 25) -> list[EmailMessage]:
        url = f"{_GRAPH}/users/{self.mailbox}/mailFolders/inbox/messages"
        params = {
            "$top": str(top),
            "$select": "id,subject,from,body,receivedDateTime,internetMessageHeaders",
            "$orderby": "receivedDateTime desc",
        }
        resp = session.get(url, headers={
            "Prefer": 'outlook.body-content-type="text"'}, params=params)
        resp.raise_for_status()
        return [self._parse_message(r) for r in resp.json().get("value", [])]

    def send_mail(self, session, to: str, subject: str, html_body: str,
                  attachments: list[tuple[str, bytes]] | None) -> None:
        message: dict = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
        if attachments:
            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": name,
                    "contentBytes": base64.b64encode(data).decode("ascii"),
                }
                for name, data in attachments
            ]
        url = f"{_GRAPH}/users/{self.mailbox}/sendMail"
        resp = session.post(url, headers={"Content-Type": "application/json"},
                            json={"message": message, "saveToSentItems": True})
        resp.raise_for_status()
