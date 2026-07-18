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
silently dropped: each one ends in exactly one of alert-sent, quarantined,
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
