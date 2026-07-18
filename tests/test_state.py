from julia_tool.state import State


def test_processed_idempotent(tmp_path):
    st = State(str(tmp_path / "state.sqlite"))
    assert st.is_processed("m1") is False
    st.mark_processed("m1", "alert_sent")
    assert st.is_processed("m1") is True


def test_reopen_persists(tmp_path):
    p = str(tmp_path / "state.sqlite")
    State(p).mark_processed("m2", "quarantined")
    assert State(p).is_processed("m2") is True


def test_audit_and_alert(tmp_path):
    st = State(str(tmp_path / "state.sqlite"))
    st.log_credential_use("XAXX010101000", "buzon_login", "ok", "2026-07-18T00:00:00Z")
    st.record_alert("XAXX010101000", "URGENT", "2026-07-18T00:00:01Z")
    assert st.audit_count() == 1
