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


def _auth_domain(value: str) -> str:
    """Reduce an auth identifier ('user@domain' or 'domain') to its domain."""
    return value.rsplit("@", 1)[-1].strip().lower()


def _method_aligned_pass(clauses: list[str], method: str, id_tag: str,
                         allowed: list[str]) -> bool:
    """True iff some clause has <method>=pass and (its id_tag is absent OR aligned)."""
    result_re = re.compile(rf"\b{method}=([a-z]+)")
    id_re = re.compile(rf"\b{re.escape(id_tag)}=([^\s;]+)")
    saw_result = False
    for clause in clauses:
        m = result_re.search(clause)
        if not m:
            continue
        saw_result = True
        if m.group(1) != "pass":
            continue
        idm = id_re.search(clause)
        if idm is None or _domain_allowed(_auth_domain(idm.group(1)), allowed):
            return True
    # No clause carried this method at all → treated as "not passing" by caller.
    # A clause carried a non-pass result, or every pass was misaligned → not aligned.
    _ = saw_result
    return False


def is_genuine_sat(msg: EmailMessage, allowed_domains: list[str]) -> tuple[bool, str]:
    domain = _domain(msg.from_address)
    if domain is None or not _domain_allowed(domain, allowed_domains):
        return False, "domain"

    ar = msg.auth_results.lower()
    clauses = [c.strip() for c in ar.split(";") if c.strip()]

    # When the receiving MTA reports a DMARC verdict, it already encodes
    # From-domain alignment — trust it directly.
    dmarc_results = [
        m.group(1) for c in clauses
        if (m := re.search(r"\bdmarc=([a-z]+)", c))
    ]
    if dmarc_results:
        return (True, "ok") if "pass" in dmarc_results else (False, "dmarc")

    # No DMARC verdict: require an aligned SPF pass AND an aligned DKIM pass.
    if not _method_aligned_pass(clauses, "spf", "smtp.mailfrom", allowed_domains):
        return False, "spf"
    if not _method_aligned_pass(clauses, "dkim", "header.d", allowed_domains):
        return False, "dkim"

    return True, "ok"
