import pytest


@pytest.fixture(autouse=True)
def _no_interactive_master_password(monkeypatch):
    """Prevent clientcli/main from blocking on getpass() during the test
    session. clientcli.run() always resolves a master password via
    JULIA_MASTER_PW-or-prompt before invoking the injected store_factory,
    even when the factory itself ignores the value (as the clientcli tests
    do). Without this, getpass() falls back to reading pytest's captured
    stdin and raises OSError instead of hanging, which is still a spurious
    failure for tests that never intend to exercise the prompt path.
    """
    monkeypatch.setenv("JULIA_MASTER_PW", "test-master-pw")
