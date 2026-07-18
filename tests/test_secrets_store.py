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

def test_file_permissions_owner_only(tmp_path):
    import os
    import stat
    p = str(tmp_path / "clients.secret")
    s = SecretsStore(p, "master-pw")
    s.add(_cred())
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600
