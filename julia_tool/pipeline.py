from julia_tool.rfc import extract_rfc
from julia_tool.verify import is_genuine_sat

def process_message(msg, *, cfg, store, state, alerter, fetcher,
                    classify_pdf, now, dry_run: bool = False) -> str:
    def _finish(outcome: str) -> str:
        if not dry_run:
            state.mark_processed(msg.id, outcome)
        return outcome

    ok, reason = is_genuine_sat(msg, cfg.allowed_domains)
    if not ok:
        alerter.send_quarantine(msg.subject, msg.from_address, reason)
        return _finish("quarantined")

    rfc = extract_rfc(f"{msg.subject}\n{msg.body}")
    if not rfc:
        alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    cred = store.get(rfc)
    if not cred:
        alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    ts = now()
    result = fetcher.fetch(cred)
    state.log_credential_use(rfc, "buzon_login", "ok" if result.ok else "fail", ts)
    if not result.ok:
        manual_url = cfg.portal.get("buzon_url", "https://www.sat.gob.mx")
        alerter.send_fetch_failed(rfc, cred.name, manual_url)
        return _finish("fetch_failed")

    cls = classify_pdf(result.pdf_path)
    pdf_bytes = None
    try:
        with open(result.pdf_path, "rb") as f:
            pdf_bytes = (f"{rfc}.pdf", f.read())
    except OSError:
        pdf_bytes = None
    alerter.send_urgent(rfc, cred.name, cls, pdf_bytes)
    if not dry_run:
        state.record_alert(rfc, cls.urgency, ts)
    return _finish("alert_sent")
