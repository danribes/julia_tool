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
