from __future__ import annotations

import json

from ..runtime_loader import error_response, invoke, public_data, schema, service, validate
from .workers import investigate

TOOLS = (
    ("ops_seed_demo", "seed", "Create a fresh independent synthetic manufacturer workspace, or idempotently reuse an explicit workspace ID."),
    ("ops_list_cases", "list", "List synthetic manufacturing cases in the current profile."),
    ("ops_case", "case", "Read a case, its evidence, alternatives, durable actions and observed outcome."),
    ("ops_investigate", "investigate", "Review supplied synthetic evidence in one bounded no-tools model task. Requires an active Hermes tool invocation; not an autonomous subagent."),
    ("ops_plan", "plan", "Persist feasible and rejected alternatives without reserving or executing."),
    ("ops_select_plan", "select", "Select a feasible plan at the supplied case revision; atomically reserve resources and prepare a durable action intent."),
    ("ops_execute", "execute", "Execute only the selected synthetic ERP action with stable logical identity; never a real purchase."),
    ("ops_reconcile", "reconcile", "Reconcile an uncertain synthetic ERP action by its stable key without blind retry."),
    ("ops_advance_demo", "advance", "Advance this synthetic workspace clock by whole hours and ingest due simulated source events."),
    ("ops_evaluate", "evaluate", "Compare immutable forecasts to simulated observations; incomplete evidence remains explicit."),
    ("ops_activate_correction", "correction", "Activate only an evidence-backed supplier-cutoff estimate at the expected policy version; never alter spending or customer priority."),
)


def register_tools(ctx):
    for name, operation, description in TOOLS:
        def handler(args, _operation=operation, **kwargs):
            try:
                validate(_operation, args)
                if _operation == "investigate":
                    result = investigate(ctx, service(), args["case_id"])
                else:
                    result = invoke(_operation, args)
                return json.dumps(public_data(result), ensure_ascii=False)
            except Exception as exc:
                status, result = error_response(exc)
                return json.dumps({**result, "status": status})

        ctx.register_tool(
            name=name, toolset="agentic_operations",
            schema={"name": name, "description": description, "parameters": schema(operation)},
            handler=handler, description=description,
        )
