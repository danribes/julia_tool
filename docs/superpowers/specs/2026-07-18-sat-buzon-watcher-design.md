# SAT Buzón Watcher — Design Spec

**Date:** 2026-07-18
**Project:** `julia_tool` (project name only; implementation language is Python)
**Status:** Approved by user (approach: full automation day one)

## 1. Purpose

A Mexican accountancy office supervises many clients. SAT (Servicio de Administración
Tributaria) sends Buzón Tributario notification emails to one shared office mailbox.
The app must, unattended:

1. Detect genuine SAT notification emails in the Outlook (Microsoft 365) mailbox.
2. Identify which client the notice belongs to (by RFC — the fiscal ID).
3. Log into the SAT Buzón Tributario portal with that client's stored credentials and
   download the actual notification document (the email is only a notice).
4. Classify the document's urgency (requerimiento, multa, sanción, embargo, …).
5. Email an alert, with the document attached, to the office's fixed responsible person.

## 2. Decisions taken (user-confirmed)

| Question | Decision |
|---|---|
| Meaning of "secret key opens the email" | SAT portal login — email is notification only; real document fetched from Buzón Tributario |
| Outlook access | Microsoft Graph API (delegated auth, device-code flow, MSAL token cache) |
| Mailbox topology | One shared office mailbox receives all clients' SAT notices |
| Alert routing | One fixed responsible person receives every alert |
| SAT credentials held | Mixed: e.firma (.cer/.key + password) for some clients, Contraseña (CIEC) for others |
| Credential storage | Single encrypted file (`clients.secret`, Fernet, scrypt-derived key from master password) — **not** plaintext |
| Build approach | Full automation from day one (portal fetch included) |
| Language | Python 3.12 |

## 3. Architecture

Console service (long-running loop) with a `--once` mode for Windows Task Scheduler /
cron. Master password prompted at startup; everything else unattended.

```
Graph poll ──> sender verify ──> RFC extract ──> credential lookup
                   │ fail              │ no match         │
                   ▼                   ▼                  ▼
             quarantine alert    unknown-client      e.firma → headless Playwright fetch
                                     alert           CIEC    → operator-assisted window
                                                          │
                                                          ▼
                                             PDF download ──> classify ──> alert responsible
                                                          │ any failure
                                                          ▼
                                              fallback alert + manual portal link
```

## 4. Components

| Module | Responsibility |
|---|---|
| `julia_tool/poller.py` | Graph API delta query on the shared mailbox inbox, every N minutes (default 5). Marks nothing read; state lives in SQLite. |
| `julia_tool/verify.py` | Anti-phishing gate. From-domain must match allowlist (`*.sat.gob.mx`); `Authentication-Results` header must contain `spf=pass` and `dkim=pass` aligned to sat.gob.mx. Fail → quarantine alert; credentials are never used for a failed message. |
| `julia_tool/rfc.py` | Extract RFC via regex `[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}` from subject + body. No match → unknown-client alert. |
| `julia_tool/secrets_store.py` | Encrypted client index (`clients.secret`): Fernet, key derived from master password with scrypt. Per RFC: client name, auth type, e.firma cert/key paths + key password, or CIEC password. CLI subcommands: `client add / list / remove`. |
| `julia_tool/buzon.py` | Playwright Chromium against known SAT URLs only (never links from the email). e.firma: headless certificate login → notifications list → download PDF. CIEC: headed browser window, app fills RFC + password, operator solves the captcha, automation resumes. Selectors in `config.yaml`; screenshot + HTML dump on failure. |
| `julia_tool/classify.py` | PyMuPDF text extraction → Spanish keyword rules → urgency `URGENT / ATTENTION / INFO` + act type. Optional Claude API pass (config flag, default off) for act-type refinement and deadline (plazo) extraction. |
| `julia_tool/alert.py` | Graph `sendMail` from the office mailbox to the fixed responsible. Subject `[URGENTE][<RFC>] <act type>`. Body: client, RFC, act, deadline, audit ref. PDF attached. Also sends quarantine, unknown-client, and fetch-failure alerts. |
| `julia_tool/state.py` | SQLite (`state.sqlite`): processed Graph message IDs (idempotency), audit log of every credential use (RFC, timestamp, purpose, outcome), alert history. |
| `julia_tool/main.py` | Config load, master-password prompt, scheduler loop / `--once` / `--dry-run`. |
| `config.yaml` | Mailbox address, poll interval, responsible email, sender allowlist, portal URLs + selectors, keyword→urgency map, Claude flag. |

## 5. Data

- **`clients.secret`** — Fernet-encrypted JSON, indexed by RFC. Never committed; `.gitignore`d along with `*.cer`, `*.key`, `state.sqlite`, token cache.
- **e.firma files** — stored outside the repo in an ACL-restricted directory; the store holds only their paths and passwords.
- **`state.sqlite`** — idempotency + audit; no secrets inside.
- **Downloads** — `downloads/<RFC>/<date>_<messageid>.pdf`.

## 6. Security requirements

- Credentials exist in memory only after master-password entry; on disk only encrypted.
- Sender verification precedes any credential access — a message that fails SPF/DKIM/domain checks can never trigger a portal login.
- Portal navigation only to configured SAT URLs; links inside emails are never followed.
- Every credential use is written to the audit log before the login attempt.
- The firm must hold signed client authorization (carta responsiva) for credential custody — operational prerequisite, noted in README.

## 7. Error handling

No silent drops. Every message ends in exactly one of: alert-sent, quarantined,
unknown-client, fetch-failed (fallback alert with manual link), or skipped-duplicate.
Transient Graph errors retry with backoff; Playwright failures capture screenshot +
HTML before falling back.

## 8. Testing

- Unit tests: sender verify (genuine SAT headers vs phishing fixtures), RFC extraction,
  classifier golden tests, secrets store round-trip.
- `--dry-run`: full pipeline, no portal login, no mail sent, prints decisions.
- Playwright logic tested against saved HTML fixtures of the SAT login/notification pages.

## 9. Out of scope (v1)

- Per-client alert routing (single responsible only).
- CFDI download / Descarga Masiva web services.
- Any captcha-solving service for CIEC (operator solves it in the headed window).
- Web dashboard; alerts are email-only.
