# Bilingual (es/en) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** All user-facing output (alert emails, CLI/console, docs) available in Spanish or English via one language setting; default Spanish; no new dependency.

**Architecture:** A single in-repo message-catalog module (`i18n.py`) maps stable message ids to `es`/`en` templates. Language resolves once (config default → `--lang` override) and is passed to the `Alerter` and CLI/console emitters.

**Tech Stack:** Python 3.12 stdlib only (dict catalog + `str.format`). Tests via pytest in the project venv.

## Global Constraints

- Run tests with `/home/dan/projects/julia_tool/.venv/bin/python -m pytest`.
- Default language is `es`. `resolve_lang(x)` returns `"es"` or `"en"`; any invalid/None → `"es"` (never crash).
- Canonical enum values (`URGENT/ATTENTION/INFO`) and outcome strings are UNCHANGED in code and audit; only their DISPLAY is localized.
- Keep `html.escape` on every interpolated UNTRUSTED value in alert bodies (client_name, rfc, act_type, deadline, terms, from_address, reason, manual_url). Static catalog text (labels, headings, notes) is our own trusted text — not escaped.
- Classifier keywords are NOT translated (they match Spanish SAT documents).
- Commit after each task. TDD: failing test → minimal code → passing test → commit.
- Branch: work on `build-bilingual` (created before Task 1). Do NOT commit to master directly.

---

### Task 1: i18n message-catalog module

**Files:** Create `julia_tool/i18n.py`, `tests/test_i18n.py`.

**Produces:**
- `DEFAULT_LANG = "es"`.
- `resolve_lang(value) -> str` — trims/lowercases; returns "es"/"en"; else/None → "es".
- `t(key, lang="es", **kwargs) -> str` — formats `MESSAGES[resolve_lang(lang)][key]`; unknown key raises `KeyError`.
- `urgency_label(urgency, lang="es") -> str` — localizes URGENT/ATTENTION/INFO; unknown passes through.
- `MESSAGES`, `URGENCY_LABELS` dicts with identical key sets across `es`/`en`.

- [ ] **Step 1: failing test** — `tests/test_i18n.py`:

```python
from julia_tool.i18n import t, resolve_lang, urgency_label, MESSAGES, URGENCY_LABELS

def test_resolve_lang_normalizes_and_defaults():
    assert resolve_lang("EN") == "en"
    assert resolve_lang(" es ") == "es"
    assert resolve_lang(None) == "es"
    assert resolve_lang("fr") == "es"

def test_t_formats_placeholders():
    assert t("cli.added", "en", rfc="XAXX") == "added XAXX"
    assert t("cli.added", "es", rfc="XAXX") == "agregado XAXX"

def test_t_unknown_key_raises():
    import pytest
    with pytest.raises(KeyError):
        t("nope.nope", "es")

def test_urgency_label_localized():
    assert urgency_label("URGENT", "es") == "URGENTE"
    assert urgency_label("URGENT", "en") == "URGENT"
    assert urgency_label("WEIRD", "es") == "WEIRD"

def test_catalogs_have_identical_keys():
    assert set(MESSAGES["es"]) == set(MESSAGES["en"])
    assert set(URGENCY_LABELS["es"]) == set(URGENCY_LABELS["en"])
```

- [ ] **Step 2: run, expect fail** (`ModuleNotFoundError: julia_tool.i18n`).
- [ ] **Step 3: implement** — `julia_tool/i18n.py`:

```python
DEFAULT_LANG = "es"
_LANGS = ("es", "en")

URGENCY_LABELS = {
    "es": {"URGENT": "URGENTE", "ATTENTION": "ATENCIÓN", "INFO": "INFO"},
    "en": {"URGENT": "URGENT", "ATTENTION": "ATTENTION", "INFO": "INFO"},
}

MESSAGES = {
    "es": {
        "alert.urgent.subject": "[{urgency}][{rfc}] {act_type}",
        "alert.urgent.heading": "Notificación SAT — {urgency}",
        "alert.quarantine.subject": "[CUARENTENA] correo sospechoso: {subject}",
        "alert.quarantine.heading": "Correo bloqueado por verificación anti-phishing",
        "alert.quarantine.reason": "Motivo: fallo de verificación '{reason}'",
        "alert.quarantine.note": "No se accedió a ninguna credencial. Revise manualmente.",
        "alert.unknown.subject": "[SIN CLIENTE] notificación sin RFC reconocido: {subject}",
        "alert.unknown.heading": "Notificación SAT sin cliente identificado",
        "alert.unknown.body": "No se encontró un RFC registrado en el correo. Revise manualmente.",
        "alert.fetch_failed.subject": "[FALLO DESCARGA][{rfc}] revisión manual requerida",
        "alert.fetch_failed.heading": "No se pudo descargar el documento del portal SAT",
        "alert.fetch_failed.link": "Ingrese manualmente al Buzón",
        "label.client": "Cliente",
        "label.act_type": "Tipo de acto",
        "label.deadline": "Plazo",
        "label.terms": "Términos detectados",
        "label.sender": "Remitente",
        "value.deadline_none": "no detectado",
        "prompt.master_password": "Contraseña maestra: ",
        "cli.added": "agregado {rfc}",
        "cli.removed": "eliminado",
        "cli.not_found": "no encontrado",
        "console.cycle_tally": "conteo del ciclo: {tally}",
    },
    "en": {
        "alert.urgent.subject": "[{urgency}][{rfc}] {act_type}",
        "alert.urgent.heading": "SAT notification — {urgency}",
        "alert.quarantine.subject": "[QUARANTINE] suspicious email: {subject}",
        "alert.quarantine.heading": "Email blocked by anti-phishing verification",
        "alert.quarantine.reason": "Reason: verification failure '{reason}'",
        "alert.quarantine.note": "No credentials were accessed. Review manually.",
        "alert.unknown.subject": "[NO CLIENT] notification with no recognized RFC: {subject}",
        "alert.unknown.heading": "SAT notification with no identified client",
        "alert.unknown.body": "No registered RFC was found in the email. Review manually.",
        "alert.fetch_failed.subject": "[DOWNLOAD FAILED][{rfc}] manual review required",
        "alert.fetch_failed.heading": "Could not download the document from the SAT portal",
        "alert.fetch_failed.link": "Log in manually to the Buzón",
        "label.client": "Client",
        "label.act_type": "Act type",
        "label.deadline": "Deadline",
        "label.terms": "Detected terms",
        "label.sender": "Sender",
        "value.deadline_none": "not detected",
        "prompt.master_password": "Master password: ",
        "cli.added": "added {rfc}",
        "cli.removed": "removed",
        "cli.not_found": "not found",
        "console.cycle_tally": "cycle tally: {tally}",
    },
}


def resolve_lang(value) -> str:
    if value is None:
        return DEFAULT_LANG
    v = str(value).strip().lower()
    return v if v in _LANGS else DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    template = MESSAGES[resolve_lang(lang)][key]
    return template.format(**kwargs) if kwargs else template


def urgency_label(urgency: str, lang: str = DEFAULT_LANG) -> str:
    return URGENCY_LABELS[resolve_lang(lang)].get(urgency, urgency)
```

- [ ] **Step 4: run, expect 5 passed.**
- [ ] **Step 5: commit** — `feat(i18n): message catalog for es/en`

---

### Task 2: Config language setting

**Files:** Modify `julia_tool/config.py`, `config.example.yaml`, `tests/test_config.py`.

**Consumes:** `resolve_lang` (Task 1). **Produces:** `Config.language: str` (always "es"/"en").

- [ ] **Step 1: append failing tests** to `tests/test_config.py`:

```python
def test_language_defaults_to_es(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    assert load_config(str(p)).language == "es"

def test_language_invalid_falls_back_to_es(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN + "language: fr\n")
    assert load_config(str(p)).language == "es"

def test_language_en_respected(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN + "language: EN\n")
    assert load_config(str(p)).language == "en"
```

- [ ] **Step 2: run, expect fail** (`AttributeError: 'Config' object has no attribute 'language'`).
- [ ] **Step 3: implement** — in `julia_tool/config.py`:
  - Add import: `from julia_tool.i18n import resolve_lang` (below the yaml import).
  - Add field to the `Config` dataclass (after `download_dir`): `language: str = "es"`.
  - In `load_config`'s `return Config(...)`, add: `language=resolve_lang(raw.get("language", "es")),`.
  - In `config.example.yaml`, add a line near the top: `language: es   # es | en — UI/alert language (default es)`.

- [ ] **Step 4: run, expect pass** (all config tests).
- [ ] **Step 5: commit** — `feat(config): language setting (es default)`

---

### Task 3: Localize alert emails

**Files:** Replace `julia_tool/alert.py`; update `tests/test_alert.py`.

**Consumes:** `t`, `urgency_label` (Task 1). **Produces:** `Alerter(graph, session, responsible_email, lang="es")` emitting localized subjects/bodies; escaping unchanged.

- [ ] **Step 1: update tests** — replace `tests/test_alert.py` with:

```python
from julia_tool.alert import Alerter
from julia_tool.models import Classification

class _FakeGraph:
    def __init__(self): self.sent = []
    def send_mail(self, session, to, subject, html_body, attachments):
        self.sent.append((to, subject, html_body, attachments))

def _alerter(lang="es"):
    return Alerter(_FakeGraph(), session=None, responsible_email="boss@firm.mx", lang=lang)

def test_urgent_subject_es_localizes_urgency_tag():
    a = _alerter("es")
    cls = Classification("URGENT", "requerimiento", "2026-08-01", ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, ("doc.pdf", b"%PDF-1.4"))
    assert subj == "[URGENTE][XAXX010101000] requerimiento"
    to, sent_subj, body, att = a.graph.sent[0]
    assert to == "boss@firm.mx"
    assert att and att[0][0] == "doc.pdf"
    assert "ACME" in body
    assert "Cliente" in body and "Tipo de acto" in body

def test_urgent_subject_en_localizes():
    a = _alerter("en")
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    subj = a.send_urgent("XAXX010101000", "ACME", cls, None)
    assert subj == "[URGENT][XAXX010101000] requerimiento"
    body = a.graph.sent[0][2]
    assert "Client" in body and "Act type" in body and "not detected" in body

def test_quarantine_es_and_en():
    es = _alerter("es"); es.send_quarantine("Falso SAT", "e@evil.com", "domain")
    assert "CUARENTENA" in es.graph.sent[0][1]
    assert es.graph.sent[0][3] is None
    en = _alerter("en"); en.send_quarantine("Fake SAT", "e@evil.com", "domain")
    assert "QUARANTINE" in en.graph.sent[0][1]

def test_unknown_client_en():
    a = _alerter("en"); subj = a.send_unknown_client("hola")
    assert "NO CLIENT" in subj
    assert "no identified client" in a.graph.sent[0][2]

def test_fetch_failed_includes_url_both_langs():
    a = _alerter("es"); a.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    assert "https://sat.gob.mx/manual" in a.graph.sent[0][2]
    b = _alerter("en"); b.send_fetch_failed("XAXX010101000", "ACME", "https://sat.gob.mx/manual")
    assert "manual review required" in b.graph.sent[0][1]

def test_quarantine_escapes_from_address():
    a = _alerter()
    a.send_quarantine("subj", "<img src=x onerror=alert(1)>@evil.com", "domain")
    body = a.graph.sent[0][2]
    assert "<img" not in body
    assert "&lt;img" in body

def test_urgent_escapes_client_name():
    a = _alerter()
    cls = Classification("URGENT", "requerimiento", None, ["requerimiento"])
    a.send_urgent("XAXX010101000", "<b>Evil</b>", cls, None)
    body = a.graph.sent[0][2]
    assert "<b>Evil</b>" not in body
    assert "&lt;b&gt;Evil" in body
```

- [ ] **Step 2: run, expect fail** (old Alerter has no `lang`; subject not localized).
- [ ] **Step 3: implement** — replace `julia_tool/alert.py` with:

```python
import html
from julia_tool.i18n import t, urgency_label
from julia_tool.models import Classification


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


class Alerter:
    def __init__(self, graph, session, responsible_email: str, lang: str = "es"):
        self.graph = graph
        self.session = session
        self.to = responsible_email
        self.lang = lang

    def send_urgent(self, rfc: str, client_name: str, cls: Classification,
                    pdf: tuple[str, bytes] | None) -> str:
        lang = self.lang
        ulabel = urgency_label(cls.urgency, lang)
        subject = t("alert.urgent.subject", lang,
                    urgency=ulabel, rfc=rfc, act_type=cls.act_type)
        deadline = cls.deadline or t("value.deadline_none", lang)
        terminos = ", ".join(cls.matched) or "—"
        body = (
            f"<h2>{t('alert.urgent.heading', lang, urgency=ulabel)}</h2>"
            f"<p><b>{t('label.client', lang)}:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f"<p><b>{t('label.act_type', lang)}:</b> {_esc(cls.act_type)}</p>"
            f"<p><b>{t('label.deadline', lang)}:</b> {_esc(deadline)}</p>"
            f"<p><b>{t('label.terms', lang)}:</b> {_esc(terminos)}</p>"
        )
        atts = [pdf] if pdf else None
        self.graph.send_mail(self.session, self.to, subject, body, atts)
        return subject

    def send_quarantine(self, msg_subject: str, from_address: str, reason: str) -> str:
        lang = self.lang
        subject = t("alert.quarantine.subject", lang, subject=msg_subject)
        body = (
            f"<h2>{t('alert.quarantine.heading', lang)}</h2>"
            f"<p><b>{t('label.sender', lang)}:</b> {_esc(from_address)}</p>"
            f"<p>{t('alert.quarantine.reason', lang, reason=_esc(reason))}</p>"
            f"<p>{t('alert.quarantine.note', lang)}</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_unknown_client(self, msg_subject: str) -> str:
        lang = self.lang
        subject = t("alert.unknown.subject", lang, subject=msg_subject)
        body = (
            f"<h2>{t('alert.unknown.heading', lang)}</h2>"
            f"<p>{t('alert.unknown.body', lang)}</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_fetch_failed(self, rfc: str, client_name: str, manual_url: str) -> str:
        lang = self.lang
        subject = t("alert.fetch_failed.subject", lang, rfc=rfc)
        url = _esc(manual_url)
        body = (
            f"<h2>{t('alert.fetch_failed.heading', lang)}</h2>"
            f"<p><b>{t('label.client', lang)}:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f'<p>{t("alert.fetch_failed.link", lang)}: <a href="{url}">{url}</a></p>'
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject
```

- [ ] **Step 4: run, expect all test_alert tests pass.**
- [ ] **Step 5: commit** — `feat(alert): localize alert emails (es/en)`

---

### Task 4: Wire `--lang` through main, run_once, and clientcli

**Files:** Modify `julia_tool/main.py`, `julia_tool/clientcli.py`; update `tests/test_main.py`, `tests/test_clientcli.py`.

**Consumes:** `t`, `resolve_lang` (Task 1), `Alerter(lang=...)` (Task 3). **Produces:** `--lang es|en` flag; `run_once(..., lang="es")`; localized CLI/console strings.

- [ ] **Step 1: append failing tests.**

`tests/test_main.py`:
```python
def test_run_once_passes_lang_to_alerter():
    from types import SimpleNamespace
    from julia_tool.models import EmailMessage
    from julia_tool.main import run_once

    captured = {}

    class _Graph:
        def list_messages(self, session, top=25):
            return [EmailMessage("m1", "s", "evil@fake.com", "spf=pass dkim=pass",
                                 "b", "t")]
        def send_mail(self, session, to, subject, body, att):
            captured["subject"] = subject

    class _State:
        def is_processed(self, mid): return False
        def mark_processed(self, *a, **k): pass

    cfg = SimpleNamespace(responsible_email="boss@firm.mx", keyword_map={},
                          allowed_domains=["sat.gob.mx"], portal={})
    run_once(cfg, None, _State(), _Graph(), None, None, lang="en")
    assert "QUARANTINE" in captured["subject"]   # English alert emitted

def test_parser_accepts_lang():
    from julia_tool.main import _build_parser
    ns = _build_parser().parse_args(["--lang", "en", "--once"])
    assert ns.lang == "en"
```

`tests/test_clientcli.py`:
```python
def test_add_message_localized_en(tmp_path, capsys):
    from julia_tool.clientcli import run
    from julia_tool.secrets_store import SecretsStore
    p = str(tmp_path / "clients.secret")
    factory = lambda pw: SecretsStore(p, "master")
    run(["add", "--rfc", "XAXX010101000", "--name", "ACME",
         "--auth-type", "ciec", "--ciec-password", "pw"], factory, lang="en")
    assert "added XAXX010101000" in capsys.readouterr().out
```

- [ ] **Step 2: run, expect fail** (`run_once` has no `lang`; `_build_parser` has no `--lang`; `run` has no `lang`).
- [ ] **Step 3: implement.**

In `julia_tool/main.py`:
- Add import: `from julia_tool.i18n import t, resolve_lang`.
- `run_once` signature → add `lang="es"`; change the Alerter line to `alerter = Alerter(graph, session, resolved_responsible, lang=resolve_lang(lang))`.
- In `_build_parser`, add before the `rest` argument:
  `parser.add_argument("--lang", default=None, help="es | en — output language (default es / config)")`
- In `main`, for client delegation change to:
  `return client_run(ns.rest[1:], lang=resolve_lang(ns.lang))`
- After `cfg = load_config(ns.config)`, add: `lang = resolve_lang(ns.lang or cfg.language)`.
- Master-password prompt: replace `"Master password: "` with `t("prompt.master_password", lang)`.
- The `run_once(...)` call: add `lang=lang`.
- The tally print: replace `print(f"cycle tally: {tally}", flush=True)` with
  `print(t("console.cycle_tally", lang, tally=tally), flush=True)`.

In `julia_tool/clientcli.py`:
- Add import: `from julia_tool.i18n import t`.
- `_master_from_env_or_prompt` → add `lang="es"` param; replace the getpass string with `t("prompt.master_password", lang)`.
- `run(argv, store_factory=None)` → `run(argv, store_factory=None, lang="es")`.
- `store = factory(_master_from_env_or_prompt())` → `store = factory(_master_from_env_or_prompt(lang))`.
- `print(f"added {ns.rfc.upper()}")` → `print(t("cli.added", lang, rfc=ns.rfc.upper()))`.
- `print("removed" if ok else "not found")` → `print(t("cli.removed", lang) if ok else t("cli.not_found", lang))`.

- [ ] **Step 4: run full suite, expect all pass.**
- [ ] **Step 5: commit** — `feat(cli): --lang flag wiring and localized console/CLI`

---

### Task 5: Spanish README

**Files:** Create `README.es.md`; modify `README.md` (add a language link line at the very top).

- [ ] **Step 1:** At the very top of `README.md`, add a first line: `> 🌐 English | [Español](README.es.md)`.
- [ ] **Step 2:** Create `README.es.md` — a faithful Spanish translation of README.md, with its first line `> 🌐 [English](README.md) | Español`. Translate all prose and section headings; keep code blocks, commands, file paths, URLs, and flag names (`--once`, `--dry-run`, `--responsible`, `--lang`, `client add`) unchanged. Document `language: es|en` config and `--lang es|en`.
- [ ] **Step 3:** Run `/home/dan/projects/julia_tool/.venv/bin/python -m pytest -q` (docs-only; expect the suite still green).
- [ ] **Step 4: commit** — `docs: Spanish README (README.es.md) + language links`

---

## Self-Review

**Spec coverage:** i18n module (Task 1) ✓; config language (Task 2) ✓; alert localization + escaping preserved (Task 3) ✓; `--lang` + run_once + CLI/console (Task 4) ✓; docs (Task 5) ✓; classifier keywords untouched ✓; default es ✓; invalid→es ✓.

**Placeholder scan:** none — every step has concrete code or exact edit instructions.

**Type consistency:** `Alerter(graph, session, responsible_email, lang="es")` consistent in Task 3 impl, Task 3 tests, and Task 4 run_once call. `run_once(..., lang="es")` matches main's call. `resolve_lang`/`t`/`urgency_label` signatures consistent across tasks. `clientcli.run(argv, store_factory=None, lang="es")` matches main's `client_run(..., lang=...)` call and the Task 4 test.

**Escaping check:** untrusted values (client_name, rfc, act_type, deadline, terms, from_address, reason, manual_url) remain `_esc`-wrapped; only trusted catalog text is unescaped. The existing injection tests are retained in Task 3.
