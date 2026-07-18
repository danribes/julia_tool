# Bilingual (Spanish / English) — Design Spec

**Date:** 2026-07-18
**Project:** `julia_tool` (SAT Buzón Tributario watcher)
**Status:** Approved by user

## 1. Purpose

Make all user-facing output available in Spanish or English, selected by a single
language setting. The Mexican accountancy office keeps Spanish as the default; English is
opt-in. Adds no runtime dependency.

## 2. Decisions taken (user-confirmed)

| Question | Decision |
|---|---|
| Bilingual model | Language **switch** (one language at a time), not both-in-every-alert |
| Default language | Spanish (`es`) — preserves current behavior |
| Per-client language | **Skip (YAGNI)** — one global language; single fixed recipient |
| Surfaces translated | Alert emails, CLI/console messages, and README/docs |
| Classifier keywords | **Stay Spanish** — they match real Spanish SAT documents (matching input, not UI) |
| Tooling | Lightweight in-repo message catalog (dict), no gettext/`.po`, no new dependency |

## 3. Architecture

A single translation module holds message catalogs for `es` and `en`; every user-facing
string becomes a catalog lookup keyed by a stable id. The active language is resolved once
(config default → `--lang` override) and passed to the components that emit text.

```
config.language (default "es") ──┐
                                 ├─ resolve_lang() ─→ lang ─→ Alerter(lang)  (emails)
CLI --lang es|en  ───────────────┘                        └─→ console/CLI prints
```

## 4. Components

| File | Change |
|---|---|
| `julia_tool/i18n.py` (new) | `MESSAGES: dict[str, dict[str, str]]` = `{"es": {...}, "en": {...}}` keyed by message id (templates use `str.format` placeholders). `t(key, lang="es", **kwargs) -> str` looks up and formats; unknown key raises `KeyError` (catches typos in tests). `resolve_lang(value) -> str` lowercases/trims, returns `"es"` or `"en"`, anything else → default `"es"`. `DEFAULT_LANG = "es"`. `URGENCY_LABELS[lang][URGENT|ATTENTION|INFO]` maps the canonical urgency enum to a localized label for display. |
| `julia_tool/config.py` | `Config` gains `language: str = "es"`; loader reads `language`, passes through `resolve_lang` so an invalid value falls back to `es` (no crash). `config.example.yaml` documents `language: es`. |
| `julia_tool/alert.py` | `Alerter(graph, session, responsible_email, lang="es")`. Every subject, heading, and label sourced from `t(...)`; urgency shown via `URGENCY_LABELS`. `html.escape` on interpolated untrusted values is unchanged. `act_type` VALUE stays as the matched Spanish SAT term (data). |
| `julia_tool/main.py` | Add `--lang es|en` (default `None`). Resolve `lang = resolve_lang(ns.lang or cfg.language)`; thread into `run_once(..., lang=lang)` → `Alerter(..., lang=lang)`. Operator console strings (`cycle tally`, master-password prompt) via `t(...)`. |
| `julia_tool/run_once` | Gains `lang="es"` param; builds `Alerter(..., lang=lang)`. |
| `julia_tool/clientcli.py` | `run(argv, store_factory=None, lang="es")`; `added`/`removed`/`not found` and the master-password prompt via `t(...)`. main passes the resolved `--lang` through (client mode does not load config; `--lang` or default `es` governs). |
| `README.es.md` (new) | Spanish translation of README.md; both link to each other at the top. |

## 5. Catalog inventory (message ids)

Alerts: `alert.urgent.subject`, `alert.urgent.heading`, `alert.quarantine.subject`,
`alert.quarantine.heading`, `alert.quarantine.reason`, `alert.quarantine.note`,
`alert.unknown.subject`, `alert.unknown.heading`, `alert.unknown.body`,
`alert.fetch_failed.subject`, `alert.fetch_failed.heading`, `alert.fetch_failed.link`.
Labels: `label.client`, `label.act_type`, `label.deadline`, `label.terms`,
`label.sender`, `value.deadline_none`. (The `—` shown when no terms matched is a
language-neutral dash, left inline.)
Urgency: `URGENCY_LABELS` (es: URGENTE/ATENCIÓN/INFO; en: URGENT/ATTENTION/INFO).
CLI/console: `prompt.master_password`, `cli.added`, `cli.removed`, `cli.not_found`,
`console.cycle_tally`.

Every `es` key MUST have an `en` counterpart and vice-versa (enforced by a test).

## 6. Behavior & compatibility

- Default `es` reproduces today's wording (accents restored where they were dropped, e.g.
  "Notificación", "verificación").
- Canonical enum values (`URGENT/ATTENTION/INFO`) and outcome strings are unchanged in
  code and audit log; only their DISPLAY is localized.
- Subjects keep the `[TAG][RFC] …` shape; the tag word is localized.
- Invalid `language`/`--lang` value → falls back to `es`, never crashes.

## 7. Testing

- `test_i18n.py`: catalogs have identical key sets across `es`/`en`; `t` formats
  placeholders; `resolve_lang` normalizes and defaults; unknown key raises.
- `test_alert.py`: extend to assert an `en` Alerter emits English subject/body and an `es`
  Alerter emits Spanish; html-escaping tests still pass.
- `test_config.py`: `language` default `es`; invalid value falls back to `es`.
- `test_clientcli.py` / `test_main.py`: `--lang en` yields English CLI/console strings;
  default stays Spanish.

## 8. Out of scope

- Per-client language.
- Translating classifier keywords (they match Spanish SAT documents).
- Translating internal logs, audit rows, code comments, or the spec/plan docs.
- Any third-party i18n framework.
