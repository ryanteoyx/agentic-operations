from __future__ import annotations

import hashlib
import json

CONNECTOR_ID = "sim-erp"


def canonical_payload(case_id: str, plan_id: str, snapshot: dict,
                      supplier: dict) -> dict:
    shortage = max(0, snapshot["replacement_units"] + snapshot["sales_units"]
                   - snapshot["stock_units"])
    return {
        "type": "purchase_order",
        "case_id": case_id,
        "plan_id": plan_id,
        "supplier_id": supplier["id"],
        "component_id": snapshot["component_id"],
        "units": shortage,
        "unit": snapshot["unit"],
        "unit_cost_minor": snapshot["component_cost_minor"],
    }


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def actual_receipt_hour(supplier: dict) -> int:
    return supplier["lead_hours"] + supplier["cutoff_delay_hours"]


def idempotency_key(case_id: str, plan_id: str) -> str:
    return f"agentic-ops:{case_id}:{plan_id}"
