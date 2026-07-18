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
