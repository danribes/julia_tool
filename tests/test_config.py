import pytest
from julia_tool.config import load_config

_MIN = """
tenant_id: t
client_id: c
mailbox: office@firm.mx
responsible_email: boss@firm.mx
"""

def test_loads_defaults(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(_MIN)
    cfg = load_config(str(p))
    assert cfg.poll_interval_s == 300
    assert cfg.use_claude is False
    assert "sat.gob.mx" in cfg.allowed_domains
    assert cfg.keyword_map["URGENT"]

def test_missing_required_raises(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("tenant_id: t\n")
    with pytest.raises(ValueError):
        load_config(str(p))
