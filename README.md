> 🌐 English | [Español](README.es.md)

# julia_tool — SAT Buzón Tributario watcher

`julia_tool` is an unattended watcher for a Mexican accountancy office that supervises
many clients' fiscal obligations. SAT (Servicio de Administración Tributaria) sends
Buzón Tributario notification e-mails to a single shared Microsoft 365 mailbox; the
e-mail itself is only a notice, never the actual document. The tool polls that mailbox
via Microsoft Graph, verifies each message is genuinely from SAT (SPF/DKIM/DMARC domain
alignment, not just an SPF pass) before trusting it, extracts the client's RFC (fiscal
ID) from the message, logs into the SAT Buzón Tributario portal with that client's
stored credentials (e.firma or CIEC) to download the real notification PDF, classifies
its urgency (requerimiento, multa, sanción, embargo, …) from the PDF text, and e-mails
an alert with the PDF attached to the office's fixed responsible person. Every step —
sender verification, credential use, and alert — is logged, and no message is ever
silently dropped: each one ends in exactly one of alert-sent, not-forwarded, quarantined,
unknown-client, fetch-failed, or skipped-duplicate.

## Legal / operational prerequisite

Before this tool is pointed at any client's SAT credentials, **the firm must hold a
signed authorization (carta responsiva) from that client** granting the firm custody of
their e.firma (.cer/.key + password) or CIEC (Contraseña) credentials for this purpose.
Do not add a client to the encrypted store (`client add`, below) without that signed
authorization on file. This is a legal prerequisite, not a technical one — the tool
does not check for it.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
playwright install chromium
```

Requires Python 3.12+. `playwright install chromium` downloads the browser binary the
Buzón portal automation drives; without it, `_fetch_efirma`/`_fetch_ciec` (once
completed — see "Current status" below) and the `docs/manual-validation.md` checklist
cannot run.

## Azure / Entra app registration

The tool authenticates to Microsoft Graph as the *operator*, not as an application
identity — this way it can only do what the signed-in operator is already permitted to
do on the shared mailbox, and every token is tied to a real person.

1. In the [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App
   registrations** → **New registration**.
   - Supported account types: single tenant (accounts in this organizational directory
     only), unless the firm's tenant setup requires otherwise.
   - Leave the redirect URI blank for now — device-code flow does not use one.
2. Under **Authentication**, enable **"Allow public client flows"** → set to **Yes**,
   and save. This registers the app as a *public client* (no client secret is stored or
   used — `GraphClient` only ever sends `client_id` + `tenant_id`, see
   `julia_tool/graph_client.py`).
3. Under **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Delegated permissions**, add:
   - `Mail.Read.Shared`
   - `Mail.Send.Shared`
   Click **Grant admin consent** for the tenant (both are delegated, but a tenant admin
   typically still needs to consent once for the org).
4. Note the **Application (client) ID** and the **Directory (tenant) ID** from the
   registration's Overview page.
5. **Delegated access to the shared mailbox**: because these are `.Shared` permissions,
   the *operator's own mailbox account* — the person who runs `julia_tool` and completes
   the device-code sign-in — must separately have delegated **Full Access** and
   **Send As** (or **Send on Behalf**) rights on the shared office mailbox
   (`mailbox:` in `config.yaml`). Grant this in Exchange admin center /
   `Add-MailboxPermission` + `Add-RecipientPermission` (or the Microsoft 365 admin
   center's shared-mailbox delegate settings) — the app registration alone does not
   grant mailbox access.
6. Put the two IDs into `config.yaml`:
   ```yaml
   tenant_id: "<Directory (tenant) ID>"
   client_id: "<Application (client) ID>"
   ```

The first run (`python -m julia_tool.main`, with no cached token) prints a
`https://microsoft.com/devicelogin` code — the operator opens that URL, enters the
code, and signs in interactively once; after that, MSAL's token cache
(`.token_cache.bin`, already git-ignored) keeps the session silent.

## Config

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml`:
- `mailbox`: the shared office mailbox address that receives SAT notices.
- `responsible_email`: the fixed person who receives every alert.
- `tenant_id` / `client_id`: from the Azure app registration above.
- `portal.*`: SAT portal URLs and CSS selectors — see
  `docs/manual-validation.md` for how these are confirmed on-site.
- `keyword_map`: **optional**. Omit it entirely to use the built-in Spanish urgency
  keyword rules (`julia_tool/classify.py:DEFAULT_KEYWORDS`); only set it to override
  those defaults.
- `language`: **optional**, `es` | `en` — the language used for console output,
  the `client` CLI, and alert e-mails. Defaults to `es`; an invalid value also falls
  back to `es`. Override it for a single run without editing `config.yaml` with the
  `--lang` flag (see "Run" below).

## Add clients

Client credentials live in an encrypted store (`clients.secret`), protected by a master
password you choose. Set it once per shell session (or be prompted interactively):

```bash
export JULIA_MASTER_PW='choose-a-strong-master-password'
```

Add a client using CIEC (Contraseña):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client add \
  --rfc XAXX010101000 --name "Cliente Ejemplo SA de CV" \
  --auth-type ciec --ciec-password 'the-client-CIEC-password'
```

Add a client using e.firma (FIEL):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client add \
  --rfc XAXX010101000 --name "Cliente Ejemplo SA de CV" \
  --auth-type efirma \
  --cer-path /secure/certs/XAXX010101000.cer \
  --key-path /secure/certs/XAXX010101000.key \
  --key-password 'the-.key-file-password'
```

List and remove clients:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client list
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client remove --rfc XAXX010101000
```

## Run

Always start with a dry run — it runs the full pipeline (Graph poll, sender
verification, RFC extraction, credential lookup) but never logs into the SAT portal and
never sends mail; it just prints the per-message outcome tally:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main --once --dry-run
```

Once the dry-run tally looks right, run one real cycle (portal fetch + alert e-mails
enabled):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main --once
```

Then run continuously (no `--once`) — it loops forever, polling every
`poll_interval_s` seconds (default 300), suitable for a long-running service, or drop
`--once` for cron/Task Scheduler instead:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main
```

Useful flags on every run:
- `--responsible EMAIL` — send this run's alerts to `EMAIL` instead of
  `config.yaml`'s `responsible_email` (e.g. to route a test run to yourself without
  editing the config).
- `--config PATH` — use a config file other than `config.yaml` (e.g. a per-environment
  or per-test config).
- `--lang es|en` — override `config.yaml`'s `language` for this run's console output,
  alert e-mails, and the `client` CLI (`--lang` also works before `client add` /
  `client list` / `client remove`). Default is `es`; an unrecognized value falls back
  to `es`.

## WhatsApp alerts (optional)

Besides the e-mail, `julia_tool` can send a short WhatsApp message to the responsible
person for every alert (urgent notice, download failed, unknown client, quarantined
e-mail). It uses Meta's official **WhatsApp Cloud API**. The e-mail is always sent
first; if WhatsApp fails, the error is printed and the e-mail and the processing of
the notice carry on.

One-time setup by the firm:

1. Create (or use) the firm's **Meta Business** account at business.facebook.com.
2. At developers.facebook.com create an app of type **Business** and add the
   **WhatsApp** product. Add the firm's sending phone number (it must not be in use
   in the WhatsApp phone app) and verify it. Note its **Phone number ID**.
3. Create a **permanent access token**: Business settings → System users → add a
   system user → assign it the app and the WhatsApp account → *Generate token* with
   the `whatsapp_business_messaging` permission. Keep it secret.
4. In WhatsApp Manager → **Message templates** → create a template:
   - Category **Utility**, name `julia_aviso_sat`, language **Spanish (MEX)** (`es_MX`)
   - Body: `Aviso de julia_tool: {{1}}. Cliente: {{2}}. Revisa el correo del despacho para ver el detalle.`
   - Submit it for approval (usually minutes to a few hours).
5. Fill the `whatsapp:` block in `config.yaml` (see `config.example.yaml`): set
   `enabled: true`, the `phone_number_id` and the recipient number(s) in international
   format, digits only (Mexico: `52` + 10 digits).
6. Start the tool with the token in the environment:
   ```bash
   JULIA_WA_TOKEN='EAAG...' JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main
   ```
   With Docker, add `-e JULIA_WA_TOKEN` to `docker run`. Without the variable the tool
   prints a warning and sends e-mail only.

The message reads, for example: *"Aviso de julia_tool: URGENTE — requerimiento.
Cliente: ACME (XAXX010101000). Revisa el correo del despacho para ver el detalle."*
Set `include_client_details: false` to leave the client name and RFC out of WhatsApp
(the second variable then shows "—"). Meta charges a small fee per delivered utility
message; check Meta's current pricing for Mexico. If a Mexican number is not reached,
check the number format Meta shows for it in the API's response (`wa_id`).

## Web UI

```bash
python -m julia_tool.main ui --port 8770
```

This opens a small local web page (`http://127.0.0.1:8770`) where the operator can set
two things without editing `config.yaml` or restarting the watcher:
- **Alert words** — a comma-separated list (e.g. `requerimiento, multa, sanción`).
- **Recipient email** — the address that receives the alert e-mails.

Both are saved to `settings_path` in `config.yaml` (default `ui_settings.json`, already
git-ignored — it holds operator data, not a secret) and are re-read by the watcher on
every poll cycle, so edits take effect without restarting `julia_tool`.

**The forward gate.** Alert words gate the *forward* of a genuine SAT notification, not
its classification — every message is still verified, fetched, and classified as
before. The words are matched against the notification e-mail (subject + body) and the
text of the fetched SAT document:
- An **empty** word list forwards everything — this is the default, so behavior is
  unchanged until the operator opts in by typing at least one word.
- If any word **matches**, the alert is sent to the recipient as usual (outcome
  `alert_sent`).
- If **no word matches**, the alert is **not sent** — the outcome is `not_forwarded`.
  It is still logged and audited (nothing is silently dropped), it is just not e-mailed.

Matching is **accent- and case-insensitive**, so `sancion` matches `sanción` and
`MULTA` matches `multa`.

**The quarantine, unknown-client, and fetch-failed alerts are never gated** — those are
security/operational notices, not SAT notifications, and are always sent regardless of
alert words.

**Recipient precedence**, highest wins: the `--responsible` command-line flag on this
run > the recipient email saved in the UI (if set) > `responsible_email` in
`config.yaml`.

The UI binds to `127.0.0.1` only — it is never reachable from the network, and it does
not touch the encrypted credential store or ask for the master password.

## Security notes

- **Encrypted credential store.** `clients.secret` is Fernet-encrypted; the encryption
  key is derived from your master password with scrypt (`n=2**16, r=8, p=1`), never
  stored. The file is written with `0600` permissions and replaced atomically on every
  write (`julia_tool/secrets_store.py`).
- **Audit log.** Every credential use (RFC, purpose, outcome, timestamp) is written to
  the `audit` table in `state.sqlite` *before* the portal login attempt — the log shows
  every time a client's SAT credentials were used, whether or not the fetch succeeded
  (`julia_tool/state.py`).
- **`.gitignore` coverage.** The repo's `.gitignore` already blocks `clients.secret`,
  `*.cer`, `*.key`, `.token_cache*`, `state.sqlite`, and `downloads/` — never commit
  these, and double-check `git status` before committing if you've moved any of them.
- **Keep `.cer`/`.key` files off the repo entirely.** The secrets store only holds
  *paths* to e.firma certificate/key files, not the files themselves — store the actual
  `.cer`/`.key` files in a directory outside the repo with OS-level ACLs restricting
  read access to the account that runs `julia_tool` (e.g. `chmod 700` the directory,
  owned by a dedicated service account, not world-readable).
- **Sender verification always precedes credential use.** A message that fails the
  SPF/DKIM/DMARC domain-alignment check (`julia_tool/verify.py`) is quarantined and
  never triggers a portal login — see `docs/superpowers/specs/2026-07-18-sat-buzon-watcher-design.md`
  §6 for the full security model.

## Current status / completing the live portal fetch

Everything in this repository is built and unit-tested — run the suite with:

```bash
.venv/bin/python -m pytest -q
```

**Except** the two live browser-automation methods, `BuzonFetcher._fetch_efirma` and
`BuzonFetcher._fetch_ciec` in `julia_tool/buzon.py`, which are currently fail-safe
`NotImplementedError` stubs. Their real portal selectors and — for e.firma — the FIEL
client-certificate challenge can only be confirmed against the live SAT portal with a
real client's credentials, which is not something that can be validated offline. A
complete, copy-pasteable reference implementation of both flows, plus the on-site
checklist to confirm selectors and move the confirmed code into `buzon.py`, is in
[`docs/manual-validation.md`](docs/manual-validation.md).

Until that on-site step is done, the tool is still fully functional end to end: every
government e-mail is verified, its client identified, and an alert sent to the
responsible person. When the live fetch is unavailable (stub raises), the pipeline
(`julia_tool/pipeline.py`) catches it as a normal `fetch_failed` outcome and sends a
fallback alert containing the client's name, RFC, and a manual link to the SAT portal
(`portal.buzon_url` in `config.yaml`) — so no notification is ever missed while the
live automation is being finished.
