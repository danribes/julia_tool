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
