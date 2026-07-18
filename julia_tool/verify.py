from julia_tool.models import EmailMessage

def _domain(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].strip().lower()

def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    for a in allowed:
        a = a.lower()
        if domain == a or domain.endswith("." + a):
            return True
    return False

def is_genuine_sat(msg: EmailMessage, allowed_domains: list[str]) -> tuple[bool, str]:
    if not _domain_allowed(_domain(msg.from_address), allowed_domains):
        return False, "domain"
    ar = msg.auth_results.lower()
    if "spf=pass" not in ar:
        return False, "spf"
    if "dkim=pass" not in ar:
        return False, "dkim"
    return True, "ok"
