from julia_tool.rfc import extract_rfc
from julia_tool.verify import is_genuine_sat
from julia_tool.alert_words import should_forward


def process_message(msg, *, cfg, store, state, alerter, fetcher,
                    classify_pdf, now, dry_run: bool = False, alert_words=None, read_pdf_text=None) -> str:
    def _finish(outcome: str) -> str:
        if not dry_run:
            state.mark_processed(msg.id, outcome)
        return outcome

    ok, reason = is_genuine_sat(msg, cfg.allowed_domains)
    if not ok:
        if not dry_run:
            alerter.send_quarantine(msg.subject, msg.from_address, reason)
        return _finish("quarantined")

    rfc = extract_rfc(f"{msg.subject}\n{msg.body}")
    if not rfc:
        if not dry_run:
            alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    cred = store.get(rfc)
    if not cred:
        if not dry_run:
            alerter.send_unknown_client(msg.subject)
        return _finish("unknown_client")

    # Dry-run stops here: no portal login, no credential use, no mail sent.
    if dry_run:
        return "alert_sent"

    ts = now()
    result = fetcher.fetch(cred)
    state.log_credential_use(rfc, "buzon_login", "ok" if result.ok else "fail", ts)
    manual_url = cfg.portal.get("buzon_url", "https://www.sat.gob.mx")
    if not result.ok:
        alerter.send_fetch_failed(rfc, cred.name, manual_url)
        return _finish("fetch_failed")

    try:
        cls = classify_pdf(result.pdf_path)
    except Exception:  # noqa: BLE001 — a corrupt/unreadable PDF must not crash the loop
        alerter.send_fetch_failed(rfc, cred.name, manual_url)
        return _finish("fetch_failed")

    doc_text = ""
    if read_pdf_text is not None:
        try:
            doc_text = read_pdf_text(result.pdf_path)
        except Exception:  # noqa: BLE001 — gating text is best-effort
            doc_text = ""
    searchable = f"{msg.subject}\n{msg.body}\n{doc_text}"
    if not should_forward(searchable, alert_words or []):
        return _finish("not_forwarded")

    pdf_bytes = None
    try:
        with open(result.pdf_path, "rb") as f:
            pdf_bytes = (f"{rfc}.pdf", f.read())
    except OSError:
        pdf_bytes = None
    alerter.send_urgent(rfc, cred.name, cls, pdf_bytes)
    state.record_alert(rfc, cls.urgency, ts)
    return _finish("alert_sent")
