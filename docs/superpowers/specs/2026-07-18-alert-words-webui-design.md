# Alert-words gate + local web UI — Design Spec

**Date:** 2026-07-18
**Project:** `julia_tool` (SAT Buzón Tributario watcher)
**Status:** Approved by user

## 1. Purpose

Give the operator a small local web page with two inputs:
1. **Alert words** (comma-separated) — a genuine SAT notification is forwarded to the
   person in charge **only if** one of these words appears in the email or the fetched SAT
   document. Empty list → forward everything (the gate is opt-in; today's behavior).
2. **Recipient email** — the address that receives the alert emails, editable from the UI.

Both settings persist to one JSON file the watcher reads each poll cycle (edits take
effect without a restart).

## 2. Decisions taken (user-confirmed)

| Question | Decision |
|---|---|
| UI delivery | Small local **Flask** web UI bound to `127.0.0.1` |
| What alert words do | **Gate the forward/resend** (not classification) |
| Match target | **Both** the notification email (subject+body) AND the fetched document text |
| Empty alert-words list | **Forward all** — gate is opt-in, backward compatible |
| UI language | **Bilingual** es/en (reuse i18n catalog + toggle) |
| Web framework | **Flask** (new dependency) |
| Recipient email in UI | **Yes** — editable field, validated, persisted (added mid-design) |
| Matching | Case- AND accent-insensitive substring |

## 3. Architecture

```
                         ui_settings.json  {alert_words:[...], responsible_email:"..."}
                            ▲ write (POST)            │ read each cycle
   Operator ── browser ──► Flask webui (127.0.0.1)   ▼
                                              run_once ─► process_message(alert_words, read_pdf_text)
                                                             │ build searchable = email + doc text
                                                             ├─ should_forward? ── yes ─► send alert  (alert_sent)
                                                             └───────────────────── no  ─► NOT sent    (not_forwarded)
```

## 4. Components

| File | Responsibility |
|---|---|
| `julia_tool/alert_words.py` (new) | Pure matching: `parse_words(raw:str) -> list[str]` (split on commas, strip, drop empties, dedupe preserving order); `normalize(s:str) -> str` (NFKD, strip diacritics, casefold); `should_forward(text:str, words:list[str]) -> bool` (empty words → True; else any normalized word is a substring of normalized text). No I/O. |
| `julia_tool/settings.py` (new) | UI settings persistence: `DEFAULTS = {"alert_words": [], "responsible_email": ""}`; `load_settings(path) -> dict` (missing file → copy of DEFAULTS; tolerates partial/corrupt → falls back to defaults per key); `save_settings(path, data) -> None` (atomic write, 0600); `valid_email(s) -> bool` (basic `x@y.z` check). `save_settings` stores only known keys; `responsible_email` "" means "unset". |
| `julia_tool/webui.py` (new) | Flask app factory `create_app(settings_path, lang="es")`. `GET /` renders the page (alert-words input prefilled comma-joined, recipient-email input prefilled, current values, es/en toggle via `?lang=`). `POST /` reads form, `parse_words`, validates recipient with `valid_email` (empty allowed = unset), saves via `save_settings`, re-renders with a saved/invalid message. Per-process CSRF token in a hidden field, checked on POST (reject → 400). Bind host fixed to `127.0.0.1`. `run_ui(settings_path, port, lang)` launches it. |
| `julia_tool/pipeline.py` (modify) | `process_message(..., alert_words=None, read_pdf_text=None)`. The gate applies ONLY to the successful notification-forward path (the `send_urgent` case). On the fetched-doc path: `doc_text = read_pdf_text(pdf) if read_pdf_text else ""` (guarded, OSError/Exception → ""); `searchable = subject + "\n" + body + "\n" + doc_text`; if `should_forward(searchable, alert_words or [])` → send alert + `record_alert` → `"alert_sent"`; else skip the send → new outcome `"not_forwarded"` (still `mark_processed`; credential-use already logged). The quarantine, unknown-client, and fetch-failed alerts are security/operational notices and are NEVER gated (always sent). Dry-run and all earlier branches unchanged. |
| `julia_tool/main.py` (modify) | `run_once` gains `alert_words=None`, `read_pdf_text=None`, resolves recipient precedence; loads settings once per cycle. New `ui` subcommand: `python -m julia_tool.main ui [--port 8770] [--lang es|en]` → `run_ui`. Recipient precedence: `--responsible` flag > settings `responsible_email` (if non-empty) > `cfg.responsible_email`. Alert words come from settings each cycle. |
| `julia_tool/config.py` (modify) | Add `settings_path: str = "ui_settings.json"`. |
| `julia_tool/i18n.py` (modify) | Add UI keys (es/en): `ui.title`, `ui.alert_words.label`, `ui.alert_words.help`, `ui.recipient.label`, `ui.recipient.help`, `ui.save`, `ui.saved`, `ui.invalid_email`, `ui.current`, `ui.empty_note`, `ui.lang_toggle`. Key parity enforced by existing test. |
| `config.example.yaml` | Document `settings_path: ui_settings.json`. |
| `.gitignore` | Add `ui_settings.json` (operator data). |
| `Dockerfile` | `EXPOSE 8770`; header note on running the UI (`docker run -p 8770:8770 … ui --port 8770`) and that the UI binds localhost inside the container (map the port). |
| `README.md` / `README.es.md` | Document the UI, the two fields, the forward gate, and the new `not_forwarded` outcome. |

## 5. Data

- **`ui_settings.json`** — `{"alert_words": ["requerimiento", "multa"], "responsible_email": "jefe@despacho.mx"}`. Written by the UI (0600), read by the watcher each cycle. Not committed (gitignored). Not secret, but operator data.
- No change to `clients.secret`, the audit DB, or credential handling. The UI never touches the secrets store (no master password needed to run it).

## 6. Behavior & compatibility

- Empty `alert_words` → `should_forward` returns True → every genuine notification forwarded (unchanged behavior).
- New terminal outcome `"not_forwarded"` joins the existing set (alert_sent, quarantined, unknown_client, fetch_failed, skipped_duplicate) → now six. Every message still ends in exactly one.
- Recipient: if the UI sets a valid `responsible_email`, it overrides `config.yaml`; a `--responsible` flag still wins over both; empty UI value → fall back to config.
- Matching is accent/case-insensitive so operators can type "sancion" and match "sanción".
- Dry-run remains fully side-effect-free (the gate is evaluated but nothing is sent).

## 7. Security

- Flask binds `127.0.0.1` only — never `0.0.0.0`. Not to be exposed to the network.
- Per-process CSRF token on the POST form (a local malicious page cannot silently repoint the recipient or clear the words).
- Recipient email validated before save; invalid input rejected with a message, previous value kept.
- `ui_settings.json` written 0600. UI does not read or display any credential/secret.
- The recipient address flows into the same `html.escape`d alert path; no new injection surface.

## 8. Testing

- `test_alert_words.py`: `parse_words` (commas/spaces/dupes/empties), `normalize` (accents/case), `should_forward` (match, no-match, empty→True, accent-insensitive).
- `test_settings.py`: load defaults on missing/corrupt file; save round-trip; `valid_email`; file perms 0600; unknown keys ignored.
- `test_pipeline.py`: words match → `alert_sent` + send; no match → `not_forwarded` + no send; empty words → forward all; dry-run still sends nothing.
- `test_webui.py`: Flask test client — `GET /` renders both inputs with current values; `POST /` with valid token saves words + recipient; invalid email → not saved + message; bad/missing CSRF token → 400; `?lang=en` shows English labels.
- `test_i18n.py`: es/en key parity still holds with the new UI keys.
- `test_main.py`: recipient precedence (flag > settings > config); `run_once` passes alert words + reader through.

## 9. Out of scope

- Authentication / multi-user / remote access to the UI.
- Editing any other config (mailbox, clients, tenant) from the UI — only alert words + recipient.
- Per-client alert words or per-client recipients.
- Live-styling framework/JS build; the page is server-rendered HTML with minimal inline CSS.
