import base64
import json
import os
from dataclasses import asdict
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from julia_tool.models import ClientCred

_MAGIC = b"JTS1"
_SALT_LEN = 16

def _derive_key(master_password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    raw = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)

class SecretsStore:
    def __init__(self, path: str, master_password: str):
        self.path = path
        self._pw = master_password
        if os.path.exists(path):
            with open(path, "rb") as f:
                blob = f.read()
            if blob[:4] != _MAGIC:
                raise ValueError("not a julia_tool secrets file")
            self._salt = blob[4:4 + _SALT_LEN]
            token = blob[4 + _SALT_LEN:]
            fernet = Fernet(_derive_key(master_password, self._salt))
            try:
                data = fernet.decrypt(token)
            except InvalidToken as exc:
                raise ValueError("bad master password") from exc
            self._db: dict[str, dict] = json.loads(data.decode("utf-8"))
        else:
            self._salt = os.urandom(_SALT_LEN)
            self._db = {}
            self._flush()

    def _flush(self) -> None:
        fernet = Fernet(_derive_key(self._pw, self._salt))
        token = fernet.encrypt(json.dumps(self._db).encode("utf-8"))
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(_MAGIC + self._salt + token)
        os.replace(tmp, self.path)

    def add(self, cred: ClientCred) -> None:
        self._db[cred.rfc] = asdict(cred)
        self._flush()

    def get(self, rfc: str) -> ClientCred | None:
        row = self._db.get(rfc)
        return ClientCred(**row) if row else None

    def list_rfcs(self) -> list[str]:
        return list(self._db.keys())

    def remove(self, rfc: str) -> bool:
        if rfc in self._db:
            del self._db[rfc]
            self._flush()
            return True
        return False
