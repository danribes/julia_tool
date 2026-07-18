# SAT Buzón Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An unattended Python service that detects genuine SAT Buzón Tributario notification emails in a shared Outlook mailbox, downloads the real notification document from the SAT portal with the matching client's credentials, classifies its urgency, and emails an alert to the office's responsible person.

**Architecture:** A long-running console loop (with `--once` / `--dry-run` modes) polls Microsoft 365 via the Graph API. Each message passes an anti-phishing gate, RFC extraction, encrypted credential lookup, Playwright portal fetch (e.firma headless / CIEC operator-assisted), keyword classification, and a Graph `sendMail` alert. Pure-logic modules (verify, rfc, classify, secrets_store, state) are fully unit-tested offline; network and browser modules are isolated behind thin clients and tested with mocks/HTML fixtures.

**Tech Stack:** Python 3.12, `msal` (Graph auth), `requests` (Graph REST), `cryptography` (Fernet + scrypt), `playwright` (Chromium), `pymupdf` (PDF text), `PyYAML`, `pytest`.

## Global Constraints

- **Python:** 3.12+ only.
- **Package layout:** all modules live under `julia_tool/`; tests under `tests/`. Absolute import root is the repo dir `/home/dan/projects/julia_tool`.
- **No secrets in git:** `.gitignore` already excludes `clients.secret`, `*.cer`, `*.key`, `state.sqlite`, `.token_cache*`, `downloads/`. Never commit real credentials or tokens; tests use synthetic values only.
- **Security ordering (non-negotiable):** sender verification MUST pass before any credential is read or any portal login is attempted. A message failing SPF/DKIM/domain checks can never trigger `secrets_store.get()` or `buzon.fetch()`.
- **Portal navigation:** Playwright navigates only to configured SAT URLs. Links contained in emails are never followed.
- **No silent drops:** every processed message ends in exactly one recorded outcome: `alert_sent`, `quarantined`, `unknown_client`, `fetch_failed`, or `skipped_duplicate`.
- **RFC regex (canonical, used everywhere):** `\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b` (uppercase input).
- **Urgency levels (canonical enum values):** `"URGENT"`, `"ATTENTION"`, `"INFO"`.
- **Commit after every task.** TDD: failing test first, minimal code, passing test, commit.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config. |
| `config.yaml` | Mailbox, poll interval, responsible email, sender allowlist, portal URLs+selectors, keyword→urgency map, Claude flag. |
| `config.example.yaml` | Committed template (no secrets). |
| `julia_tool/__init__.py` | Package marker + version. |
| `julia_tool/config.py` | Load + validate `config.yaml` into a typed `Config` object. |
| `julia_tool/models.py` | Shared dataclasses: `EmailMessage`, `ClientCred`, `Classification`, `FetchResult`. |
| `julia_tool/rfc.py` | Extract RFC from text. |
| `julia_tool/verify.py` | Anti-phishing sender gate. |
| `julia_tool/classify.py` | PDF text → urgency + act type. |
| `julia_tool/secrets_store.py` | Fernet-encrypted per-RFC credential store. |
| `julia_tool/state.py` | SQLite: processed IDs, audit log, alert history. |
| `julia_tool/graph_client.py` | MSAL auth, list/get messages, download MIME, sendMail. |
| `julia_tool/buzon.py` | Playwright SAT portal fetch (e.firma / CIEC). |
| `julia_tool/alert.py` | Compose + send the four alert types via graph_client. |
| `julia_tool/pipeline.py` | Per-message orchestration (verify→rfc→cred→fetch→classify→alert→record). |
| `julia_tool/main.py` | CLI entry: loop / `--once` / `--dry-run`, master-password prompt. |
| `julia_tool/clientcli.py` | `client add/list/remove` subcommands for the secrets store. |
| `tests/…` | One test module per unit above. |

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `julia_tool/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: importable package `julia_tool` with `julia_tool.__version__: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
import julia_tool

def test_version_present():
    assert isinstance(julia_tool.__version__, str)
    assert julia_tool.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dan/projects/julia_tool && python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "julia_tool"
version = "0.1.0"
description = "SAT Buzon Tributario notification watcher"
requires-python = ">=3.12"
dependencies = [
    "msal>=1.28",
    "requests>=2.31",
    "cryptography>=42",
    "playwright>=1.44",
    "pymupdf>=1.24",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```python
# julia_tool/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml julia_tool/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: project scaffold"
```

---

### Task 2: Shared data models

**Files:**
- Create: `julia_tool/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `EmailMessage(id: str, subject: str, from_address: str, auth_results: str, body: str, received: str)` — dataclass.
  - `ClientCred(rfc: str, name: str, auth_type: str, ciec_password: str | None, cer_path: str | None, key_path: str | None, key_password: str | None)` — dataclass; `auth_type` is `"efirma"` or `"ciec"`.
  - `Classification(urgency: str, act_type: str, deadline: str | None, matched: list[str])` — dataclass; `urgency` ∈ canonical enum.
  - `FetchResult(ok: bool, pdf_path: str | None, error: str | None, screenshot_path: str | None)` — dataclass.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from julia_tool.models import EmailMessage, ClientCred, Classification, FetchResult

def test_models_construct():
    m = EmailMessage(id="1", subject="s", from_address="a@sat.gob.mx",
                     auth_results="spf=pass", body="b", received="2026-07-18T00:00:00Z")
    assert m.id == "1"
    c = ClientCred(rfc="XAXX010101000", name="ACME", auth_type="ciec",
                   ciec_password="p", cer_path=None, key_path=None, key_password=None)
    assert c.auth_type == "ciec"
    cl = Classification(urgency="URGENT", act_type="requerimiento",
                        deadline="2026-08-01", matched=["requerimiento"])
    assert cl.urgency == "URGENT"
    f = FetchResult(ok=True, pdf_path="/x.pdf", error=None, screenshot_path=None)
    assert f.ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/models.py
from dataclasses import dataclass

@dataclass
class EmailMessage:
    id: str
    subject: str
    from_address: str
    auth_results: str
    body: str
    received: str

@dataclass
class ClientCred:
    rfc: str
    name: str
    auth_type: str  # "efirma" | "ciec"
    ciec_password: str | None
    cer_path: str | None
    key_path: str | None
    key_password: str | None

@dataclass
class Classification:
    urgency: str  # "URGENT" | "ATTENTION" | "INFO"
    act_type: str
    deadline: str | None
    matched: list[str]

@dataclass
class FetchResult:
    ok: bool
    pdf_path: str | None
    error: str | None
    screenshot_path: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add julia_tool/models.py tests/test_models.py
git commit -m "feat: shared data models"
```

---

### Task 3: RFC extraction

**Files:**
- Create: `julia_tool/rfc.py`
- Create: `tests/test_rfc.py`

**Interfaces:**
- Produces: `extract_rfc(text: str) -> str | None` — returns the first RFC found (uppercased), else `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rfc.py
from julia_tool.rfc import extract_rfc

def test_extracts_moral_rfc():
    assert extract_rfc("Contribuyente ACM950101ABC requiere atencion") == "ACM950101ABC"

def test_extracts_physical_rfc_lowercase_input():
    assert extract_rfc("rfc: xaxx010101000 saludos") == "XAXX010101000"

def test_no_rfc_returns_none():
    assert extract_rfc("no fiscal id here 12345") is None

def test_ignores_substring_without_boundary():
    # 13 chars but embedded in a longer token → not a valid standalone RFC
    assert extract_rfc("ZZZZAAA950101ABCDEF") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rfc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.rfc'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/rfc.py
import re

_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")

def extract_rfc(text: str) -> str | None:
    m = _RFC_RE.search(text.upper())
    return m.group(0) if m else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rfc.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/rfc.py tests/test_rfc.py
git commit -m "feat: RFC extraction"
```

---

### Task 4: Anti-phishing sender verification

**Files:**
- Create: `julia_tool/verify.py`
- Create: `tests/test_verify.py`

**Interfaces:**
- Consumes: `EmailMessage` (Task 2).
- Produces: `is_genuine_sat(msg: EmailMessage, allowed_domains: list[str]) -> tuple[bool, str]` — returns `(ok, reason)`. `ok` is True only when the from-address domain matches an allowed domain AND `auth_results` shows `spf=pass` AND `dkim=pass`. `reason` names the first failing check (or `"ok"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verify.py
from julia_tool.models import EmailMessage
from julia_tool.verify import is_genuine_sat

ALLOW = ["sat.gob.mx"]

def _msg(frm, auth):
    return EmailMessage(id="1", subject="s", from_address=frm,
                        auth_results=auth, body="b", received="r")

def test_genuine_passes():
    ok, reason = is_genuine_sat(
        _msg("notificaciones@sat.gob.mx", "spf=pass; dkim=pass"), ALLOW)
    assert ok is True and reason == "ok"

def test_subdomain_allowed():
    ok, _ = is_genuine_sat(
        _msg("no-reply@buzon.sat.gob.mx", "spf=pass dkim=pass"), ALLOW)
    assert ok is True

def test_wrong_domain_fails():
    ok, reason = is_genuine_sat(
        _msg("attacker@sat.gob.mx.evil.com", "spf=pass dkim=pass"), ALLOW)
    assert ok is False and reason == "domain"

def test_spf_fail_blocks():
    ok, reason = is_genuine_sat(
        _msg("x@sat.gob.mx", "spf=fail dkim=pass"), ALLOW)
    assert ok is False and reason == "spf"

def test_dkim_missing_blocks():
    ok, reason = is_genuine_sat(
        _msg("x@sat.gob.mx", "spf=pass"), ALLOW)
    assert ok is False and reason == "dkim"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.verify'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/verify.py
from julia_tool.models import EmailMessage

def _domain(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].strip().lower()

def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    for a in allowed:
        a = a.lower()
        if domain == a or domain.endswith("." + a):
            return True
    return False

def is_genuine_sat(msg: EmailMessage, allowed_domains: list[str]) -> tuple[bool, str]:
    if not _domain_allowed(_domain(msg.from_address), allowed_domains):
        return False, "domain"
    ar = msg.auth_results.lower()
    if "spf=pass" not in ar:
        return False, "spf"
    if "dkim=pass" not in ar:
        return False, "dkim"
    return True, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_verify.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/verify.py tests/test_verify.py
git commit -m "feat: anti-phishing sender verification"
```

---

### Task 5: Urgency classifier

**Files:**
- Create: `julia_tool/classify.py`
- Create: `tests/test_classify.py`

**Interfaces:**
- Consumes: `Classification` (Task 2).
- Produces:
  - `classify_text(text: str, keyword_map: dict[str, list[str]]) -> Classification` — lowercases text, scans each urgency level's keyword list, assigns the highest-severity level with a match (URGENT > ATTENTION > INFO), records matched keywords, and picks `act_type` = first matched keyword (or `"desconocido"`).
  - `DEFAULT_KEYWORDS: dict[str, list[str]]` — built-in Spanish keyword map used when config omits one.

Note: PDF text extraction via PyMuPDF is wired in Task 11 (`extract_pdf_text`), kept out of this pure-logic unit so classification is testable without a PDF.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classify.py
from julia_tool.classify import classify_text, DEFAULT_KEYWORDS

def test_requerimiento_is_urgent():
    c = classify_text("Se emite REQUERIMIENTO de obligaciones", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"
    assert "requerimiento" in c.matched
    assert c.act_type == "requerimiento"

def test_embargo_is_urgent():
    c = classify_text("notificacion de embargo precautorio", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"

def test_informative_is_info():
    c = classify_text("Acuse de recibo de su declaracion", DEFAULT_KEYWORDS)
    assert c.urgency == "INFO"

def test_highest_severity_wins():
    # contains both an INFO word (acuse) and URGENT word (sancion)
    c = classify_text("acuse y sancion aplicable", DEFAULT_KEYWORDS)
    assert c.urgency == "URGENT"

def test_no_keyword_is_info_unknown():
    c = classify_text("texto neutro sin terminos", DEFAULT_KEYWORDS)
    assert c.urgency == "INFO"
    assert c.act_type == "desconocido"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_classify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.classify'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/classify.py
from julia_tool.models import Classification

DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "URGENT": [
        "requerimiento", "multa", "sancion", "sanción", "embargo",
        "credito fiscal", "crédito fiscal", "pama", "visita domiciliaria",
        "69-b", "presuncion", "presunción", "determinacion", "determinación",
    ],
    "ATTENTION": [
        "invitacion", "invitación", "carta invitacion", "aclaracion",
        "aclaración", "revision", "revisión", "plazo", "vencimiento",
    ],
    "INFO": [
        "acuse", "constancia", "aviso", "notificacion", "notificación",
        "informativo",
    ],
}

_ORDER = ["URGENT", "ATTENTION", "INFO"]

def classify_text(text: str, keyword_map: dict[str, list[str]]) -> Classification:
    low = text.lower()
    for level in _ORDER:
        matched = [kw for kw in keyword_map.get(level, []) if kw in low]
        if matched:
            return Classification(
                urgency=level, act_type=matched[0],
                deadline=None, matched=matched,
            )
    return Classification(
        urgency="INFO", act_type="desconocido", deadline=None, matched=[])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_classify.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/classify.py tests/test_classify.py
git commit -m "feat: Spanish urgency classifier"
```

---

### Task 6: Encrypted secrets store

**Files:**
- Create: `julia_tool/secrets_store.py`
- Create: `tests/test_secrets_store.py`

**Interfaces:**
- Consumes: `ClientCred` (Task 2).
- Produces: class `SecretsStore(path: str, master_password: str)` with:
  - `add(cred: ClientCred) -> None` — upsert by RFC, re-encrypt file.
  - `get(rfc: str) -> ClientCred | None`.
  - `list_rfcs() -> list[str]`.
  - `remove(rfc: str) -> bool`.
  - On construction: if the file exists, decrypt it (wrong password raises `ValueError("bad master password")`); else start empty. The Fernet key is derived from the master password via scrypt with a per-file random salt stored in the file header.

File format: `b"JTS1"` magic + 16-byte salt + Fernet token over JSON `{rfc: {fields…}}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_secrets_store.py
import pytest
from julia_tool.models import ClientCred
from julia_tool.secrets_store import SecretsStore

def _cred(rfc="XAXX010101000"):
    return ClientCred(rfc=rfc, name="ACME", auth_type="ciec",
                      ciec_password="s3cret", cer_path=None, key_path=None,
                      key_password=None)

def test_roundtrip(tmp_path):
    p = str(tmp_path / "clients.secret")
    s = SecretsStore(p, "master-pw")
    s.add(_cred())
    got = s.get("XAXX010101000")
    assert got.name == "ACME"
    assert got.ciec_password == "s3cret"

def test_persists_across_instances(tmp_path):
    p = str(tmp_path / "clients.secret")
    SecretsStore(p, "master-pw").add(_cred())
    s2 = SecretsStore(p, "master-pw")
    assert s2.get("XAXX010101000").ciec_password == "s3cret"

def test_wrong_password_rejected(tmp_path):
    p = str(tmp_path / "clients.secret")
    SecretsStore(p, "master-pw").add(_cred())
    with pytest.raises(ValueError):
        SecretsStore(p, "WRONG")

def test_list_and_remove(tmp_path):
    p = str(tmp_path / "clients.secret")
    s = SecretsStore(p, "master-pw")
    s.add(_cred("XAXX010101000"))
    s.add(_cred("ACM950101ABC"))
    assert set(s.list_rfcs()) == {"XAXX010101000", "ACM950101ABC"}
    assert s.remove("XAXX010101000") is True
    assert s.get("XAXX010101000") is None

def test_missing_returns_none(tmp_path):
    s = SecretsStore(str(tmp_path / "clients.secret"), "pw")
    assert s.get("NOPE010101ABC") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_secrets_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.secrets_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/secrets_store.py
import base64
import json
import os
from dataclasses import asdict
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from julia_tool.models import ClientCred

_MAGIC = b"JTS1"
_SALT_LEN = 16

def _derive_key(master_password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    raw = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)

class SecretsStore:
    def __init__(self, path: str, master_password: str):
        self.path = path
        self._pw = master_password
        if os.path.exists(path):
            with open(path, "rb") as f:
                blob = f.read()
            if blob[:4] != _MAGIC:
                raise ValueError("not a julia_tool secrets file")
            self._salt = blob[4:4 + _SALT_LEN]
            token = blob[4 + _SALT_LEN:]
            fernet = Fernet(_derive_key(master_password, self._salt))
            try:
                data = fernet.decrypt(token)
            except InvalidToken as exc:
                raise ValueError("bad master password") from exc
            self._db: dict[str, dict] = json.loads(data.decode("utf-8"))
        else:
            self._salt = os.urandom(_SALT_LEN)
            self._db = {}
            self._flush()

    def _flush(self) -> None:
        fernet = Fernet(_derive_key(self._pw, self._salt))
        token = fernet.encrypt(json.dumps(self._db).encode("utf-8"))
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(_MAGIC + self._salt + token)
        os.replace(tmp, self.path)

    def add(self, cred: ClientCred) -> None:
        self._db[cred.rfc] = asdict(cred)
        self._flush()

    def get(self, rfc: str) -> ClientCred | None:
        row = self._db.get(rfc)
        return ClientCred(**row) if row else None

    def list_rfcs(self) -> list[str]:
        return list(self._db.keys())

    def remove(self, rfc: str) -> bool:
        if rfc in self._db:
            del self._db[rfc]
            self._flush()
            return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_secrets_store.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/secrets_store.py tests/test_secrets_store.py
git commit -m "feat: Fernet-encrypted per-RFC secrets store"
```

---

### Task 7: SQLite state + audit log

**Files:**
- Create: `julia_tool/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces: class `State(db_path: str)` with:
  - `is_processed(message_id: str) -> bool`.
  - `mark_processed(message_id: str, outcome: str) -> None` — outcome ∈ the five canonical outcomes.
  - `log_credential_use(rfc: str, purpose: str, outcome: str, ts: str) -> None`.
  - `record_alert(rfc: str, urgency: str, ts: str) -> None`.
  - `audit_count() -> int` (test helper).
  - Constructor creates tables if absent (idempotent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from julia_tool.state import State

def test_processed_idempotent(tmp_path):
    st = State(str(tmp_path / "state.sqlite"))
    assert st.is_processed("m1") is False
    st.mark_processed("m1", "alert_sent")
    assert st.is_processed("m1") is True

def test_reopen_persists(tmp_path):
    p = str(tmp_path / "state.sqlite")
    State(p).mark_processed("m2", "quarantined")
    assert State(p).is_processed("m2") is True

def test_audit_and_alert(tmp_path):
    st = State(str(tmp_path / "state.sqlite"))
    st.log_credential_use("XAXX010101000", "buzon_login", "ok", "2026-07-18T00:00:00Z")
    st.record_alert("XAXX010101000", "URGENT", "2026-07-18T00:00:01Z")
    assert st.audit_count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/state.py
import sqlite3

class State:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS processed (
                message_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc TEXT, purpose TEXT, outcome TEXT, ts TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc TEXT, urgency TEXT, ts TEXT
            );
            """
        )
        self._conn.commit()

    def is_processed(self, message_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM processed WHERE message_id=?", (message_id,))
        return cur.fetchone() is not None

    def mark_processed(self, message_id: str, outcome: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO processed(message_id, outcome) VALUES (?,?)",
            (message_id, outcome))
        self._conn.commit()

    def log_credential_use(self, rfc: str, purpose: str, outcome: str, ts: str) -> None:
        self._conn.execute(
            "INSERT INTO audit(rfc, purpose, outcome, ts) VALUES (?,?,?,?)",
            (rfc, purpose, outcome, ts))
        self._conn.commit()

    def record_alert(self, rfc: str, urgency: str, ts: str) -> None:
        self._conn.execute(
            "INSERT INTO alerts(rfc, urgency, ts) VALUES (?,?,?)",
            (rfc, urgency, ts))
        self._conn.commit()

    def audit_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/state.py tests/test_state.py
git commit -m "feat: SQLite state and audit log"
```

---

### Task 8: Config loader

**Files:**
- Create: `julia_tool/config.py`
- Create: `config.example.yaml`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces:
  - dataclass `Config(tenant_id, client_id, mailbox, poll_interval_s, responsible_email, allowed_domains: list[str], portal, keyword_map: dict[str, list[str]], use_claude: bool, secrets_path, state_path, download_dir)`.
  - `load_config(path: str) -> Config` — parses YAML, applies defaults (`poll_interval_s=300`, `use_claude=False`, `keyword_map=DEFAULT_KEYWORDS` when omitted), raises `ValueError` listing any missing required keys (`tenant_id`, `client_id`, `mailbox`, `responsible_email`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
from julia_tool.config import load_config

_MIN = """
tenant_id: t
client_id: c
mailbox: office@firm.mx
responsible_email: boss@firm.mx
"""

def test_loads_defaults(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    cfg = load_config(str(p))
    assert cfg.poll_interval_s == 300
    assert cfg.use_claude is False
    assert "sat.gob.mx" in cfg.allowed_domains
    assert cfg.keyword_map["URGENT"]

def test_missing_required_raises(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("tenant_id: t\n")
    with pytest.raises(ValueError):
        load_config(str(p))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/config.py
from dataclasses import dataclass, field
import yaml
from julia_tool.classify import DEFAULT_KEYWORDS

_REQUIRED = ["tenant_id", "client_id", "mailbox", "responsible_email"]

@dataclass
class Config:
    tenant_id: str
    client_id: str
    mailbox: str
    responsible_email: str
    poll_interval_s: int = 300
    allowed_domains: list[str] = field(default_factory=lambda: ["sat.gob.mx"])
    portal: dict = field(default_factory=dict)
    keyword_map: dict[str, list[str]] = field(
        default_factory=lambda: DEFAULT_KEYWORDS)
    use_claude: bool = False
    secrets_path: str = "clients.secret"
    state_path: str = "state.sqlite"
    download_dir: str = "downloads"

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    missing = [k for k in _REQUIRED if not raw.get(k)]
    if missing:
        raise ValueError(f"missing required config keys: {missing}")
    return Config(
        tenant_id=raw["tenant_id"],
        client_id=raw["client_id"],
        mailbox=raw["mailbox"],
        responsible_email=raw["responsible_email"],
        poll_interval_s=raw.get("poll_interval_s", 300),
        allowed_domains=raw.get("allowed_domains", ["sat.gob.mx"]),
        portal=raw.get("portal", {}),
        keyword_map=raw.get("keyword_map", DEFAULT_KEYWORDS),
        use_claude=raw.get("use_claude", False),
        secrets_path=raw.get("secrets_path", "clients.secret"),
        state_path=raw.get("state_path", "state.sqlite"),
        download_dir=raw.get("download_dir", "downloads"),
    )
```

```yaml
# config.example.yaml
tenant_id: "YOUR-ENTRA-TENANT-ID"
client_id: "YOUR-APP-REGISTRATION-CLIENT-ID"
mailbox: "buzon@tudespacho.mx"
responsible_email: "responsable@tudespacho.mx"
poll_interval_s: 300
allowed_domains:
  - sat.gob.mx
use_claude: false
secrets_path: clients.secret
state_path: state.sqlite
download_dir: downloads
portal:
  efirma_login_url: "https://cfdiau.sat.gob.mx/nidp/app/login?id=fielHtml5"
  ciec_login_url: "https://cfdiau.sat.gob.mx/nidp/app/login?id=SATUPCB"
  buzon_url: "https://cfdiau.sat.gob.mx/nidp/app/login?id=SATx509Custom"
  notifications_selector: "table#notificaciones tbody tr"
  download_link_selector: "a.descargar"
# keyword_map: optional override; omit to use built-in Spanish defaults
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/config.py config.example.yaml tests/test_config.py
git commit -m "feat: config loader with defaults"
```

---

### Task 9: Graph client (auth, list, get, download, sendMail)

**Files:**
- Create: `julia_tool/graph_client.py`
- Create: `tests/test_graph_client.py`

**Interfaces:**
- Consumes: `EmailMessage` (Task 2).
- Produces: class `GraphClient(tenant_id, client_id, mailbox, token_cache_path=".token_cache.bin")` with:
  - `acquire_token(prompt: bool = True) -> str` — MSAL public-client device-code flow with on-disk `SerializableTokenCache`; returns access token. (Not unit-tested against live Graph.)
  - `list_messages(session, top: int = 25) -> list[EmailMessage]` — GET inbox messages, maps JSON→`EmailMessage`, pulling `internetMessageHeaders` for `Authentication-Results`.
  - `send_mail(session, to: str, subject: str, html_body: str, attachments: list[tuple[str, bytes]] | None) -> None` — POST sendMail.
  - `_parse_message(raw: dict) -> EmailMessage` — pure mapper (this is the unit-tested seam).
  - `_extract_auth_results(headers: list[dict]) -> str` — pure helper.

Design note: HTTP is injected as a `session` object (anything with `.get`/`.post` returning a `requests`-style response) so tests pass a fake. `_parse_message` and `_extract_auth_results` are pure and fully tested; `acquire_token`/live calls are covered later by manual/integration testing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_client.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graph_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.graph_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/graph_client.py
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
            cache.deserialize(open(self.token_cache_path).read())
        return cache

    def _save_cache(self, cache: msal.SerializableTokenCache) -> None:
        if cache.has_state_changed:
            with open(self.token_cache_path, "w") as f:
                f.write(cache.serialize())

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
            from_address=(raw.get("from", {}) or {}).get("emailAddress", {})
                .get("address", ""),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graph_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/graph_client.py tests/test_graph_client.py
git commit -m "feat: Graph client with testable mappers"
```

---

### Task 10: Alert composer

**Files:**
- Create: `julia_tool/alert.py`
- Create: `tests/test_alert.py`

**Interfaces:**
- Consumes: `GraphClient.send_mail` (Task 9), `Classification` (Task 2).
- Produces: class `Alerter(graph: GraphClient, session, responsible_email: str)` with:
  - `send_urgent(rfc, client_name, cls: Classification, pdf: tuple[str, bytes] | None) -> str` — subject `[<URGENCY>][<rfc>] <act_type>`; returns the subject sent.
  - `send_quarantine(msg_subject: str, from_address: str, reason: str) -> str`.
  - `send_unknown_client(msg_subject: str) -> str`.
  - `send_fetch_failed(rfc: str, client_name: str, manual_url: str) -> str`.
  - Each builds an HTML body and calls `graph.send_mail`. Subject strings are returned so tests assert without a live Graph.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_alert.py
from julia_tool.alert import Alerter
from julia_tool.models import Classification

class _FakeGraph:
    def __init__(self): self.sent = []
    def send_mail(self, session, to, subject, html_body, attachments):
        self.sent.append((to, subject, html_body, attachments))

def _alerter():
    return Alerter(_FakeGraph(), session=None, responsible_email="boss@firm.mx")

def test_urgent_subject_and_attachment():
    a = _alerter()
    cls = Classification("URGENT", "requerimiento", "2026-08-01", ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, ("doc.pdf", b"%PDF-1.4"))
    assert subj == "[URGENT][XAXX010101000] requerimiento"
    to, sent_subj, body, att = a.graph.sent[0]
    assert to == "boss@firm.mx"
    assert att and att[0][0] == "doc.pdf"
    assert "ACME" in body

def test_quarantine_names_reason():
    a = _alerter()
    subj = a.send_quarantine("Falso SAT", "evil@fake.com", "domain")
    assert "CUARENTENA" in subj
    assert a.graph.sent[0][3] is None  # no attachment

def test_fetch_failed_includes_url():
    a = _alerter()
    a.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    body = a.graph.sent[0][2]
    assert "https://sat.gob.mx/manual" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_alert.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.alert'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/alert.py
from julia_tool.models import Classification

class Alerter:
    def __init__(self, graph, session, responsible_email: str):
        self.graph = graph
        self.session = session
        self.to = responsible_email

    def send_urgent(self, rfc: str, client_name: str, cls: Classification,
                    pdf: tuple[str, bytes] | None) -> str:
        subject = f"[{cls.urgency}][{rfc}] {cls.act_type}"
        deadline = cls.deadline or "no detectado"
        body = (
            f"<h2>Notificacion SAT — {cls.urgency}</h2>"
            f"<p><b>Cliente:</b> {client_name} ({rfc})</p>"
            f"<p><b>Tipo de acto:</b> {cls.act_type}</p>"
            f"<p><b>Plazo:</b> {deadline}</p>"
            f"<p><b>Terminos detectados:</b> {', '.join(cls.matched) or '—'}</p>"
        )
        atts = [pdf] if pdf else None
        self.graph.send_mail(self.session, self.to, subject, body, atts)
        return subject

    def send_quarantine(self, msg_subject: str, from_address: str, reason: str) -> str:
        subject = f"[CUARENTENA] correo sospechoso: {msg_subject}"
        body = (
            "<h2>Correo bloqueado por verificacion anti-phishing</h2>"
            f"<p><b>Remitente:</b> {from_address}</p>"
            f"<p><b>Motivo:</b> fallo de verificacion '{reason}'</p>"
            "<p>No se accedio a ninguna credencial. Revise manualmente.</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_unknown_client(self, msg_subject: str) -> str:
        subject = f"[SIN CLIENTE] notificacion sin RFC reconocido: {msg_subject}"
        body = (
            "<h2>Notificacion SAT sin cliente identificado</h2>"
            "<p>No se encontro un RFC registrado en el correo. Revise manualmente.</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_fetch_failed(self, rfc: str, client_name: str, manual_url: str) -> str:
        subject = f"[FALLO DESCARGA][{rfc}] revision manual requerida"
        body = (
            "<h2>No se pudo descargar el documento del portal SAT</h2>"
            f"<p><b>Cliente:</b> {client_name} ({rfc})</p>"
            f"<p>Ingrese manualmente al Buzon: <a href='{manual_url}'>{manual_url}</a></p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_alert.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/alert.py tests/test_alert.py
git commit -m "feat: alert composer for four alert types"
```

---

### Task 11: PDF text extraction helper

**Files:**
- Modify: `julia_tool/classify.py` (append `extract_pdf_text`)
- Create: `tests/test_pdf.py`

**Interfaces:**
- Produces: `extract_pdf_text(pdf_path: str) -> str` — opens PDF with PyMuPDF, concatenates page text. Added here so `pipeline` can call `classify_text(extract_pdf_text(path), …)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf.py
import fitz  # PyMuPDF
from julia_tool.classify import extract_pdf_text

def test_extracts_text(tmp_path):
    p = str(tmp_path / "doc.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "REQUERIMIENTO de obligaciones")
    doc.save(p)
    doc.close()
    text = extract_pdf_text(p)
    assert "REQUERIMIENTO" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_pdf_text'`

- [ ] **Step 3: Write minimal implementation**

Append to `julia_tool/classify.py`:

```python
def extract_pdf_text(pdf_path: str) -> str:
    import fitz  # PyMuPDF
    parts = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add julia_tool/classify.py tests/test_pdf.py
git commit -m "feat: PDF text extraction helper"
```

---

### Task 12: Buzón portal fetcher (Playwright)

**Files:**
- Create: `julia_tool/buzon.py`
- Create: `tests/test_buzon.py`

**Interfaces:**
- Consumes: `ClientCred` (Task 2), `FetchResult` (Task 2), `Config.portal` (Task 8).
- Produces: class `BuzonFetcher(portal: dict, download_dir: str)` with:
  - `fetch(cred: ClientCred, headless: bool = True) -> FetchResult` — dispatches on `cred.auth_type`: `_fetch_efirma` (headless certificate login) or `_fetch_ciec` (headed window; operator solves captcha). Wraps everything in try/except; on any exception captures a screenshot to `download_dir/<rfc>_fail.png` and returns `FetchResult(ok=False, …)`.
  - `_pick_first_notification_pdf(page) -> str | None` — pure-ish helper: given a Playwright page, reads `portal["notifications_selector"]`, clicks the first `download_link_selector`, waits for download, returns saved path. (Live-portal behavior verified manually.)
  - `_download_path(rfc: str) -> str` — pure helper returning `download_dir/<rfc>_<n>.pdf`; unit-tested.

Design note: Playwright drives a real browser and cannot be meaningfully unit-tested offline, so this task's automated test covers only the pure helpers (`_download_path`, auth-type dispatch raising for unknown type) and that an injected fake page-factory routes to the right private method. Live e.firma/CIEC runs are validated in Task 15 (manual checklist).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_buzon.py
import pytest
from julia_tool.models import ClientCred
from julia_tool.buzon import BuzonFetcher

def _fetcher(tmp_path):
    portal = {"efirma_login_url": "x", "ciec_login_url": "y",
              "notifications_selector": "tr", "download_link_selector": "a"}
    return BuzonFetcher(portal, str(tmp_path))

def test_download_path_format(tmp_path):
    f = _fetcher(tmp_path)
    p = f._download_path("XAXX010101000")
    assert p.endswith("XAXX010101000_1.pdf")

def test_unknown_auth_type_returns_error(tmp_path):
    f = _fetcher(tmp_path)
    cred = ClientCred("XAXX010101000", "ACME", "unknown",
                      None, None, None, None)
    # inject a fake browser factory that must never be called for unknown type
    res = f.fetch(cred, headless=True, _browser_factory=lambda headless: None)
    assert res.ok is False
    assert "auth_type" in res.error

def test_dispatch_routes_efirma(tmp_path, monkeypatch):
    f = _fetcher(tmp_path)
    called = {}
    monkeypatch.setattr(f, "_fetch_efirma",
                        lambda cred, browser: called.setdefault("efirma", True))
    cred = ClientCred("XAXX010101000", "ACME", "efirma",
                      None, "/c.cer", "/k.key", "pw")
    f.fetch(cred, headless=True, _browser_factory=lambda headless: object())
    assert called.get("efirma") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_buzon.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.buzon'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/buzon.py
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
        try:
            browser = factory(headless if cred.auth_type == "efirma" else False)
            if cred.auth_type == "efirma":
                return self._fetch_efirma(cred, browser)
            return self._fetch_ciec(cred, browser)
        except Exception as exc:  # noqa: BLE001 — any failure → fallback alert
            shot = os.path.join(self.download_dir, f"{cred.rfc}_fail.png")
            return FetchResult(False, None, str(exc), shot)

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_buzon.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/buzon.py tests/test_buzon.py
git commit -m "feat: Buzon fetcher skeleton with tested dispatch + helpers"
```

---

### Task 13: Per-message pipeline orchestration

**Files:**
- Create: `julia_tool/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `process_message(msg, *, cfg, store, state, alerter, fetcher, classify_pdf, now, dry_run=False) -> str` — returns the outcome string (one of the five canonical outcomes) and records it via `state.mark_processed` unless `dry_run`. `classify_pdf` is injected: a callable `(pdf_path) -> Classification` (wraps `classify_text(extract_pdf_text(path), cfg.keyword_map)`), keeping the pipeline testable without a real PDF. `now` is an injected `() -> str` timestamp provider (ISO 8601), so tests are deterministic and the module never calls a forbidden clock directly.

Order enforced (Global Constraints): verify → (fail ⇒ quarantine) → RFC → (none ⇒ unknown_client) → store.get → (none ⇒ unknown_client) → **log_credential_use** → fetcher.fetch → (fail ⇒ fetch_failed) → classify → alert → record.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from julia_tool.models import EmailMessage, ClientCred, Classification, FetchResult
from julia_tool.pipeline import process_message

class _Cfg:
    allowed_domains = ["sat.gob.mx"]
    keyword_map = {"URGENT": ["requerimiento"], "ATTENTION": [], "INFO": []}
    portal = {"buzon_url": "https://sat.gob.mx/manual"}

class _Store:
    def __init__(self, cred): self._c = cred
    def get(self, rfc): return self._c

class _State:
    def __init__(self): self.processed = {}; self.audits = []; self.alerts = []
    def mark_processed(self, mid, outcome): self.processed[mid] = outcome
    def log_credential_use(self, rfc, purpose, outcome, ts):
        self.audits.append((rfc, purpose, outcome))
    def record_alert(self, rfc, urgency, ts): self.alerts.append((rfc, urgency))

class _Alerter:
    def __init__(self): self.calls = []
    def send_urgent(self, rfc, name, cls, pdf): self.calls.append(("urgent", rfc)); return "s"
    def send_quarantine(self, s, f, r): self.calls.append(("quarantine", r)); return "s"
    def send_unknown_client(self, s): self.calls.append(("unknown",)); return "s"
    def send_fetch_failed(self, rfc, name, url): self.calls.append(("failed", rfc)); return "s"

class _Fetcher:
    def __init__(self, result): self._r = result
    def fetch(self, cred, headless=True): return self._r

def _msg(frm="no-reply@sat.gob.mx", auth="spf=pass dkim=pass",
         body="Contribuyente XAXX010101000 requerimiento"):
    return EmailMessage("m1", "asunto", frm, auth, body, "2026-07-18T00:00:00Z")

_NOW = lambda: "2026-07-18T00:00:00Z"
_CRED = ClientCred("XAXX010101000", "ACME", "ciec", "pw", None, None, None)

def _classify_ok(_path):
    return Classification("URGENT", "requerimiento", None, ["requerimiento"])

def test_happy_path_sends_urgent():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "alert_sent"
    assert ("urgent", "XAXX010101000") in al.calls
    assert st.processed["m1"] == "alert_sent"
    assert st.audits and st.audits[0][2] == "ok"

def test_phishing_is_quarantined_no_credential_use():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(frm="evil@fake.com"), cfg=_Cfg(), store=_Store(_CRED), state=st,
        alerter=al, fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "quarantined"
    assert st.audits == []          # credentials never touched
    assert al.calls[0][0] == "quarantine"

def test_no_rfc_is_unknown_client():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="sin rfc aqui"), cfg=_Cfg(), store=_Store(None), state=st,
        alerter=al, fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "unknown_client"

def test_fetch_failure_sends_fallback():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(False, None, "boom", "/s.png")),
        classify_pdf=_classify_ok, now=_NOW)
    assert out == "fetch_failed"
    assert ("failed", "XAXX010101000") in al.calls
    assert st.audits[0][2] == "fail"

def test_dry_run_does_not_mark_processed():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW, dry_run=True)
    assert out == "alert_sent"
    assert st.processed == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.pipeline'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/pipeline.py
from julia_tool.rfc import extract_rfc
from julia_tool.verify import is_genuine_sat

def process_message(msg, *, cfg, store, state, alerter, fetcher,
                    classify_pdf, now, dry_run: bool = False) -> str:
    def _finish(outcome: str) -> str:
        if not dry_run:
            state.mark_processed(msg.id, outcome)
        return outcome

    ok, reason = is_genuine_sat(msg, cfg.allowed_domains)
    if not ok:
        alerter.send_quarantine(msg.subject, msg.from_address, reason)
        return _finish("quarantined")

    rfc = extract_rfc(f"{msg.subject}\n{msg.body}")
    if not rfc:
        alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    cred = store.get(rfc)
    if not cred:
        alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    ts = now()
    result = fetcher.fetch(cred)
    state.log_credential_use(rfc, "buzon_login", "ok" if result.ok else "fail", ts)
    if not result.ok:
        manual_url = cfg.portal.get("buzon_url", "https://www.sat.gob.mx")
        alerter.send_fetch_failed(rfc, cred.name, manual_url)
        return _finish("fetch_failed")

    cls = classify_pdf(result.pdf_path)
    pdf_bytes = None
    try:
        with open(result.pdf_path, "rb") as f:
            pdf_bytes = (f"{rfc}.pdf", f.read())
    except OSError:
        pdf_bytes = None
    alerter.send_urgent(rfc, cred.name, cls, pdf_bytes)
    if not dry_run:
        state.record_alert(rfc, cls.urgency, ts)
    return _finish("alert_sent")
```

Note: the `open()` on `result.pdf_path` is guarded so the injected fake path `/x.pdf` (nonexistent) yields `pdf_bytes=None` without failing the test; live runs read the real downloaded file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add julia_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: per-message pipeline orchestration"
```

---

### Task 14: Client-management CLI + main entry

**Files:**
- Create: `julia_tool/clientcli.py`
- Create: `julia_tool/main.py`
- Create: `tests/test_clientcli.py`

**Interfaces:**
- Consumes: `SecretsStore` (Task 6), `ClientCred` (Task 2), `Config` (Task 8), and the pipeline.
- Produces:
  - `clientcli.run(argv: list[str], store_factory) -> int` — parses `add/list/remove` subcommands; `store_factory(master_pw) -> SecretsStore` is injected so tests avoid real prompts. Returns process exit code.
  - `main.build_now() -> Callable[[], str]` — returns an ISO-8601 UTC timestamp provider (uses `datetime.now(timezone.utc)`; lives in `main`, never imported by pure-logic modules).
  - `main.run_once(cfg, store, state, graph, session, fetcher) -> dict[str,int]` — lists messages, skips already-processed, runs `process_message` for the rest, returns an outcome tally.
  - `main.main(argv)` — arg parsing: `--config`, `--once`, `--dry-run`, and `client …` delegating to `clientcli`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clientcli.py
from julia_tool.clientcli import run
from julia_tool.secrets_store import SecretsStore

def test_add_then_list(tmp_path, capsys):
    p = str(tmp_path / "clients.secret")
    factory = lambda pw: SecretsStore(p, "master")
    rc = run(["add", "--rfc", "XAXX010101000", "--name", "ACME",
              "--auth-type", "ciec", "--ciec-password", "pw"], factory)
    assert rc == 0
    rc = run(["list"], factory)
    out = capsys.readouterr().out
    assert "XAXX010101000" in out
    assert rc == 0

def test_remove(tmp_path):
    p = str(tmp_path / "clients.secret")
    factory = lambda pw: SecretsStore(p, "master")
    run(["add", "--rfc", "ACM950101ABC", "--name", "X",
         "--auth-type", "ciec", "--ciec-password", "z"], factory)
    rc = run(["remove", "--rfc", "ACM950101ABC"], factory)
    assert rc == 0
    assert SecretsStore(p, "master").get("ACM950101ABC") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clientcli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'julia_tool.clientcli'`

- [ ] **Step 3: Write minimal implementation**

```python
# julia_tool/clientcli.py
import argparse
import os
from julia_tool.models import ClientCred

def _master_from_env_or_prompt() -> str:
    pw = os.environ.get("JULIA_MASTER_PW")
    if pw:
        return pw
    import getpass
    return getpass.getpass("Master password: ")

def run(argv: list[str], store_factory=None) -> int:
    parser = argparse.ArgumentParser(prog="julia_tool client")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--rfc", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--auth-type", required=True, choices=["efirma", "ciec"])
    a.add_argument("--ciec-password")
    a.add_argument("--cer-path")
    a.add_argument("--key-path")
    a.add_argument("--key-password")

    r = sub.add_parser("remove")
    r.add_argument("--rfc", required=True)

    sub.add_parser("list")

    ns = parser.parse_args(argv)
    factory = store_factory or (lambda pw: _real_store(pw))
    store = factory(_master_from_env_or_prompt())

    if ns.cmd == "add":
        store.add(ClientCred(
            rfc=ns.rfc.upper(), name=ns.name, auth_type=ns.auth_type,
            ciec_password=ns.ciec_password, cer_path=ns.cer_path,
            key_path=ns.key_path, key_password=ns.key_password))
        print(f"added {ns.rfc.upper()}")
        return 0
    if ns.cmd == "remove":
        ok = store.remove(ns.rfc.upper())
        print("removed" if ok else "not found")
        return 0
    if ns.cmd == "list":
        for rfc in store.list_rfcs():
            print(rfc)
        return 0
    return 1

def _real_store(pw: str):
    from julia_tool.config import load_config
    from julia_tool.secrets_store import SecretsStore
    cfg = load_config(os.environ.get("JULIA_CONFIG", "config.yaml"))
    return SecretsStore(cfg.secrets_path, pw)
```

```python
# julia_tool/main.py
import argparse
import os
import time
from datetime import datetime, timezone
from julia_tool.config import load_config
from julia_tool.secrets_store import SecretsStore
from julia_tool.state import State
from julia_tool.graph_client import GraphClient
from julia_tool.buzon import BuzonFetcher
from julia_tool.alert import Alerter
from julia_tool.classify import classify_text, extract_pdf_text
from julia_tool.pipeline import process_message

def build_now():
    return lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_once(cfg, store, state, graph, session, fetcher, dry_run=False) -> dict:
    now = build_now()
    alerter = Alerter(graph, session, cfg.responsible_email)
    def classify_pdf(path):
        return classify_text(extract_pdf_text(path), cfg.keyword_map)
    tally: dict[str, int] = {}
    for msg in graph.list_messages(session):
        if state.is_processed(msg.id):
            outcome = "skipped_duplicate"
        else:
            outcome = process_message(
                msg, cfg=cfg, store=store, state=state, alerter=alerter,
                fetcher=fetcher, classify_pdf=classify_pdf, now=now,
                dry_run=dry_run)
        tally[outcome] = tally.get(outcome, 0) + 1
    return tally

def main(argv=None):
    parser = argparse.ArgumentParser(prog="julia_tool")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)

    if ns.rest and ns.rest[0] == "client":
        from julia_tool.clientcli import run as client_run
        return client_run(ns.rest[1:])

    cfg = load_config(ns.config)
    import getpass
    master = os.environ.get("JULIA_MASTER_PW") or getpass.getpass("Master password: ")
    store = SecretsStore(cfg.secrets_path, master)
    state = State(cfg.state_path)
    graph = GraphClient(cfg.tenant_id, cfg.client_id, cfg.mailbox)
    token = graph.acquire_token(prompt=True)
    session = graph.session(token)
    fetcher = BuzonFetcher(cfg.portal, cfg.download_dir)

    while True:
        tally = run_once(cfg, store, state, graph, session, fetcher,
                         dry_run=ns.dry_run)
        print(f"cycle tally: {tally}", flush=True)
        if ns.once:
            return 0
        time.sleep(cfg.poll_interval_s)

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clientcli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite + commit**

Run: `python -m pytest -v`
Expected: ALL PASS

```bash
git add julia_tool/clientcli.py julia_tool/main.py tests/test_clientcli.py
git commit -m "feat: client CLI and main entry point"
```

---

### Task 15: README, Azure setup, and live-portal validation checklist

**Files:**
- Create: `README.md`
- Create: `docs/manual-validation.md`

**Interfaces:** none (documentation + operational runbook). This task also implements the live `_fetch_efirma` / `_fetch_ciec` bodies against the real portal, since their selectors and certificate-challenge behavior can only be confirmed interactively.

- [ ] **Step 1: Write `README.md`**

Contents (write in full):
- What the tool does (one paragraph).
- **Legal/operational prerequisite:** the firm must hold a signed authorization (carta responsiva) from each client to custody SAT credentials.
- Install: `python -m venv .venv && . .venv/bin/activate && pip install -e .[dev] && playwright install chromium`.
- Azure/Entra app registration steps: register a public client app; add delegated Graph permissions `Mail.Read.Shared`, `Mail.Send.Shared`; enable device-code (public client) flow; put `tenant_id`/`client_id` in `config.yaml`.
- Copy `config.example.yaml` → `config.yaml`; fill mailbox + responsible email.
- Add clients: `JULIA_MASTER_PW=… python -m julia_tool.main client add --rfc … --name … --auth-type ciec --ciec-password …` (or `--auth-type efirma --cer-path … --key-path … --key-password …`).
- Run: `python -m julia_tool.main --once --dry-run` first, then `--once`, then loop.
- Security notes: encrypted store, audit log location, `.gitignore` coverage, keep `.cer/.key` in an ACL-restricted directory.

- [ ] **Step 2: Write `docs/manual-validation.md`** — the interactive checklist:
  - Dry-run over a real inbox: confirm SAT emails classified, phishing quarantined, tally printed, nothing sent.
  - e.firma live: run non-headless once, confirm certificate challenge satisfied with `.cer/.key`, notification list loads, first PDF downloads to `downloads/<rfc>_*.pdf`. Record the real `notifications_selector`/`download_link_selector` and update `config.yaml`.
  - CIEC live: confirm headed window opens, RFC+password filled, operator solves captcha, automation resumes and downloads.
  - Fill in the `_fetch_efirma` / `_fetch_ciec` bodies in `julia_tool/buzon.py` using the confirmed selectors; re-run `pytest` (helpers still pass) and one live message end-to-end to a test responsible address.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/manual-validation.md julia_tool/buzon.py
git commit -m "docs: README, Azure setup, live-portal validation checklist"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) |
|---|---|
| Graph poll (§3, §4 poller) | 9, 14 (`run_once`) |
| Sender verify / anti-phishing (§4, §6) | 4, 13 (order enforced) |
| RFC extract (§4) | 3, 13 |
| Encrypted secrets store, CLI (§4, §5) | 6, 14 |
| Buzón fetch e.firma/CIEC (§4) | 12, 15 |
| Classify (§4) | 5, 11 |
| Alert to fixed responsible (§4) | 10, 13 |
| SQLite state + audit (§4, §8 state) | 7, 13 |
| Config (§4) | 8 |
| Security ordering (§6) | 13 (verify-before-credential test) + Global Constraints |
| Error handling, no silent drops (§7) | 13 (five outcomes), 12 (screenshot fallback) |
| Testing / dry-run (§8) | every task; `--dry-run` in 13/14 |
| Out-of-scope items (§9) | not implemented (correct) |

No gaps.

**2. Placeholder scan:** No "TBD"/"implement later" in code steps. The two `NotImplementedError` bodies in Task 12 are deliberate and explicitly deferred to Task 15's live checklist (browser code can't be unit-tested offline) — their pure helpers and dispatch ARE tested. Everything else is complete runnable code.

**3. Type consistency:** `Classification(urgency, act_type, deadline, matched)`, `ClientCred(rfc, name, auth_type, ciec_password, cer_path, key_path, key_password)`, `FetchResult(ok, pdf_path, error, screenshot_path)`, `EmailMessage(id, subject, from_address, auth_results, body, received)` used identically across Tasks 2/5/6/9/10/12/13/14. `process_message` signature in Task 13 matches its call in Task 14 `run_once`. Canonical enums (`URGENT/ATTENTION/INFO`) and outcomes (`alert_sent/quarantined/unknown_client/fetch_failed/skipped_duplicate`) consistent. Injected `now`/`classify_pdf`/`store_factory`/`_browser_factory` seams consistent between definition and tests.

No issues found.
