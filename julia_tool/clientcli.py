import argparse
import os
from julia_tool.models import ClientCred

def _master_from_env_or_prompt() -> str:
    pw = os.environ.get("JULIA_MASTER_PW")
    if pw:
        return pw
    import getpass
    return getpass.getpass("Master password: ")

def run(argv: list[str], store_factory=None) -> int:
    parser = argparse.ArgumentParser(prog="julia_tool client")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--rfc", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--auth-type", required=True, choices=["efirma", "ciec"])
    a.add_argument("--ciec-password")
    a.add_argument("--cer-path")
    a.add_argument("--key-path")
    a.add_argument("--key-password")

    r = sub.add_parser("remove")
    r.add_argument("--rfc", required=True)

    sub.add_parser("list")

    ns = parser.parse_args(argv)
    factory = store_factory or (lambda pw: _real_store(pw))
    store = factory(_master_from_env_or_prompt())

    if ns.cmd == "add":
        store.add(ClientCred(
            rfc=ns.rfc.upper(), name=ns.name, auth_type=ns.auth_type,
            ciec_password=ns.ciec_password, cer_path=ns.cer_path,
            key_path=ns.key_path, key_password=ns.key_password))
        print(f"added {ns.rfc.upper()}")
        return 0
    if ns.cmd == "remove":
        ok = store.remove(ns.rfc.upper())
        print("removed" if ok else "not found")
        return 0
    if ns.cmd == "list":
        for rfc in store.list_rfcs():
            print(rfc)
        return 0
    return 1

def _real_store(pw: str):
    from julia_tool.config import load_config
    from julia_tool.secrets_store import SecretsStore
    cfg = load_config(os.environ.get("JULIA_CONFIG", "config.yaml"))
    return SecretsStore(cfg.secrets_path, pw)
