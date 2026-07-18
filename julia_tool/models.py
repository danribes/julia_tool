from dataclasses import dataclass

@dataclass
class EmailMessage:
    id: str
    subject: str
    from_address: str
    auth_results: str
    body: str
    received: str

@dataclass
class ClientCred:
    rfc: str
    name: str
    auth_type: str  # "efirma" | "ciec"
    ciec_password: str | None
    cer_path: str | None
    key_path: str | None
    key_password: str | None

@dataclass
class Classification:
    urgency: str  # "URGENT" | "ATTENTION" | "INFO"
    act_type: str
    deadline: str | None
    matched: list[str]

@dataclass
class FetchResult:
    ok: bool
    pdf_path: str | None
    error: str | None
    screenshot_path: str | None
