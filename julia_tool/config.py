from dataclasses import dataclass, field
import yaml
from julia_tool.classify import DEFAULT_KEYWORDS
from julia_tool.i18n import resolve_lang

_REQUIRED = ["tenant_id", "client_id", "mailbox", "responsible_email"]

@dataclass
class Config:
    tenant_id: str
    client_id: str
    mailbox: str
    responsible_email: str
    poll_interval_s: int = 300
    allowed_domains: list[str] = field(default_factory=lambda: ["sat.gob.mx"])
    portal: dict = field(default_factory=dict)
    keyword_map: dict[str, list[str]] = field(
        default_factory=lambda: DEFAULT_KEYWORDS)
    use_claude: bool = False
    secrets_path: str = "clients.secret"
    state_path: str = "state.sqlite"
    download_dir: str = "downloads"
    language: str = "es"

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    missing = [k for k in _REQUIRED if not raw.get(k)]
    if missing:
        raise ValueError(f"missing required config keys: {missing}")
    return Config(
        tenant_id=raw["tenant_id"],
        client_id=raw["client_id"],
        mailbox=raw["mailbox"],
        responsible_email=raw["responsible_email"],
        poll_interval_s=raw.get("poll_interval_s", 300),
        allowed_domains=raw.get("allowed_domains", ["sat.gob.mx"]),
        portal=raw.get("portal", {}),
        keyword_map=raw.get("keyword_map", DEFAULT_KEYWORDS),
        use_claude=raw.get("use_claude", False),
        secrets_path=raw.get("secrets_path", "clients.secret"),
        state_path=raw.get("state_path", "state.sqlite"),
        download_dir=raw.get("download_dir", "downloads"),
        language=resolve_lang(raw.get("language", "es")),
    )
