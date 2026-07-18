import sqlite3


class State:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS processed (
                message_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc TEXT, purpose TEXT, outcome TEXT, ts TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc TEXT, urgency TEXT, ts TEXT
            );
            """
        )
        self._conn.commit()

    def is_processed(self, message_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM processed WHERE message_id=?", (message_id,))
        return cur.fetchone() is not None

    def mark_processed(self, message_id: str, outcome: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO processed(message_id, outcome) VALUES (?,?)",
            (message_id, outcome))
        self._conn.commit()

    def log_credential_use(self, rfc: str, purpose: str, outcome: str, ts: str) -> None:
        self._conn.execute(
            "INSERT INTO audit(rfc, purpose, outcome, ts) VALUES (?,?,?,?)",
            (rfc, purpose, outcome, ts))
        self._conn.commit()

    def record_alert(self, rfc: str, urgency: str, ts: str) -> None:
        self._conn.execute(
            "INSERT INTO alerts(rfc, urgency, ts) VALUES (?,?,?)",
            (rfc, urgency, ts))
        self._conn.commit()

    def audit_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
