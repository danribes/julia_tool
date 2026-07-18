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


def test_spoofed_from_with_attacker_alignment_blocked():
    # Forged From: sat.gob.mx, but SPF/DKIM pass belong to attacker.com.
    ok, reason = is_genuine_sat(
        _msg("notificaciones@sat.gob.mx",
             "spf=pass smtp.mailfrom=attacker.com; dkim=pass header.d=attacker.com"),
        ALLOW)
    assert ok is False and reason == "spf"


def test_aligned_spf_dkim_accepts():
    ok, reason = is_genuine_sat(
        _msg("x@sat.gob.mx",
             "spf=pass smtp.mailfrom=sat.gob.mx; dkim=pass header.d=sat.gob.mx"),
        ALLOW)
    assert ok is True and reason == "ok"


def test_dmarc_pass_accepts():
    ok, reason = is_genuine_sat(
        _msg("x@sat.gob.mx",
             "spf=pass smtp.mailfrom=sat.gob.mx; dkim=pass header.d=sat.gob.mx; "
             "dmarc=pass action=none header.from=sat.gob.mx"),
        ALLOW)
    assert ok is True and reason == "ok"


def test_dmarc_fail_blocks():
    ok, reason = is_genuine_sat(
        _msg("x@sat.gob.mx", "spf=pass dkim=pass; dmarc=fail"), ALLOW)
    assert ok is False and reason == "dmarc"


def test_reverse_multi_at_rejected():
    # Malformed address whose rightmost @-segment is an allowed domain.
    ok, reason = is_genuine_sat(
        _msg("a@evil.com@sat.gob.mx", "spf=pass dkim=pass"), ALLOW)
    assert ok is False and reason == "domain"


def test_no_at_rejected():
    ok, reason = is_genuine_sat(_msg("sat.gob.mx", "spf=pass dkim=pass"), ALLOW)
    assert ok is False and reason == "domain"


def test_case_insensitive_domain():
    ok, reason = is_genuine_sat(
        _msg("X@SAT.GOB.MX", "SPF=PASS DKIM=PASS"), ALLOW)
    assert ok is True and reason == "ok"


def test_empty_allowlist_fails_closed():
    ok, reason = is_genuine_sat(_msg("x@sat.gob.mx", "spf=pass dkim=pass"), [])
    assert ok is False and reason == "domain"
