# Manual validation checklist — live SAT Buzón Tributario portal

## Why this document exists

`julia_tool` is fully built and unit-tested except for two methods:
`BuzonFetcher._fetch_efirma` and `BuzonFetcher._fetch_ciec` in `julia_tool/buzon.py`.
Both are currently fail-safe `NotImplementedError` stubs, on purpose. The SAT Buzón
Tributario portal's real HTML selectors and the exact behavior of the e.firma (FIEL)
client-certificate challenge cannot be discovered or verified without a browser pointed
at the real portal and a real client's credentials — nothing that can be reproduced or
safely faked in an offline development/CI environment. Building "plausible" selectors
and certificate-handling code without ever running it against the real portal would
produce code that *looks* finished but has never actually worked, which is worse than
an honest stub: the stub fails loudly and immediately falls back to a manual-portal-link
alert (see `julia_tool/pipeline.py`), so no notification is ever silently lost while
this step is outstanding.

This document is two things in one:

1. **An interactive checklist** an operator runs once, on-site, against a real client's
   real SAT portal access, to confirm the pipeline behaves correctly end to end.
2. **A complete, copy-pasteable reference implementation** of both live methods, so the
   operator doing the on-site validation only has to *confirm and correct selectors*,
   not write browser-automation code from scratch under time pressure.

Every code block below is marked **UNVERIFIED — confirm selectors on-site before moving
into `buzon.py`**. Nothing in this document has been run against the real SAT portal.
Do not paste it into `julia_tool/buzon.py` and consider the job done — walk through the
checklist next to it first.

### Prerequisites before you start

- [ ] `python -m venv .venv && . .venv/bin/activate && pip install -e .[dev] && playwright install chromium` has been run (see `README.md`).
- [ ] `config.yaml` exists (copied from `config.example.yaml`) with real `tenant_id`,
      `client_id`, `mailbox`, and `responsible_email`.
- [ ] At least one **test client** has been added via `client add` (see `README.md`),
      for whom a signed carta responsiva is on file, and whose real SAT credentials you
      are authorized to use for this validation.
- [ ] Ideally, validate against a client whose Buzón currently has at least one real
      notification, so the download step has something to fetch.
- [ ] A safe `--responsible EMAIL` test address to receive alerts during validation, so
      you don't spam the real responsible person's inbox while testing
      (`python -m julia_tool.main --responsible your-test-address@example.com …`).

---

## Part 1 — Dry-run over a real inbox

Confirms Graph polling, sender verification, RFC extraction, and classification work
against real mail, with zero side effects (no portal login, no mail sent).

```bash
JULIA_MASTER_PW=... python -m julia_tool.main --once --dry-run --responsible you@example.com
```

Checklist:

- [ ] The device-code prompt appears (first run) and sign-in completes; subsequent runs
      are silent (token cache).
- [ ] The final printed `cycle tally: {...}` line accounts for every message in the
      inbox (`--dry-run` still processes and tallies, just without side effects) —
      counts should sum to the number of messages Graph returned.
- [ ] Genuine SAT notification e-mails (real `*.sat.gob.mx` sender, passing
      SPF/DKIM/DMARC) are tallied under `alert_sent` or `fetch_failed` (the live fetch
      is still a stub at this point, so `fetch_failed` is expected — that's fine, see
      "Current status" in `README.md`), **not** `quarantined`.
- [ ] Any spoofed/phishing-style test message (if you seed one — e.g. forward a SAT
      look-alike from a non-SAT domain) is tallied under `quarantined`.
- [ ] Confirm **no e-mail was actually sent** — check the test responsible mailbox's
      inbox/sent items: `--dry-run` must produce zero `sendMail` calls. (If you want to
      see the alert content without sending, temporarily drop `--dry-run` but keep
      `--responsible` pointed at a throwaway test address instead — see Part 4.)
- [ ] Confirm `state.sqlite`'s `processed` table was **not** written to for this run
      (dry-run should not mark messages processed, so a second `--dry-run` reprocesses
      the same messages rather than reporting them as `skipped_duplicate`).

---

## Part 2 — e.firma (FIEL) live validation

Run **non-headless** so you can watch the certificate challenge and confirm selectors
live. `BuzonFetcher.fetch()` already opens e.firma sessions headless by default
(`headless=True` unless overridden), so drive this step directly against a
`BuzonFetcher` instance in a scratch script, or temporarily call `fetcher.fetch(cred,
headless=False)` — do not change the default in `buzon.py`, just override it for this
manual run.

Checklist:

- [ ] The browser opens to `config.yaml`'s `portal.efirma_login_url`
      (`https://cfdiau.sat.gob.mx/nidp/app/login?id=fielHtml5` in
      `config.example.yaml` — confirm this is still current; SAT changes URLs
      occasionally).
- [ ] Identify the real selectors for: the `.cer` file upload input, the `.key` file
      upload input, the key-password field, and the submit control. Use
      `playwright codegen <efirma_login_url>` or the browser devtools inspector — do
      **not** guess from memory, SAT's markup changes across releases.
- [ ] Confirm the FIEL client-certificate challenge is satisfied using the test
      client's real `.cer` + `.key` + key password (from the encrypted store, i.e.
      `cred.cer_path` / `cred.key_path` / `cred.key_password`) and the portal proceeds
      to the notifications list without additional manual steps.
- [ ] Confirm the notifications list loads and record the real
      `notifications_selector` (a CSS selector matching one row per notification).
- [ ] Confirm each row has a download control and record the real
      `download_link_selector` (a CSS selector, evaluated *relative to a row*, i.e.
      passed to `row.query_selector(...)`, matching `julia_tool/buzon.py`'s existing
      `_pick_first_notification_pdf`).
- [ ] Trigger the download of the first notification and confirm a PDF lands in
      `downloads/<rfc>_*.pdf` (see the "known related fix" note at the end of this
      document — as written today, `_pick_first_notification_pdf` names the file
      `download_*.pdf`, not `<rfc>_*.pdf`; fix that one line at the same time you wire
      in this reference code).
- [ ] Update `config.yaml`'s `portal.notifications_selector` and
      `portal.download_link_selector` with the confirmed values.

### Reference implementation — `_fetch_efirma`

**UNVERIFIED — confirm selectors on-site before moving into `buzon.py`.** Placeholder
selectors below (`#fileCert`, `#fileKey`, …) are illustrative only.

```python
def _fetch_efirma(self, cred: ClientCred, browser) -> FetchResult:
    """Live e.firma (FIEL) flow — UNVERIFIED, confirm on-site (see
    docs/manual-validation.md Part 2) before this replaces the
    NotImplementedError stub in julia_tool/buzon.py."""
    page = browser.new_page()
    try:
        page.goto(self.portal["efirma_login_url"], wait_until="networkidle")

        # --- FIEL certificate challenge ---------------------------------
        # UNVERIFIED selectors — replace with the real ones from
        # `playwright codegen` against the live login page.
        page.set_input_files('input[type="file"]#fileCert', cred.cer_path)
        page.set_input_files('input[type="file"]#fileKey', cred.key_path)
        page.fill('input[type="password"]#password', cred.key_password)
        page.click('#submit, button[type="submit"]')

        # Wait for the notifications list to appear (post-login landing
        # page). Long timeout: SAT's portal can be slow to validate the
        # certificate chain.
        page.wait_for_selector(self.portal["notifications_selector"],
                                timeout=60_000)

        pdf_path = self._pick_first_notification_pdf(page)
        if pdf_path is None:
            return FetchResult(False, None,
                                "efirma login ok but no notifications listed",
                                None)
        return FetchResult(True, pdf_path, None, None)

    except Exception as exc:  # noqa: BLE001 — capture real diagnostics here,
        # not the fabricated path in fetch()'s outer handler (see the "known
        # related fix" note at the end of this document).
        shot = os.path.join(self.download_dir, f"{cred.rfc}_efirma_fail.png")
        html_dump = os.path.join(self.download_dir, f"{cred.rfc}_efirma_fail.html")
        try:
            page.screenshot(path=shot, full_page=True)
            with open(html_dump, "w", encoding="utf-8") as f:
                f.write(page.content())
        except Exception:  # noqa: BLE001 — best-effort diagnostics only
            shot = None
        return FetchResult(False, None, str(exc), shot)
    finally:
        page.close()
```

Note this reference implementation deliberately calls `self._pick_first_notification_pdf(page)`
(the existing helper in `julia_tool/buzon.py`, already unit-testable via its selector
lookups) rather than reimplementing the download logic — see the "known related fix"
note below about the one line inside that helper worth fixing at the same time.

---

## Part 3 — CIEC live validation

CIEC (Contraseña) always runs in a **headed** window — `BuzonFetcher.fetch()` already
forces `headless=False` for `auth_type == "ciec"` regardless of the `headless=` argument
passed in, so the operator can see the browser and solve the captcha by hand. No code
change is needed to make this headed; just run `fetcher.fetch(cred)` for a `ciec` client
and the window will appear.

Checklist:

- [ ] The browser opens to `config.yaml`'s `portal.ciec_login_url`
      (`https://cfdiau.sat.gob.mx/nidp/app/login?id=SATUPCB` in
      `config.example.yaml` — confirm current).
- [ ] Identify and record the real selectors for the RFC field, the password
      (Contraseña) field, and the captcha challenge element (image/reCAPTCHA/etc — this
      one is **not** automated, just note what it looks like so the operator recognizes
      it).
- [ ] Confirm the app fills RFC (`cred.rfc`) and password (`cred.ciec_password`)
      automatically and then **stops and waits** — it must not attempt to solve or
      bypass the captcha itself (out of scope per the design spec, §9).
- [ ] The operator manually solves the captcha and submits the form in the visible
      browser window.
- [ ] Confirm automation resumes automatically once the post-login page appears (the
      reference implementation below polls for the notifications selector with a
      multi-minute timeout — tune the timeout to how long solving the captcha actually
      takes in practice).
- [ ] Confirm the notification downloads to `downloads/<rfc>_*.pdf`, same as Part 2.
- [ ] Update `config.yaml` selectors if they differ from the e.firma ones (SAT may use
      the same notifications table markup for both flows — check).

### Reference implementation — `_fetch_ciec`

**UNVERIFIED — confirm selectors on-site before moving into `buzon.py`.** Placeholder
selectors below (`#rfc`, `#password`, …) are illustrative only.

```python
def _fetch_ciec(self, cred: ClientCred, browser) -> FetchResult:
    """Live CIEC flow — UNVERIFIED, confirm on-site (see
    docs/manual-validation.md Part 3) before this replaces the
    NotImplementedError stub in julia_tool/buzon.py.

    `browser` here is already headed (fetch() forces headless=False for
    auth_type == "ciec") so the operator can solve the captcha by hand."""
    page = browser.new_page()
    try:
        page.goto(self.portal["ciec_login_url"], wait_until="networkidle")

        # --- fill what we can; leave the captcha to the operator --------
        # UNVERIFIED selectors — replace with the real ones from
        # `playwright codegen` against the live login page.
        page.fill('input#rfc', cred.rfc)
        page.fill('input[type="password"]#password', cred.ciec_password)

        # Do NOT click submit here if the captcha must be solved first —
        # confirm on-site whether SAT's form requires the captcha to be
        # solved before submit is even clickable, or whether the operator
        # must click submit themselves after solving it. Either way, the
        # automation's job past this point is to wait, not to act.
        print(f"[{cred.rfc}] CIEC form filled — solve the captcha and "
              f"submit in the browser window now.", flush=True)

        # Long timeout: this is a human-paced step. 3 minutes is a
        # starting point — tune after watching a few real attempts.
        page.wait_for_selector(self.portal["notifications_selector"],
                                timeout=180_000)

        pdf_path = self._pick_first_notification_pdf(page)
        if pdf_path is None:
            return FetchResult(False, None,
                                "ciec login ok but no notifications listed",
                                None)
        return FetchResult(True, pdf_path, None, None)

    except Exception as exc:  # noqa: BLE001 — capture real diagnostics here,
        # not the fabricated path in fetch()'s outer handler (see the "known
        # related fix" note at the end of this document).
        shot = os.path.join(self.download_dir, f"{cred.rfc}_ciec_fail.png")
        html_dump = os.path.join(self.download_dir, f"{cred.rfc}_ciec_fail.html")
        try:
            page.screenshot(path=shot, full_page=True)
            with open(html_dump, "w", encoding="utf-8") as f:
                f.write(page.content())
        except Exception:  # noqa: BLE001 — best-effort diagnostics only
            shot = None
        return FetchResult(False, None, str(exc), shot)
    finally:
        page.close()
```

---

## Part 4 — Moving the confirmed code into `buzon.py`

Once both parts above are confirmed against the real portal:

1. Replace the two `NotImplementedError` bodies of `_fetch_efirma` and `_fetch_ciec` in
   `julia_tool/buzon.py` with the confirmed versions of the reference code above (real
   selectors substituted in).
2. Apply the "known related fix" below to `_pick_first_notification_pdf` at the same
   time (one-line change) so downloaded files are actually named `<rfc>_*.pdf`.
3. Update `config.yaml`'s `portal.notifications_selector` and
   `portal.download_link_selector` (and URLs, if they'd drifted from
   `config.example.yaml`'s placeholders) with the confirmed values.
4. Re-run the unit test suite — it must still be green; the existing tests in
   `tests/test_buzon.py` cover dispatch and helpers with fake browser factories, so they
   don't touch the network and should be unaffected by filling in the two method
   bodies:
   ```bash
   .venv/bin/python -m pytest -q
   ```
5. Run one real end-to-end message through the live pipeline to a **test** responsible
   address, confirming the full chain (Graph poll → verify → RFC → live portal fetch →
   classify → alert with PDF attached) works without `--dry-run`:
   ```bash
   JULIA_MASTER_PW=... python -m julia_tool.main --once --responsible your-test-address@example.com
   ```
   Confirm the test address receives an alert e-mail with the real PDF attached, and
   that `state.sqlite`'s `audit` table recorded the credential use
   (`state.audit_count()` increments, or `SELECT * FROM audit ORDER BY id DESC LIMIT 1`).
6. Commit the completed `buzon.py` and updated `config.yaml`/`config.example.yaml`
   selectors as their own change, separate from this documentation commit.

### Known related fix worth bundling in at the same time

`_pick_first_notification_pdf` (already in `julia_tool/buzon.py`, unmodified by this
documentation task) currently does this:

```python
def _pick_first_notification_pdf(self, page) -> str | None:
    rows = page.query_selector_all(self.portal["notifications_selector"])
    if not rows:
        return None
    link = rows[0].query_selector(self.portal["download_link_selector"])
    if not link:
        return None
    with page.expect_download() as dl:
        link.click()
    path = self._download_path("download")   # <-- hardcoded, not cred.rfc
    dl.value.save_as(path)
    return path
```

It names every downloaded file `download_<N>.pdf` because it calls
`self._download_path("download")` with a literal string, not the client's RFC. Both this
checklist and `README.md` describe the expected filename pattern as
`downloads/<rfc>_*.pdf` (matching `_download_path`'s actual `{prefix}_{counter}.pdf`
format, confirmed by `tests/test_buzon.py::test_download_path_format`). When you wire in
the confirmed live code, also change this method's signature to accept the RFC and call
`self._download_path(cred.rfc)` instead — e.g.:

```python
def _pick_first_notification_pdf(self, page, rfc: str) -> str | None:
    ...
    path = self._download_path(rfc)
    ...
```

and update the two call sites in your confirmed `_fetch_efirma`/`_fetch_ciec` to
`self._pick_first_notification_pdf(page, cred.rfc)`. This is a pre-existing placeholder
in already-reviewed code (Task 12), not something introduced here — flagging it now so
it isn't missed when the live selectors are wired in, since it's a one-line change in
the same method you're already touching.

This documentation task intentionally does not modify `julia_tool/buzon.py` — see the
top of this document for why.
