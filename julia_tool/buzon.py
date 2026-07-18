import os
from julia_tool.models import ClientCred, FetchResult

class BuzonFetcher:
    def __init__(self, portal: dict, download_dir: str):
        self.portal = portal
        self.download_dir = download_dir
        self._counter = 0
        os.makedirs(download_dir, exist_ok=True)

    def _download_path(self, rfc: str) -> str:
        self._counter += 1
        return os.path.join(self.download_dir, f"{rfc}_{self._counter}.pdf")

    def _default_browser_factory(self, headless: bool):
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=headless)
        return (pw, browser)

    def fetch(self, cred: ClientCred, headless: bool = True,
              _browser_factory=None) -> FetchResult:
        if cred.auth_type not in ("efirma", "ciec"):
            return FetchResult(False, None,
                               f"unsupported auth_type: {cred.auth_type}", None)
        factory = _browser_factory or self._default_browser_factory
        pw = None
        try:
            pw, browser = factory(headless if cred.auth_type == "efirma" else False)
            if cred.auth_type == "efirma":
                return self._fetch_efirma(cred, browser)
            return self._fetch_ciec(cred, browser)
        except Exception as exc:  # noqa: BLE001 — any failure → fallback alert
            shot = os.path.join(self.download_dir, f"{cred.rfc}_fail.png")
            return FetchResult(False, None, str(exc), shot)
        finally:
            if pw is not None:
                try:
                    pw.stop()
                except Exception:  # noqa: BLE001 — best-effort cleanup
                    pass

    def _fetch_efirma(self, cred: ClientCred, browser) -> FetchResult:
        # Live implementation validated manually (Task 15).
        # Uses cred.cer_path/key_path/key_password to satisfy the FIEL client
        # certificate challenge, then _pick_first_notification_pdf(page).
        raise NotImplementedError("e.firma live flow — see Task 15 checklist")

    def _fetch_ciec(self, cred: ClientCred, browser) -> FetchResult:
        # Live implementation validated manually (Task 15).
        # Fills RFC + cred.ciec_password, pauses for operator captcha, then
        # _pick_first_notification_pdf(page).
        raise NotImplementedError("CIEC live flow — see Task 15 checklist")

    def _pick_first_notification_pdf(self, page) -> str | None:
        rows = page.query_selector_all(self.portal["notifications_selector"])
        if not rows:
            return None
        link = rows[0].query_selector(self.portal["download_link_selector"])
        if not link:
            return None
        with page.expect_download() as dl:
            link.click()
        path = self._download_path("download")
        dl.value.save_as(path)
        return path
