import argparse
import os
import time
from datetime import datetime, timezone
from julia_tool.config import load_config
from julia_tool.secrets_store import SecretsStore
from julia_tool.state import State
from julia_tool.graph_client import GraphClient
from julia_tool.buzon import BuzonFetcher
from julia_tool.alert import Alerter
from julia_tool.classify import classify_text, extract_pdf_text
from julia_tool.pipeline import process_message

def build_now():
    return lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_once(cfg, store, state, graph, session, fetcher, dry_run=False,
            responsible=None) -> dict:
    now = build_now()
    resolved_responsible = responsible if responsible is not None else cfg.responsible_email
    alerter = Alerter(graph, session, resolved_responsible)
    def classify_pdf(path):
        return classify_text(extract_pdf_text(path), cfg.keyword_map)
    tally: dict[str, int] = {}
    for msg in graph.list_messages(session):
        if state.is_processed(msg.id):
            outcome = "skipped_duplicate"
        else:
            outcome = process_message(
                msg, cfg=cfg, store=store, state=state, alerter=alerter,
                fetcher=fetcher, classify_pdf=classify_pdf, now=now,
                dry_run=dry_run)
        tally[outcome] = tally.get(outcome, 0) + 1
    return tally

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="julia_tool")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--responsible", default=None,
                        help="override config.yaml's responsible_email "
                             "for alert recipients on this run")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    return parser

def main(argv=None):
    parser = _build_parser()
    ns = parser.parse_args(argv)

    if ns.rest and ns.rest[0] == "client":
        from julia_tool.clientcli import run as client_run
        return client_run(ns.rest[1:])

    cfg = load_config(ns.config)
    responsible = ns.responsible or cfg.responsible_email
    import getpass
    master = os.environ.get("JULIA_MASTER_PW") or getpass.getpass("Master password: ")
    store = SecretsStore(cfg.secrets_path, master)
    state = State(cfg.state_path)
    graph = GraphClient(cfg.tenant_id, cfg.client_id, cfg.mailbox)
    token = graph.acquire_token(prompt=True)
    session = graph.session(token)
    fetcher = BuzonFetcher(cfg.portal, cfg.download_dir)

    while True:
        tally = run_once(cfg, store, state, graph, session, fetcher,
                         dry_run=ns.dry_run, responsible=responsible)
        print(f"cycle tally: {tally}", flush=True)
        if ns.once:
            return 0
        time.sleep(cfg.poll_interval_s)

if __name__ == "__main__":
    raise SystemExit(main())
