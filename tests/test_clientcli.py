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

def test_add_message_localized_en(tmp_path, capsys):
    from julia_tool.clientcli import run
    from julia_tool.secrets_store import SecretsStore
    p = str(tmp_path / "clients.secret")
    factory = lambda pw: SecretsStore(p, "master")
    run(["add", "--rfc", "XAXX010101000", "--name", "ACME",
         "--auth-type", "ciec", "--ciec-password", "pw"], factory, lang="en")
    assert "added XAXX010101000" in capsys.readouterr().out
