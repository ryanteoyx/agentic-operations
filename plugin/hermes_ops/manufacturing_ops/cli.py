from __future__ import annotations

import argparse
import json

from ..runtime_loader import error_response, invoke

COMMANDS = {
    "seed": "seed", "list": "list", "case": "case", "plan": "plan", "select": "select",
    "execute": "execute", "reconcile": "reconcile", "advance": "advance",
    "evaluate": "evaluate", "correction": "correction", "playbook": "playbook",
}


def setup_parser(parser):
    parser.add_argument("--data-dir", help="Explicit data root; otherwise the active Hermes profile")
    commands = parser.add_subparsers(dest="ops_command", required=True)
    for name in COMMANDS:
        command = commands.add_parser(name)
        if name not in {"seed", "list", "playbook"}:
            command.add_argument("case_id")
        if name in {"plan", "select"}:
            command.add_argument("--expected-revision", type=int, required=name == "select")
        if name == "select":
            command.add_argument("plan_id")
        if name == "advance":
            command.add_argument("--hours", type=int, required=True)
        if name == "correction":
            command.add_argument("--expected-policy-version", type=int, required=True)
        if name == "seed":
            command.add_argument("--workspace-id")


def run(args):
    operation = COMMANDS[args.ops_command]
    names = ("case_id", "plan_id", "expected_revision", "hours", "expected_policy_version", "workspace_id")
    arguments = {key: getattr(args, key) for key in names if getattr(args, key, None) is not None}
    try:
        print(json.dumps(invoke(operation, arguments, args.data_dir), indent=2))
        return 0
    except Exception as exc:
        status, payload = error_response(exc)
        print(json.dumps({**payload, "status": status}))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic manufacturing operations")
    setup_parser(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
