import re
from julia_tool.models import EmailMessage


def _domain(addr: str) -> str | None:
    """Return the lowercased domain of a single-mailbox address, else None."""
    parts = addr.strip().split("@")
    if len(parts) != 2:
        return None
    local, dom = parts
    if not local or not dom:
        return None
    return dom.lower()


def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    for a in allowed:
        a = a.lower()
        if domain == a or domain.endswith("." + a):
            return True
    return False


def _tag(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _auth_domain(value: str) -> str:
    """Reduce an auth identifier ('user@domain' or 'domain') to its domain."""
    return value.rsplit("@", 1)[-1].strip().strip(";").lower()


def is_genuine_sat(msg: EmailMessage, allowed_domains: list[str]) -> tuple[bool, str]:
    domain = _domain(msg.from_address)
    if domain is None or not _domain_allowed(domain, allowed_domains):
        return False, "domain"

    ar = msg.auth_results.lower()

    # When the receiving MTA reports a DMARC verdict, it already encodes
    # From-domain alignment — trust it directly.
    dmarc = _tag(r"\bdmarc=([a-z]+)", ar)
    if dmarc is not None:
        return (True, "ok") if dmarc == "pass" else (False, "dmarc")

    # No DMARC verdict: require SPF and DKIM to pass AND, where the aligning
    # identifier is present, to be aligned to an allowed domain.
    spf = _tag(r"\bspf=([a-z]+)", ar)
    if spf != "pass":
        return False, "spf"
    mailfrom = _tag(r"smtp\.mailfrom=([^\s;]+)", ar)
    if mailfrom is not None and not _domain_allowed(_auth_domain(mailfrom), allowed_domains):
        return False, "spf"

    dkim = _tag(r"\bdkim=([a-z]+)", ar)
    if dkim != "pass":
        return False, "dkim"
    header_d = _tag(r"header\.d=([^\s;]+)", ar)
    if header_d is not None and not _domain_allowed(_auth_domain(header_d), allowed_domains):
        return False, "dkim"

    return True, "ok"
