# Alert-words gate + web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** A local Flask web UI (localhost) with two inputs — alert words (comma-separated) and recipient email — persisted to `ui_settings.json`; the watcher reads it each cycle and forwards a genuine SAT notification to the recipient only if an alert word matches (empty list → forward all). Bilingual UI. New outcome `not_forwarded`.

**Architecture:** Pure matching (`alert_words.py`) + settings persistence (`settings.py`) feed a pipeline gate on the successful-forward path and a Flask settings page (`webui.py`). Language via the existing i18n catalog.

**Tech Stack:** Python 3.12, Flask (new dep), stdlib json/unicodedata/secrets. Tests: pytest in the project venv (Flask already installed).

## Global Constraints

- Run tests with `/home/dan/projects/julia_tool/.venv/bin/python -m pytest`.
- Flask binds `127.0.0.1` ONLY — never `0.0.0.0`.
- The gate applies ONLY to the successful notification-forward path (`send_urgent`). Quarantine / unknown-client / fetch-failed alerts are NEVER gated.
- Empty alert-words list → `should_forward` returns True → forward all (backward compatible).
- Matching is accent- AND case-insensitive.
- Keep the existing alert HTML-escaping and the dry-run side-effect-free guarantee.
- Recipient precedence: `--responsible` flag > `ui_settings.json` responsible_email (if non-empty) > `config.yaml` responsible_email.
- `ui_settings.json` written mode 0600; never committed (gitignored).
- Branch: `build-alertwords-ui`. Commit after each task.

---

### Task 1: `alert_words.py` — pure matching

**Files:** Create `julia_tool/alert_words.py`, `tests/test_alert_words.py`.

**Produces:** `parse_words(raw) -> list[str]`, `normalize(s) -> str`, `should_forward(text, words) -> bool`.

- [ ] **Step 1: failing test** — `tests/test_alert_words.py`:

```python
from julia_tool.alert_words import parse_words, normalize, should_forward

def test_parse_words_splits_trims_dedupes():
    assert parse_words("multa,  sanción ,multa,, requerimiento ") == \
        ["multa", "sanción", "requerimiento"]
    assert parse_words("") == []
    assert parse_words("   ") == []

def test_normalize_strips_accents_and_case():
    assert normalize("Sanción") == normalize("sancion")
    assert normalize("REQUERIMIENTO") == "requerimiento"

def test_should_forward_empty_words_forwards_all():
    assert should_forward("cualquier texto", []) is True

def test_should_forward_matches_accent_insensitive():
    assert should_forward("Se emite una SANCIÓN", ["sancion"]) is True
    assert should_forward("aviso informativo", ["sancion"]) is False

def test_should_forward_substring_match():
    assert should_forward("acuse de requerimiento fiscal", ["requerimiento"]) is True
```

- [ ] **Step 2: run, expect fail** (ModuleNotFoundError).
- [ ] **Step 3: implement** — `julia_tool/alert_words.py`:

```python
import unicodedata


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def parse_words(raw: str) -> list[str]:
    seen = set()
    out = []
    for part in raw.split(","):
        w = part.strip()
        if not w:
            continue
        key = w.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def should_forward(text: str, words: list[str]) -> bool:
    if not words:
        return True
    haystack = normalize(text)
    return any(normalize(w) in haystack for w in words)
```

- [ ] **Step 4: run, expect 5 passed.**
- [ ] **Step 5: commit** — `feat(alert_words): comma-word parse + accent-insensitive forward gate`

---

### Task 2: `settings.py` — UI settings persistence

**Files:** Create `julia_tool/settings.py`, `tests/test_settings.py`.

**Produces:** `DEFAULTS`, `load_settings(path) -> dict`, `save_settings(path, data) -> None`, `valid_email(s) -> bool`.

- [ ] **Step 1: failing test** — `tests/test_settings.py`:

```python
import os
import stat
from julia_tool.settings import load_settings, save_settings, valid_email, DEFAULTS

def test_load_missing_returns_defaults(tmp_path):
    s = load_settings(str(tmp_path / "nope.json"))
    assert s == DEFAULTS
    assert s is not DEFAULTS  # a copy, not the shared default

def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, {"alert_words": ["multa"], "responsible_email": "a@b.mx"})
    s = load_settings(p)
    assert s["alert_words"] == ["multa"]
    assert s["responsible_email"] == "a@b.mx"

def test_save_ignores_unknown_keys(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, {"alert_words": [], "responsible_email": "", "evil": "x"})
    assert "evil" not in load_settings(p)

def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    with open(p, "w") as f:
        f.write("{not json")
    assert load_settings(p) == DEFAULTS

def test_save_file_permissions_owner_only(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    save_settings(p, dict(DEFAULTS))
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600

def test_valid_email():
    assert valid_email("jefe@despacho.mx") is True
    assert valid_email("bad") is False
    assert valid_email("") is False
    assert valid_email("a@b") is False
```

- [ ] **Step 2: run, expect fail.**
- [ ] **Step 3: implement** — `julia_tool/settings.py`:

```python
import json
import os
import re
import tempfile

DEFAULTS = {"alert_words": [], "responsible_email": ""}
_KEYS = tuple(DEFAULTS.keys())
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s or ""))


def load_settings(path: str) -> dict:
    result = {"alert_words": list(DEFAULTS["alert_words"]),
              "responsible_email": DEFAULTS["responsible_email"]}
    if not path or not os.path.exists(path):
        return result
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return result
    if not isinstance(raw, dict):
        return result
    words = raw.get("alert_words")
    if isinstance(words, list):
        result["alert_words"] = [str(w) for w in words]
    email = raw.get("responsible_email")
    if isinstance(email, str):
        result["responsible_email"] = email
    return result


def save_settings(path: str, data: dict) -> None:
    clean = {k: data.get(k, DEFAULTS[k]) for k in _KEYS}
    dirname = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirname, prefix=".ui-settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except BaseException:
        os.unlink(tmp)
        raise
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
```

- [ ] **Step 4: run, expect 6 passed.**
- [ ] **Step 5: commit** — `feat(settings): ui_settings.json persistence (alert words + recipient)`

---

### Task 3: Config `settings_path`

**Files:** Modify `julia_tool/config.py`, `config.example.yaml`, `tests/test_config.py`.

- [ ] **Step 1: append failing test** to `tests/test_config.py`:

```python
def test_settings_path_default(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    assert load_config(str(p)).settings_path == "ui_settings.json"
```

- [ ] **Step 2: run, expect fail** (AttributeError).
- [ ] **Step 3: implement:**
  - In the `Config` dataclass, add after `download_dir`: `settings_path: str = "ui_settings.json"`.
  - In `load_config`'s `return Config(...)`, add: `settings_path=raw.get("settings_path", "ui_settings.json"),`.
  - In `config.example.yaml`, add: `settings_path: ui_settings.json   # web-UI settings (alert words + recipient)`.

- [ ] **Step 4: run, expect pass.**
- [ ] **Step 5: commit** — `feat(config): settings_path for web-UI settings`

---

### Task 4: i18n UI keys

**Files:** Modify `julia_tool/i18n.py`; `tests/test_i18n.py` parity test already covers new keys.

- [ ] **Step 1: failing test** — append to `tests/test_i18n.py`:

```python
def test_ui_keys_present_both_langs():
    for lang in ("es", "en"):
        for key in ("ui.title", "ui.alert_words.label", "ui.recipient.label",
                    "ui.save", "ui.saved", "ui.invalid_email", "ui.current",
                    "ui.empty_note", "ui.lang_toggle", "ui.alert_words.help",
                    "ui.recipient.help"):
            assert key in MESSAGES[lang]
```

- [ ] **Step 2: run, expect fail** (KeyError / assertion).
- [ ] **Step 3: implement** — add these entries to BOTH `MESSAGES["es"]` and `MESSAGES["en"]` in `julia_tool/i18n.py` (keeping key sets identical):

es:
```python
        "ui.title": "Configuración de alertas — julia_tool",
        "ui.alert_words.label": "Palabras de alerta (separadas por comas)",
        "ui.alert_words.help": "El aviso del SAT se reenvía al responsable solo si aparece alguna de estas palabras. Vacío = reenviar todo.",
        "ui.recipient.label": "Correo del responsable de alertas",
        "ui.recipient.help": "Dirección que recibe los correos de alerta. Vacío = usar el de config.yaml.",
        "ui.save": "Guardar",
        "ui.saved": "Cambios guardados.",
        "ui.invalid_email": "Correo inválido; no se guardó el destinatario.",
        "ui.current": "Valores actuales",
        "ui.empty_note": "(sin palabras: se reenvía todo)",
        "ui.lang_toggle": "English",
```

en:
```python
        "ui.title": "Alert settings — julia_tool",
        "ui.alert_words.label": "Alert words (comma-separated)",
        "ui.alert_words.help": "The SAT notice is forwarded to the responsible person only if one of these words appears. Empty = forward everything.",
        "ui.recipient.label": "Alert recipient email",
        "ui.recipient.help": "Address that receives the alert emails. Empty = use the one in config.yaml.",
        "ui.save": "Save",
        "ui.saved": "Changes saved.",
        "ui.invalid_email": "Invalid email; recipient not saved.",
        "ui.current": "Current values",
        "ui.empty_note": "(no words: everything is forwarded)",
        "ui.lang_toggle": "Español",
```

- [ ] **Step 4: run** `pytest tests/test_i18n.py`, expect pass (incl. the existing identical-keys test).
- [ ] **Step 5: commit** — `feat(i18n): web-UI message keys (es/en)`

---

### Task 5: Pipeline forward gate

**Files:** Modify `julia_tool/pipeline.py`; append to `tests/test_pipeline.py`.

**Consumes:** `should_forward` (Task 1). **Produces:** `process_message(..., alert_words=None, read_pdf_text=None)`; new outcome `"not_forwarded"`.

- [ ] **Step 1: append failing tests** to `tests/test_pipeline.py`:

```python
def _reader_ok(_path):
    return "cuerpo del documento con multa aplicada"

def test_forward_gate_match_sends():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["multa"], read_pdf_text=_reader_ok)
    assert out == "alert_sent"
    assert ("urgent", "XAXX010101000") in al.calls

def test_forward_gate_no_match_not_forwarded():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="texto sin terminos"), cfg=_Cfg(), store=_Store(_CRED),
        state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["embargo"], read_pdf_text=lambda p: "nada relevante")
    assert out == "not_forwarded"
    assert al.calls == []                 # no alert sent
    assert st.processed["m1"] == "not_forwarded"
    assert st.audits and st.audits[0][2] == "ok"   # fetch still audited

def test_forward_gate_empty_words_forwards():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(), cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=[], read_pdf_text=lambda p: "nada")
    assert out == "alert_sent"

def test_forward_gate_matches_on_email_when_doc_lacks_it():
    st = _State(); al = _Alerter()
    out = process_message(
        _msg(body="Contribuyente XAXX010101000 con embargo precautorio"),
        cfg=_Cfg(), store=_Store(_CRED), state=st, alerter=al,
        fetcher=_Fetcher(FetchResult(True, "/x.pdf", None, None)),
        classify_pdf=_classify_ok, now=_NOW,
        alert_words=["embargo"], read_pdf_text=lambda p: "documento sin la palabra")
    assert out == "alert_sent"
```

- [ ] **Step 2: run, expect fail** (`process_message` has no `alert_words`).
- [ ] **Step 3: implement** — edit `julia_tool/pipeline.py`:
  - Add import at top: `from julia_tool.alert_words import should_forward`.
  - Change the signature to:
    `def process_message(msg, *, cfg, store, state, alerter, fetcher, classify_pdf, now, dry_run: bool = False, alert_words=None, read_pdf_text=None) -> str:`
  - Replace the tail (from the `try: cls = classify_pdf(...)` block through the final `return _finish("alert_sent")`) with:

```python
    try:
        cls = classify_pdf(result.pdf_path)
    except Exception:  # noqa: BLE001 — a corrupt/unreadable PDF must not crash the loop
        alerter.send_fetch_failed(rfc, cred.name, manual_url)
        return _finish("fetch_failed")

    doc_text = ""
    if read_pdf_text is not None:
        try:
            doc_text = read_pdf_text(result.pdf_path)
        except Exception:  # noqa: BLE001 — gating text is best-effort
            doc_text = ""
    searchable = f"{msg.subject}\n{msg.body}\n{doc_text}"
    if not should_forward(searchable, alert_words or []):
        return _finish("not_forwarded")

    pdf_bytes = None
    try:
        with open(result.pdf_path, "rb") as f:
            pdf_bytes = (f"{rfc}.pdf", f.read())
    except OSError:
        pdf_bytes = None
    alerter.send_urgent(rfc, cred.name, cls, pdf_bytes)
    state.record_alert(rfc, cls.urgency, ts)
    return _finish("alert_sent")
```

  (The `dry_run` early-return, verify/rfc/cred/fetch branches are UNCHANGED.)

- [ ] **Step 4: run full `tests/test_pipeline.py`, expect all pass** (old + 4 new).
- [ ] **Step 5: commit** — `feat(pipeline): alert-word forward gate + not_forwarded outcome`

---

### Task 6: Flask web UI

**Files:** Create `julia_tool/webui.py`, `tests/test_webui.py`; modify `pyproject.toml` (add Flask).

**Consumes:** `settings` (Task 2), `alert_words.parse_words` (Task 1), `i18n` (Task 4).
**Produces:** `create_app(settings_path, lang="es") -> Flask`, `run_ui(settings_path, port=8770, lang="es")`.

- [ ] **Step 1: failing test** — `tests/test_webui.py`:

```python
import re
from julia_tool.webui import create_app
from julia_tool.settings import load_settings

def _client(tmp_path):
    p = str(tmp_path / "ui_settings.json")
    app = create_app(p, lang="es")
    app.config.update(TESTING=True)
    return app.test_client(), p

def _token(html):
    m = re.search(r'name="csrf" value="([^"]+)"', html)
    return m.group(1)

def test_get_renders_both_inputs(tmp_path):
    c, _ = _client(tmp_path)
    html = c.get("/").get_data(as_text=True)
    assert 'name="alert_words"' in html
    assert 'name="responsible_email"' in html
    assert "Palabras de alerta" in html   # es labels

def test_get_en_labels(tmp_path):
    c, _ = _client(tmp_path)
    html = c.get("/?lang=en").get_data(as_text=True)
    assert "Alert words" in html

def test_post_saves_words_and_recipient(tmp_path):
    c, p = _client(tmp_path)
    token = _token(c.get("/").get_data(as_text=True))
    r = c.post("/", data={"csrf": token, "alert_words": "multa, sanción",
                          "responsible_email": "jefe@despacho.mx"})
    assert r.status_code == 200
    s = load_settings(p)
    assert s["alert_words"] == ["multa", "sanción"]
    assert s["responsible_email"] == "jefe@despacho.mx"

def test_post_invalid_email_not_saved(tmp_path):
    c, p = _client(tmp_path)
    token = _token(c.get("/").get_data(as_text=True))
    r = c.post("/", data={"csrf": token, "alert_words": "multa",
                          "responsible_email": "bad"})
    body = r.get_data(as_text=True)
    assert "inválido" in body or "Invalid" in body
    s = load_settings(p)
    assert s["responsible_email"] == ""      # rejected
    assert s["alert_words"] == ["multa"]     # words still saved

def test_post_bad_csrf_rejected(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/", data={"csrf": "wrong", "alert_words": "x",
                          "responsible_email": ""})
    assert r.status_code == 400
```

- [ ] **Step 2: run, expect fail** (ModuleNotFoundError).
- [ ] **Step 3: implement** — `julia_tool/webui.py`:

```python
import html
import secrets
from flask import Flask, request, abort
from julia_tool.alert_words import parse_words
from julia_tool.i18n import t, resolve_lang
from julia_tool.settings import load_settings, save_settings, valid_email, DEFAULTS

_PAGE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem}}
 label{{display:block;font-weight:600;margin-top:1.2rem}}
 .help{{color:#555;font-size:.9rem;margin:.2rem 0 .4rem}}
 input[type=text]{{width:100%;padding:.5rem;font-size:1rem;box-sizing:border-box}}
 button{{margin-top:1.2rem;padding:.6rem 1.2rem;font-size:1rem;cursor:pointer}}
 .msg{{padding:.6rem;border-radius:4px;margin:1rem 0}}
 .ok{{background:#e6f4ea}} .err{{background:#fce8e6}}
 .cur{{background:#f3f3f3;padding:.8rem;border-radius:4px;margin-top:1.5rem}}
 .top{{text-align:right}}
</style></head><body>
<div class="top"><a href="?lang={other_lang}">{lang_toggle}</a></div>
<h1>{title}</h1>
{message}
<form method="post">
 <input type="hidden" name="csrf" value="{csrf}">
 <label>{aw_label}</label>
 <p class="help">{aw_help}</p>
 <input type="text" name="alert_words" value="{aw_value}">
 <label>{re_label}</label>
 <p class="help">{re_help}</p>
 <input type="text" name="responsible_email" value="{re_value}">
 <button type="submit">{save}</button>
</form>
<div class="cur"><b>{current}:</b><br>
 {aw_label}: {aw_current}<br>
 {re_label}: {re_current}
</div>
</body></html>"""


def create_app(settings_path: str, lang: str = "es") -> Flask:
    app = Flask(__name__)
    app.config["CSRF_TOKEN"] = secrets.token_urlsafe(32)
    app.config["SETTINGS_PATH"] = settings_path
    app.config["DEFAULT_LANG"] = resolve_lang(lang)

    def render(message_html: str = "") -> str:
        lg = resolve_lang(request.args.get("lang", app.config["DEFAULT_LANG"]))
        other = "en" if lg == "es" else "es"
        s = load_settings(app.config["SETTINGS_PATH"])
        words = s["alert_words"]
        aw_current = ", ".join(words) if words else t("ui.empty_note", lg)
        re_current = s["responsible_email"] or "—"
        return _PAGE.format(
            lang=lg,
            other_lang=other,
            lang_toggle=html.escape(t("ui.lang_toggle", lg)),
            title=html.escape(t("ui.title", lg)),
            message=message_html,
            csrf=app.config["CSRF_TOKEN"],
            aw_label=html.escape(t("ui.alert_words.label", lg)),
            aw_help=html.escape(t("ui.alert_words.help", lg)),
            aw_value=html.escape(", ".join(words), quote=True),
            re_label=html.escape(t("ui.recipient.label", lg)),
            re_help=html.escape(t("ui.recipient.help", lg)),
            re_value=html.escape(s["responsible_email"], quote=True),
            save=html.escape(t("ui.save", lg)),
            current=html.escape(t("ui.current", lg)),
            aw_current=html.escape(aw_current),
            re_current=html.escape(re_current),
        )

    @app.get("/")
    def index():
        return render()

    @app.post("/")
    def save():
        if request.form.get("csrf") != app.config["CSRF_TOKEN"]:
            abort(400)
        lg = resolve_lang(request.args.get("lang", app.config["DEFAULT_LANG"]))
        words = parse_words(request.form.get("alert_words", ""))
        email = (request.form.get("responsible_email", "") or "").strip()
        data = {"alert_words": words, "responsible_email": ""}
        msgs = []
        if email and not valid_email(email):
            msgs.append(f'<div class="msg err">{html.escape(t("ui.invalid_email", lg))}</div>')
        else:
            data["responsible_email"] = email
        save_settings(app.config["SETTINGS_PATH"], data)
        msgs.insert(0, f'<div class="msg ok">{html.escape(t("ui.saved", lg))}</div>')
        return render("".join(msgs))

    return app


def run_ui(settings_path: str, port: int = 8770, lang: str = "es") -> None:
    app = create_app(settings_path, lang=lang)
    app.run(host="127.0.0.1", port=port)
```

  Then in `pyproject.toml`, add `"flask>=3.0",` to the `dependencies` list.

- [ ] **Step 4: run** `pytest tests/test_webui.py`, expect 5 passed. Then full suite.
- [ ] **Step 5: commit** — `feat(webui): Flask settings page (alert words + recipient, bilingual, CSRF)`

---

### Task 7: Wire settings into run_once + `ui` command

**Files:** Modify `julia_tool/main.py`; append to `tests/test_main.py`.

**Consumes:** `settings` (Task 2), `webui.run_ui` (Task 6), pipeline gate (Task 5).

- [ ] **Step 1: append failing tests** to `tests/test_main.py`:

```python
def test_run_once_recipient_precedence_settings_over_config(tmp_path):
    from types import SimpleNamespace
    from julia_tool.main import run_once
    from julia_tool.settings import save_settings
    from julia_tool.models import EmailMessage

    sp = str(tmp_path / "ui_settings.json")
    save_settings(sp, {"alert_words": [], "responsible_email": "ui@x.mx"})
    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["to"] = to

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="cfg@x.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={},
                          settings_path=sp)
    run_once(cfg, None, _State(), _Graph(), None, None)
    assert captured["to"] == "ui@x.mx"   # settings beat config; flag not given

def test_run_once_flag_beats_settings(tmp_path):
    from types import SimpleNamespace
    from julia_tool.main import run_once
    from julia_tool.settings import save_settings
    from julia_tool.models import EmailMessage

    sp = str(tmp_path / "ui_settings.json")
    save_settings(sp, {"alert_words": [], "responsible_email": "ui@x.mx"})
    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["to"] = to

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="cfg@x.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={},
                          settings_path=sp)
    run_once(cfg, None, _State(), _Graph(), None, None, responsible="flag@x.mx")
    assert captured["to"] == "flag@x.mx"

def test_parser_accepts_port():
    from julia_tool.main import _build_parser
    ns = _build_parser().parse_args(["--port", "9001", "--once"])
    assert ns.port == 9001
```

- [ ] **Step 2: run, expect fail.**
- [ ] **Step 3: implement** — edit `julia_tool/main.py`:
  - Add imports: `from julia_tool.settings import load_settings, DEFAULTS`.
  - In `_build_parser`, add: `parser.add_argument("--port", type=int, default=8770, help="web UI port (ui mode)")`.
  - Replace the body of `run_once` between `now = build_now()` and the `def classify_pdf` line with:

```python
    settings_path = getattr(cfg, "settings_path", "") or ""
    settings = load_settings(settings_path) if settings_path else dict(DEFAULTS)
    settings_email = settings.get("responsible_email") or None
    if responsible is not None:
        resolved_responsible = responsible
    elif settings_email:
        resolved_responsible = settings_email
    else:
        resolved_responsible = cfg.responsible_email
    alert_words = settings.get("alert_words", [])
    alerter = Alerter(graph, session, resolved_responsible, lang=resolve_lang(lang))
```

  - In `run_once`, change the `process_message(...)` call to also pass:
    `alert_words=alert_words, read_pdf_text=extract_pdf_text`.
  - In `main`, add a `ui` branch BEFORE the `client` branch:

```python
    if ns.rest and ns.rest[0] == "ui":
        from julia_tool.webui import run_ui
        cfg = load_config(ns.config)
        lang = resolve_lang(ns.lang or cfg.language)
        run_ui(cfg.settings_path, port=ns.port, lang=lang)
        return 0
```

  (Everything else in `main` — client delegation, master-password prompt, the loop — unchanged. `extract_pdf_text` is already imported in main.py.)

- [ ] **Step 4: run full suite, expect all pass.**
- [ ] **Step 5: commit** — `feat(main): load ui settings each cycle, recipient precedence, ui command`

---

### Task 8: Docs, Dockerfile, gitignore

**Files:** Modify `README.md`, `README.es.md`, `Dockerfile`, `.gitignore`.

- [ ] **Step 1:** `.gitignore` — append `ui_settings.json`.
- [ ] **Step 2:** `Dockerfile` — add `EXPOSE 8770` (after the `USER appuser` line) and a header comment: running the UI = `docker run --rm -p 8770:8770 -e JULIA_MASTER_PW=… -v "$PWD/ui_settings.json:/app/ui_settings.json" julia_tool ui --port 8770` (note it binds 127.0.0.1 inside the container, so `-p` maps it out).
- [ ] **Step 3:** `README.md` — add a "Web UI" section: `python -m julia_tool.main ui --port 8770` opens a localhost page to set the alert words (comma-separated) and the recipient email; explain the forward gate (empty = forward all; a match forwards; no match → `not_forwarded`, logged but not sent), matching is accent/case-insensitive, recipient precedence (`--responsible` > UI > config), localhost-only. Add `not_forwarded` to any outcomes list.
- [ ] **Step 4:** `README.es.md` — the same section in Spanish.
- [ ] **Step 5:** Run `pytest -q` (docs-only; suite green). Commit — `docs: web UI + forward gate (README es/en, Dockerfile, gitignore)`.

---

## Self-Review

**Spec coverage:** alert_words (T1) ✓; settings persistence + valid_email + 0600 (T2) ✓; config settings_path (T3) ✓; i18n UI keys (T4) ✓; pipeline gate + not_forwarded, gate only on forward path (T5) ✓; Flask UI both inputs + CSRF + localhost + bilingual (T6) ✓; run_once settings-per-cycle + recipient precedence + ui command (T7) ✓; docs/Docker/gitignore (T8) ✓. Empty→forward-all, accent-insensitive, dry-run untouched all covered.

**Placeholder scan:** none — every step has concrete code or an exact edit.

**Type consistency:** `should_forward(text, words)`, `parse_words(raw)`, `normalize(s)` consistent T1↔T5↔T6. `load_settings/save_settings/valid_email/DEFAULTS` consistent T2↔T6↔T7. `process_message(..., alert_words=None, read_pdf_text=None)` matches T5 impl and T7 call. `create_app(settings_path, lang)` / `run_ui(settings_path, port, lang)` match T6 impl and T7 call. Recipient precedence identical in spec §6 and T7 code.

**Backward-compat:** existing pipeline tests omit alert_words/read_pdf_text → default []/None → forward all; existing run_once tests use cfg without settings_path → `getattr(..,"")` → DEFAULTS → forward all, recipient falls to config. No existing test breaks.

**Security:** Flask host pinned 127.0.0.1 in `run_ui`; CSRF token checked on POST; recipient validated; settings file 0600; all rendered values `html.escape`d; UI never touches the secrets store.
