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
