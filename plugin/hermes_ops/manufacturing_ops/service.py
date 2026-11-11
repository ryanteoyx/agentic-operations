from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from . import decision, evaluation, execution
from .models import ConflictError
from .sim.erp import SimulatedERP
from .store import connect, init_db, write_tx

FIXTURE_PATH = Path(__file__).parent / "sim" / "manufacturer.json"
SCENARIO_TITLE = "Supplier delay threatens an order and warranty replacement"
TASK_LEASE_SECONDS = 90

_INT_KEYS = (
    "stock_units", "replacement_units", "replacement_due_hour",
    "sales_units", "sales_due_hour", "hours_per_unit",
    "original_po_units", "original_receipt_hour",
    "component_cost_minor", "expedite_limit_minor",
)
_STR_KEYS = (
    "product_id", "bom_id", "bom_revision", "component_id", "unit",
    "replacement_id", "sales_order_id", "original_po_id",
)


def validate_snapshot(s: dict) -> dict:
    if not isinstance(s, dict):
        raise ValueError("snapshot must be an object")
    for key in _INT_KEYS:
        if not isinstance(s.get(key), int) or isinstance(s.get(key), bool):
            raise ValueError(f"snapshot field {key} must be an integer")
    for key in _STR_KEYS:
        if not isinstance(s.get(key), str) or not s[key]:
            raise ValueError(f"snapshot field {key} must be a nonempty string")
    if s.get("synthetic") is not True:
        raise ValueError("snapshot must be marked synthetic")
    if s.get("scenario_id") != "cutoff":
        raise ValueError("unknown scenario_id")
    if s["unit"] != "each":
        raise ValueError("unsupported unit")
    if s.get("components_per_unit") != 1:
        raise ValueError("unsupported components_per_unit")
    if s["stock_units"] < 0 or s["original_po_units"] < 0:
        raise ValueError("quantities cannot be negative")
    if s["replacement_units"] <= 0 or s["sales_units"] <= 0:
        raise ValueError("order quantities must be positive")
    if s["replacement_due_hour"] < 0 or s["sales_due_hour"] < 0 or s["original_receipt_hour"] < 0:
        raise ValueError("deadlines cannot be negative")
    if s["hours_per_unit"] <= 0 or s["component_cost_minor"] < 0:
        raise ValueError("invalid capacity or cost figure")
    if s["expedite_limit_minor"] < 0:
        raise ValueError("expedite limit cannot be negative")
    suppliers = s.get("suppliers")
    if not isinstance(suppliers, list) or not suppliers:
        raise ValueError("snapshot requires a nonempty suppliers list")
    seen = set()
    for p in suppliers:
        if not isinstance(p, dict):
            raise ValueError("supplier entries must be objects")
        for key in ("id", "plan_id", "label"):
            if not isinstance(p.get(key), str) or not p[key]:
                raise ValueError("supplier requires id, plan_id, and label")
        if not isinstance(p.get("approved"), bool):
            raise ValueError("supplier approved flag must be boolean")
        for key in ("lead_hours", "cutoff_delay_hours", "incremental_cost_minor"):
            if not isinstance(p.get(key), int) or isinstance(p.get(key), bool) or p[key] < 0:
                raise ValueError(f"supplier field {key} must be a nonnegative integer")
        if p["id"] in seen or p["plan_id"] in seen:
            raise ValueError("duplicate supplier identity")
        seen.add(p["id"])
        seen.add(p["plan_id"])
    if not isinstance(s.get("evidence"), list):
        raise ValueError("snapshot requires an evidence list")
    for e in s["evidence"]:
        if not isinstance(e.get("id"), str) or not e["id"]:
            raise ValueError("evidence item requires an id")
    return s


def _new_id() -> str:
    return uuid.uuid4().hex


class OpsService:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ops_path = self.data_dir / "operations.db"
        init_db(self.ops_path)
        self.erp = SimulatedERP(self.data_dir / "sim_erp.db")
        conn = self._conn()
        try:
            with write_tx(conn):
                self._expire_tasks(conn)
        finally:
            conn.close()

    def _conn(self):
        return connect(self.ops_path)

    def _load_fixture(self) -> dict:
        return validate_snapshot(json.loads(FIXTURE_PATH.read_text()))

    def _active_policy_version(self, conn) -> int:
        return conn.execute(
            "SELECT active_version FROM policy_state WHERE id = 1"
        ).fetchone()[0]

    def _get_row(self, conn, table: str, row_id: str):
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise KeyError(row_id)
        return row

    def _add_event(self, conn, workspace_id: str, case_id: str | None, kind: str,
                   at_hour: int, payload: dict, source_event_key: str | None = None) -> int:
        return conn.execute(
            "INSERT OR IGNORE INTO events (id, workspace_id, case_id, kind, at_hour, payload, source_event_key)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_new_id(), workspace_id, case_id, kind, at_hour,
             json.dumps(payload, sort_keys=True), source_event_key),
        ).rowcount

    def seed_demo(self, scenario_id: str = "cutoff", workspace_id: str | None = None) -> dict:
        snapshot = self._load_fixture()
        if scenario_id != snapshot["scenario_id"]:
            raise ValueError("unknown scenario_id")
        conn = self._conn()
        try:
            with write_tx(conn):
                if workspace_id is not None:
                    ws = conn.execute(
                        "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
                    ).fetchone()
                    if ws is not None:
                        case = conn.execute(
                            "SELECT * FROM cases WHERE workspace_id = ? ORDER BY created_hour, id",
                            (workspace_id,),
                        ).fetchone()
                        return self._case_dict(conn, case["id"])
                ws_id = workspace_id or _new_id()
                trigger_key = f"{scenario_id}:{snapshot['replacement_id']}:{snapshot['sales_order_id']}"
                conn.execute(
                    "INSERT INTO workspaces (id, company, currency, timezone, base_instant, stock_units, policy_version)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ws_id, snapshot["company"], snapshot["currency"],
                     snapshot["timezone"], snapshot["base_instant"],
                     snapshot["stock_units"], self._active_policy_version(conn)),
                )
                case_id = _new_id()
                conn.execute(
                    "INSERT INTO cases (id, workspace_id, title, state, revision, trigger_key, policy_version, snapshot, created_hour)"
                    " VALUES (?, ?, ?, 'OPEN', 1, ?, ?, ?, 0)",
                    (case_id, ws_id, SCENARIO_TITLE, trigger_key,
                     self._active_policy_version(conn), json.dumps(snapshot, sort_keys=True)),
                )
                for kind, source_id, due in (
                    ("warranty_shipment", snapshot["replacement_id"], snapshot["replacement_due_hour"]),
                    ("sales_shipment", snapshot["sales_order_id"], snapshot["sales_due_hour"]),
                ):
                    conn.execute(
                        "INSERT INTO obligations (id, case_id, kind, source_id, due_hour, status)"
                        " VALUES (?, ?, ?, ?, ?, 'OPEN')",
                        (_new_id(), case_id, kind, source_id, due),
                    )
                self._add_event(conn, ws_id, case_id, "case_opened", 0,
                                {"trigger_key": trigger_key, "scenario_id": scenario_id},
                                source_event_key=f"trigger:{trigger_key}")
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def _expire_tasks(self, conn) -> None:
        conn.execute(
            "UPDATE tasks SET status = 'INTERRUPTED',"
            " error = 'Worker lease expired; retry with a new attempt'"
            " WHERE status = 'RUNNING' AND (lease_until IS NULL OR lease_until <= ?)",
            (time.time(),),
        )

    def list_cases(self) -> list[dict]:
        conn = self._conn()
        try:
            with write_tx(conn):
                self._expire_tasks(conn)
            rows = conn.execute(
                "SELECT id FROM cases ORDER BY created_hour, id"
            ).fetchall()
            return [self._case_dict(conn, r["id"]) for r in rows]
        finally:
            conn.close()

    def get_case(self, case_id: str) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                self._expire_tasks(conn)
            return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def plan(self, case_id: str, expected_revision: int | None = None) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                self._check_revision(case, expected_revision)
                if case["selected_plan_id"] is not None:
                    raise ConflictError("selected plan is immutable")
                if case["state"] in ("CANCELLED", "CLOSED"):
                    raise ConflictError(f"case is {case['state']}")
                if self._clock(conn, case["workspace_id"]) != 0:
                    raise ConflictError("plan expired; demo selection must execute at hour zero")
                snapshot = json.loads(case["snapshot"])
                options = decision.build_options(snapshot, case["policy_version"])
                feasible = [o for o in options if o["feasible"]]
                if feasible:
                    state = "READY"
                    attention = None
                else:
                    state = "NEEDS_ATTENTION"
                    attention = sorted({r for o in options for r in o["reasons"]})
                conn.execute(
                    "UPDATE cases SET state = ?, options = ?, attention_reasons = ?, revision = revision + 1"
                    " WHERE id = ? AND revision = ?",
                    (state, json.dumps(options), json.dumps(attention),
                     case_id, case["revision"]),
                )
                self._add_event(conn, case["workspace_id"], case_id, "options_evaluated",
                                self._clock(conn, case["workspace_id"]),
                                {"policy_version": case["policy_version"],
                                 "feasible": [o["id"] for o in feasible]})
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def select_plan(self, case_id: str, plan_id: str, expected_revision: int) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                self._check_revision(case, expected_revision)
                if case["selected_plan_id"] is not None:
                    raise ConflictError("selected plan is immutable")
                if case["state"] not in ("READY", "OPEN", "INVESTIGATING"):
                    raise ConflictError(f"case is {case['state']}")
                if self._clock(conn, case["workspace_id"]) != 0:
                    raise ConflictError("plan expired; demo selection must execute at hour zero")
                options = json.loads(case["options"]) if case["options"] else None
                if options is None:
                    raise ConflictError("plan must be evaluated before selection")
                option = next((o for o in options if o["id"] == plan_id), None)
                if option is None:
                    raise ValueError(f"unknown plan id {plan_id}")
                if not option["feasible"]:
                    raise ValueError(f"plan {plan_id} is infeasible: {option['reasons']}")
                snapshot = json.loads(case["snapshot"])
                ws = self._get_row(conn, "workspaces", case["workspace_id"])
                held = conn.execute(
                    "SELECT COALESCE(SUM(qty), 0) FROM reservations"
                    " WHERE workspace_id = ? AND kind = 'stock' AND state = 'HELD'",
                    (ws["id"],),
                ).fetchone()[0]
                reserved_units = min(snapshot["stock_units"],
                                     snapshot["replacement_units"] + snapshot["sales_units"])
                if ws["stock_units"] - held < reserved_units:
                    raise ConflictError("insufficient unreserved stock for the plan")
                start, end = 0, option["predicted_sales_ship_hour"]
                overlap = conn.execute(
                    "SELECT COUNT(*) FROM reservations WHERE workspace_id = ? AND kind = 'assembly'"
                    " AND state = 'HELD' AND start_hour < ? AND end_hour > ?",
                    (ws["id"], end, start),
                ).fetchone()[0]
                if overlap:
                    raise ConflictError("assembly interval is already reserved")
                conn.execute(
                    "INSERT INTO reservations (id, workspace_id, case_id, kind, qty, start_hour, end_hour, state)"
                    " VALUES (?, ?, ?, 'stock', ?, NULL, NULL, 'HELD')",
                    (_new_id(), ws["id"], case_id, reserved_units),
                )
                conn.execute(
                    "INSERT INTO reservations (id, workspace_id, case_id, kind, qty, start_hour, end_hour, state)"
                    " VALUES (?, ?, ?, 'assembly', 0, ?, ?, 'HELD')",
                    (_new_id(), ws["id"], case_id, start, end),
                )
                if option["supplier_id"] is not None:
                    supplier = next(p for p in snapshot["suppliers"]
                                    if p["id"] == option["supplier_id"])
                    payload = execution.canonical_payload(case_id, plan_id, snapshot, supplier)
                    conn.execute(
                        "INSERT INTO actions (id, case_id, idempotency_key, connector, payload, payload_hash, status)"
                        " VALUES (?, ?, ?, ?, ?, ?, 'PREPARED')",
                        (_new_id(), case_id, execution.idempotency_key(case_id, plan_id),
                         execution.CONNECTOR_ID, json.dumps(payload, sort_keys=True),
                         execution.payload_hash(payload)),
                    )
                conn.execute(
                    "UPDATE cases SET state = 'READY', selected_plan_id = ?, prediction = ?,"
                    " revision = revision + 1 WHERE id = ? AND revision = ?",
                    (plan_id, json.dumps(option, sort_keys=True), case_id, case["revision"]),
                )
                self._add_event(conn, ws["id"], case_id, "plan_selected",
                                self._clock(conn, ws["id"]), {"plan_id": plan_id})
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def execute(self, case_id: str, crash_after_external: bool = False) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                if case["selected_plan_id"] is None:
                    raise ConflictError("no plan is selected")
                action = conn.execute(
                    "SELECT * FROM actions WHERE case_id = ?", (case_id,)
                ).fetchone()
                if action is None:
                    raise ConflictError("selected plan created no executable action")
                if action["status"] in ("CONFIRMED",):
                    return self._case_dict(conn, case_id)
                if self._clock(conn, case["workspace_id"]) != 0:
                    raise ConflictError("plan expired; demo selection must execute at hour zero")
                if action["status"] != "PREPARED":
                    raise ConflictError(f"action is {action['status']}; reconcile first")
                n = conn.execute(
                    "SELECT COUNT(*) FROM action_attempts WHERE action_id = ?", (action["id"],)
                ).fetchone()[0] + 1
                conn.execute(
                    "INSERT INTO action_attempts (id, action_id, n, status) VALUES (?, ?, ?, 'IN_FLIGHT')",
                    (_new_id(), action["id"], n),
                )
                conn.execute("UPDATE actions SET status = 'IN_FLIGHT' WHERE id = ?", (action["id"],))
                conn.execute(
                    "UPDATE cases SET state = 'EXECUTING', revision = revision + 1 WHERE id = ?",
                    (case_id,))
            conn.close()
            snapshot = json.loads(case["snapshot"])
            payload = json.loads(action["payload"])
            supplier = next(p for p in snapshot["suppliers"]
                            if p["id"] == payload["supplier_id"])
            try:
                po = self.erp.execute(
                    action["idempotency_key"], payload, action["payload_hash"],
                    self._clock_by_id(case["workspace_id"]),
                    execution.actual_receipt_hour(supplier),
                )
            except Exception as exc:
                conn2 = self._conn()
                try:
                    with write_tx(conn2):
                        conn2.execute(
                            "UPDATE action_attempts SET status = 'UNCERTAIN', detail = ?"
                            " WHERE action_id = ? AND status = 'IN_FLIGHT'",
                            (str(exc), action["id"]),
                        )
                        conn2.execute(
                            "UPDATE actions SET status = 'UNCERTAIN' WHERE id = ?",
                            (action["id"],),
                        )
                        conn2.execute(
                            "UPDATE cases SET state = 'NEEDS_ATTENTION',"
                            " attention_reasons = ?, revision = revision + 1 WHERE id = ?",
                            (json.dumps([f"connector outcome unknown: {exc}"]), case_id),
                        )
                        self._add_event(conn2, case["workspace_id"], case_id,
                                        "action_outcome_unknown",
                                        self._clock(conn2, case["workspace_id"]),
                                        {"action_id": action["id"], "error": str(exc)})
                finally:
                    conn2.close()
                raise
            if crash_after_external:
                os._exit(73)
            conn2 = self._conn()
            try:
                with write_tx(conn2):
                    self._confirm_action(conn2, conn2.execute(
                        "SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone(),
                        conn2.execute("SELECT * FROM actions WHERE id = ?",
                                      (action["id"],)).fetchone(),
                        po, "action_confirmed")
                    return self._case_dict(conn2, case_id)
            finally:
                conn2.close()
        finally:
            conn.close()

    def _consume_stock(self, conn, case_id: str):
        res = conn.execute(
            "SELECT * FROM reservations WHERE case_id = ? AND kind = 'stock' AND state = 'HELD'",
            (case_id,),
        ).fetchone()
        if res is not None:
            cur = conn.execute(
                "UPDATE reservations SET state = 'CONSUMED' WHERE id = ? AND state = 'HELD'",
                (res["id"],),
            )
            if cur.rowcount == 1:
                conn.execute(
                    "UPDATE workspaces SET stock_units = stock_units - ? WHERE id = ?",
                    (res["qty"], res["workspace_id"]),
                )

    def _confirm_action(self, conn, case, action, po: dict, event_kind: str):
        if action["status"] == "CONFIRMED":
            return
        conn.execute(
            "UPDATE actions SET status = 'CONFIRMED', external_ref = ? WHERE id = ?",
            (po["id"], action["id"]),
        )
        conn.execute(
            "UPDATE action_attempts SET status = 'SUCCEEDED'"
            " WHERE action_id = ? AND status = 'IN_FLIGHT'",
            (action["id"],),
        )
        conn.execute(
            "UPDATE cases SET state = 'OBSERVING', attention_reasons = NULL,"
            " revision = revision + 1 WHERE id = ?",
            (case["id"],),
        )
        self._consume_stock(conn, case["id"])
        self._add_event(conn, case["workspace_id"], case["id"], event_kind,
                        self._clock(conn, case["workspace_id"]),
                        {"action_id": action["id"], "external_ref": po["id"],
                         "receipt_hour": po["receipt_hour"]},
                        source_event_key=f"ack:{action['idempotency_key']}")
        snapshot = json.loads(case["snapshot"])
        payload = json.loads(action["payload"])
        supplier = next((p for p in snapshot["suppliers"]
                         if p["id"] == payload["supplier_id"]), None)
        if supplier is not None and supplier["cutoff_delay_hours"] > 0:
            self._add_event(conn, case["workspace_id"], case["id"],
                            "supplier_cutoff_confirmed",
                            self._clock(conn, case["workspace_id"]),
                            {"supplier_id": supplier["id"],
                             "cutoff_delay_hours": supplier["cutoff_delay_hours"],
                             "source_po": po["id"]},
                            source_event_key=f"cutoff:{action['idempotency_key']}")

    def reconcile(self, case_id: str) -> dict:
        conn = self._conn()
        try:
            self._get_row(conn, "cases", case_id)
            pending = conn.execute(
                "SELECT * FROM actions WHERE case_id = ? AND status IN ('IN_FLIGHT', 'UNCERTAIN', 'NEEDS_ATTENTION')",
                (case_id,),
            ).fetchall()
        finally:
            conn.close()
        lookups = {a["id"]: self.erp.lookup(a["idempotency_key"]) for a in pending}
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                for prior in pending:
                    action = conn.execute(
                        "SELECT * FROM actions WHERE id = ?", (prior["id"],)
                    ).fetchone()
                    if action is None or action["status"] != prior["status"]:
                        continue
                    po = lookups[prior["id"]]
                    if po is None or po["payload_hash"] != action["payload_hash"]:
                        if action["status"] == "NEEDS_ATTENTION":
                            continue
                        reason = ("connector outcome unknown"
                                  if po is None else "connector payload mismatch")
                        conn.execute(
                            "UPDATE action_attempts SET status = 'UNCERTAIN', detail = ?"
                            " WHERE action_id = ? AND status = 'IN_FLIGHT'",
                            (reason, action["id"]),
                        )
                        conn.execute(
                            "UPDATE actions SET status = 'NEEDS_ATTENTION' WHERE id = ?",
                            (action["id"],),
                        )
                        conn.execute(
                            "UPDATE cases SET state = 'NEEDS_ATTENTION',"
                            " attention_reasons = ?, revision = revision + 1 WHERE id = ?",
                            (json.dumps([reason]), case_id),
                        )
                        self._add_event(conn, case["workspace_id"], case_id,
                                        "action_outcome_unknown",
                                        self._clock(conn, case["workspace_id"]),
                                        {"action_id": action["id"], "reason": reason})
                    else:
                        conn.execute(
                            "UPDATE action_attempts SET status = 'RECONCILED'"
                            " WHERE action_id = ? AND status IN ('IN_FLIGHT', 'UNCERTAIN')",
                            (action["id"],),
                        )
                        self._confirm_action(conn, case, action, po, "reconciled")
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def advance(self, case_id: str, hours: int) -> dict:
        if not isinstance(hours, int) or isinstance(hours, bool) or hours < 0:
            raise ValueError("hours must be a nonnegative whole number")
        conn = self._conn()
        try:
            self._get_row(conn, "cases", case_id)
            prior_action = conn.execute(
                "SELECT * FROM actions WHERE case_id = ? AND status = 'CONFIRMED'",
                (case_id,),
            ).fetchone()
        finally:
            conn.close()
        po = self.erp.lookup(prior_action["idempotency_key"]) if prior_action else None
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                ws = self._get_row(conn, "workspaces", case["workspace_id"])
                if not ws["demo"]:
                    raise ConflictError("advance is only available for demo workspaces")
                action = conn.execute(
                    "SELECT * FROM actions WHERE case_id = ? AND status = 'CONFIRMED'",
                    (case_id,),
                ).fetchone()
                if case["selected_plan_id"] is None or not prior_action or not po:
                    raise ConflictError(
                        "execute and reconcile the selected action before advancing")
                if action is None or action["idempotency_key"] != prior_action["idempotency_key"] \
                        or po["action_key"] != action["idempotency_key"] \
                        or po["payload_hash"] != action["payload_hash"]:
                    raise ConflictError(
                        "connector record does not match the confirmed action")
                now = ws["clock_hour"] + hours
                conn.execute(
                    "UPDATE workspaces SET clock_hour = ? WHERE id = ?", (now, ws["id"])
                )
                snapshot = json.loads(case["snapshot"])
                self._add_event(conn, ws["id"], case_id, "clock_advanced", now,
                                {"hours": hours, "clock_hour": now},
                                source_event_key=f"clock:{case_id}:{now}")
                if now >= snapshot["original_receipt_hour"]:
                    inserted = self._add_event(
                        conn, ws["id"], case_id, "original_receipt",
                        snapshot["original_receipt_hour"],
                        {"po_id": snapshot["original_po_id"],
                         "units": snapshot["original_po_units"],
                         "component_id": snapshot["component_id"]},
                        source_event_key=f"orig-receipt:{snapshot['original_po_id']}")
                    if inserted:
                        conn.execute(
                            "UPDATE workspaces SET stock_units = stock_units + ? WHERE id = ?",
                            (snapshot["original_po_units"], ws["id"]),
                        )
                if hours > 0:
                    conn.execute(
                        "UPDATE cases SET revision = revision + 1 WHERE id = ?",
                        (case_id,),
                    )
                if po["receipt_hour"] <= now:
                    self._add_event(conn, ws["id"], case_id, "erp_receipt",
                                        po["receipt_hour"],
                                        {"action_id": action["id"],
                                         "external_ref": po["id"],
                                         "receipt_hour": po["receipt_hour"],
                                         "units": json.loads(action["payload"])["units"]},
                                        source_event_key=f"receipt:{action['idempotency_key']}")
                snapshot_now = json.loads(case['snapshot'])
                replacement_ship = snapshot_now['replacement_units'] * snapshot_now['hours_per_unit']
                initial_sales = max(0, min(snapshot_now['sales_units'], snapshot_now['stock_units'] - snapshot_now['replacement_units']))
                initial_finish = replacement_ship + initial_sales * snapshot_now['hours_per_unit']
                remaining_sales = snapshot_now['sales_units'] - initial_sales
                sales_ship = max(initial_finish, po['receipt_hour']) + remaining_sales * snapshot_now['hours_per_unit'] if remaining_sales else initial_finish
                if replacement_ship <= now:
                    self._add_event(conn, ws["id"], case_id, "shipment",
                                    replacement_ship,
                                    {"order_id": snapshot_now["replacement_id"],
                                     "units": snapshot_now["replacement_units"]},
                                    source_event_key=f"ship:{snapshot_now['replacement_id']}")
                if sales_ship <= now:
                    self._add_event(conn, ws["id"], case_id, "shipment",
                                    sales_ship,
                                    {"order_id": snapshot_now["sales_order_id"],
                                     "units": snapshot_now["sales_units"]},
                                    source_event_key=f"ship:{snapshot_now['sales_order_id']}")
                shipped = {
                    r[0] for r in conn.execute(
                        "SELECT json_extract(payload, '$.order_id') FROM events"
                        " WHERE case_id = ? AND kind = 'shipment'", (case_id,)
                    ).fetchall()
                }
                open_obs = conn.execute(
                    "SELECT * FROM obligations WHERE case_id = ? AND status = 'OPEN'", (case_id,)
                ).fetchall()
                for ob in open_obs:
                    if ob["source_id"] in shipped:
                        conn.execute(
                            "UPDATE obligations SET status = 'RESOLVED' WHERE id = ?", (ob["id"],)
                        )
                remaining = conn.execute(
                    "SELECT COUNT(*) FROM obligations WHERE case_id = ? AND status != 'RESOLVED'",
                    (case_id,),
                ).fetchone()[0]
                if remaining == 0 and conn.execute(
                    "SELECT state FROM cases WHERE id = ?", (case_id,)
                ).fetchone()[0] not in ("CLOSED", "CANCELLED"):
                    conn.execute(
                        "UPDATE cases SET state = 'CLOSED', revision = revision + 1 WHERE id = ?",
                        (case_id,),
                    )
                    conn.execute(
                        "UPDATE reservations SET state = 'RELEASED'"
                        " WHERE case_id = ? AND kind = 'assembly' AND state = 'HELD'",
                        (case_id,),
                    )
                    self._add_event(conn, ws["id"], case_id, "case_closed", now, {})
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def evaluate(self, case_id: str) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                if case["prediction"] is None:
                    raise ConflictError("no plan has been selected")
                snapshot = json.loads(case["snapshot"])
                prediction = json.loads(case["prediction"])
                observed = {}
                for ev in conn.execute(
                    "SELECT * FROM events WHERE case_id = ? AND kind IN ('erp_receipt', 'shipment')",
                    (case_id,),
                ).fetchall():
                    payload = json.loads(ev["payload"])
                    if ev["kind"] == "erp_receipt":
                        observed["receipt_hour"] = payload["receipt_hour"]
                    elif payload.get("order_id") == snapshot["replacement_id"]:
                        observed["replacement_ship_hour"] = ev["at_hour"]
                    elif payload.get("order_id") == snapshot["sales_order_id"]:
                        observed["sales_ship_hour"] = ev["at_hour"]
                result = evaluation.compare_outcome(snapshot, prediction, observed)
                conn.execute(
                    "UPDATE cases SET evaluation = ? WHERE id = ?",
                    (json.dumps(result, sort_keys=True), case_id),
                )
                if result.get("complete") and not result["sales_on_time"]:
                    cutoff_ev = conn.execute(
                        "SELECT * FROM events WHERE case_id = ? AND kind = 'supplier_cutoff_confirmed'"
                        " ORDER BY at_hour LIMIT 1", (case_id,),
                    ).fetchone()
                    receipt_ev = conn.execute(
                        "SELECT * FROM events WHERE case_id = ? AND kind = 'erp_receipt'"
                        " ORDER BY at_hour LIMIT 1", (case_id,),
                    ).fetchone()
                    if (cutoff_ev is not None and receipt_ev is not None
                            and result["actual_receipt_hour"] > prediction["predicted_receipt_hour"]):
                        cutoff_payload = json.loads(cutoff_ev["payload"])
                        existing = conn.execute(
                            "SELECT * FROM corrections WHERE case_id = ?", (case_id,)
                        ).fetchone()
                        if existing is None:
                            conn.execute(
                                "INSERT INTO corrections (id, case_id, state, evidence, proposal, prev_version)"
                                " VALUES (?, ?, 'proposed', ?, ?, ?)",
                                (_new_id(), case_id,
                                 json.dumps({"event_ids": [cutoff_ev["id"], receipt_ev["id"]],
                                             "actual_receipt_hour": result["actual_receipt_hour"],
                                             "predicted_receipt_hour": prediction["predicted_receipt_hour"],
                                             "supplier_id": cutoff_payload["supplier_id"],
                                             "cutoff_delay_hours": cutoff_payload["cutoff_delay_hours"],
                                             "source_po": cutoff_payload["source_po"]}),
                                 json.dumps({"estimate": "supplier_cutoff_delay",
                                             "cutoff_delay_hours": cutoff_payload["cutoff_delay_hours"]}),
                                 case["policy_version"]),
                            )
                            self._add_event(conn, case["workspace_id"], case_id,
                                            "correction_proposed", self._clock(conn, case["workspace_id"]),
                                            {"supplier_id": cutoff_payload["supplier_id"]})
                self._add_event(conn, case["workspace_id"], case_id, "outcome_evaluated",
                                self._clock(conn, case["workspace_id"]),
                                {"complete": result["complete"]},
                                source_event_key=f"eval:{case_id}:{result.get('complete')}")
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def activate_correction(self, case_id: str, expected_policy_version: int) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                correction = conn.execute(
                    "SELECT * FROM corrections WHERE case_id = ?", (case_id,)
                ).fetchone()
                if correction is None:
                    raise ConflictError("no proposed correction exists for this case")
                if correction["state"] == "activated":
                    return self._case_dict(conn, case_id)
                eval_row = json.loads(case["evaluation"]) if case["evaluation"] else None
                if not eval_row or not eval_row.get("complete"):
                    raise ConflictError("correction requires complete supporting observations")
                if expected_policy_version != correction["prev_version"] \
                        or correction["prev_version"] != case["policy_version"]:
                    raise ConflictError("correction proposal is stale")
                if correction["prev_version"] != 1:
                    raise ConflictError("only the v1 cutoff estimate can be activated")
                cur = conn.execute(
                    "UPDATE policy_state SET active_version = 2"
                    " WHERE id = 1 AND active_version = ?",
                    (expected_policy_version,),
                )
                if cur.rowcount != 1:
                    raise ConflictError("policy version conflict")
                conn.execute(
                    "UPDATE corrections SET state = 'activated', new_version = ? WHERE id = ?",
                    (expected_policy_version + 1, correction["id"]),
                )
                conn.execute(
                    "UPDATE cases SET revision = revision + 1 WHERE id = ?", (case_id,)
                )
                self._add_event(conn, case["workspace_id"], case_id, "correction_activated",
                                self._clock(conn, case["workspace_id"]),
                                {"new_version": expected_policy_version + 1})
                return self._case_dict(conn, case_id)
        finally:
            conn.close()

    def playbook(self) -> dict:
        conn = self._conn()
        try:
            corrections = conn.execute(
                "SELECT * FROM corrections ORDER BY prev_version, id"
            ).fetchall()
            return {
                "active_version": self._active_policy_version(conn),
                "synthetic": True,
                "constraints": [
                    "warranty commitment deadline",
                    "sales order commitment deadline",
                    "approved suppliers only",
                    "delegated incremental spend limit",
                    "usable stock and assembly capacity",
                ],
                "corrections": [
                    {"id": c["id"], "case_id": c["case_id"], "state": c["state"],
                     "prev_version": c["prev_version"], "new_version": c["new_version"],
                     "evidence": json.loads(c["evidence"]),
                     "proposal": json.loads(c["proposal"])}
                    for c in corrections
                ],
            }
        finally:
            conn.close()

    def create_task(self, case_id: str, role: str = "supplier-review") -> dict:
        if role != "supplier-review":
            raise ValueError("unsupported worker role")
        conn = self._conn()
        try:
            with write_tx(conn):
                case = self._get_row(conn, "cases", case_id)
                if case["state"] in ("CLOSED", "CANCELLED"):
                    raise ConflictError(f"case is {case['state']}")
                task_id = _new_id()
                conn.execute(
                    "INSERT INTO tasks (id, case_id, role, status, input_revision)"
                    " VALUES (?, ?, ?, 'PENDING', ?)",
                    (task_id, case_id, role, case["revision"]),
                )
                self._add_event(conn, case["workspace_id"], case_id, "task_created",
                                self._clock(conn, case["workspace_id"]),
                                {"task_id": task_id, "role": role})
                return self._task_dict(self._get_row(conn, "tasks", task_id))
        finally:
            conn.close()

    def start_task(self, task_id: str, attempt_id: str, handle: dict) -> dict:
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError("attempt_id is required")
        conn = self._conn()
        try:
            with write_tx(conn):
                self._expire_tasks(conn)
                task = self._get_row(conn, "tasks", task_id)
                if task["status"] == "RUNNING":
                    raise ConflictError("task has an active attempt")
                if task["attempts"] >= 2:
                    raise ConflictError("maximum attempts reached")
                if task["attempt_id"] == attempt_id:
                    raise ConflictError("attempt_id was already used")
                cur = conn.execute(
                    "UPDATE tasks SET status = 'RUNNING', attempt_id = ?, handle = ?,"
                    " lease_until = ?, error = NULL, result = NULL, input_revision ="
                    " (SELECT revision FROM cases WHERE id = tasks.case_id), attempts = attempts + 1"
                    " WHERE id = ? AND status IN ('PENDING', 'FAILED', 'INTERRUPTED')",
                    (attempt_id, json.dumps(handle) if handle is not None else None,
                     time.time() + TASK_LEASE_SECONDS, task_id),
                )
                if cur.rowcount != 1:
                    raise ConflictError("task cannot be claimed in its current state")
                return self._task_dict(self._get_row(conn, "tasks", task_id))
        finally:
            conn.close()

    def finish_task(self, task_id: str, attempt_id: str, input_revision: int,
                    result: dict) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                task = self._get_row(conn, "tasks", task_id)
                if task["status"] != "RUNNING" or task["attempt_id"] != attempt_id:
                    raise ConflictError("no active attempt matches")
                if task["lease_until"] is not None and task["lease_until"] <= time.time():
                    raise ConflictError("worker lease expired")
                case = self._get_row(conn, "cases", task["case_id"])
                if input_revision != task["input_revision"] or input_revision != case["revision"]:
                    raise ConflictError("task input revision is stale")
                self._validate_worker_result(json.loads(case["snapshot"]), result)
                conn.execute(
                    "UPDATE tasks SET status = 'SUCCEEDED', result = ?, error = NULL WHERE id = ?",
                    (json.dumps(result, sort_keys=True), task_id),
                )
                self._add_event(conn, case["workspace_id"], case["id"], "task_succeeded",
                                self._clock(conn, case["workspace_id"]),
                                {"task_id": task_id})
                return self._task_dict(self._get_row(conn, "tasks", task_id))
        finally:
            conn.close()

    def fail_task(self, task_id: str, attempt_id: str, reason: str) -> dict:
        conn = self._conn()
        try:
            with write_tx(conn):
                task = self._get_row(conn, "tasks", task_id)
                if task["status"] != "RUNNING" or task["attempt_id"] != attempt_id:
                    raise ConflictError("no active attempt matches")
                conn.execute(
                    "UPDATE tasks SET status = 'FAILED', error = ? WHERE id = ?",
                    (reason, task_id),
                )
                return self._task_dict(self._get_row(conn, "tasks", task_id))
        finally:
            conn.close()

    def _validate_worker_result(self, snapshot: dict, result: dict) -> None:
        if not isinstance(result, dict):
            raise ValueError("worker result must be an object")
        if set(result.keys()) != {"summary", "evidence_ids",
                                  "affected_order_ids", "shortage_units"}:
            raise ValueError("worker result keys must be exactly the contract fields")
        if not isinstance(result["summary"], str) or not result["summary"].strip() \
                or len(result["summary"]) > 2000:
            raise ValueError("worker result requires a nonblank summary of at most 2000 characters")
        evidence_ids = {e["id"] for e in snapshot["evidence"]}
        supplied = result["evidence_ids"]
        if not isinstance(supplied, list) or not supplied \
                or not all(isinstance(i, str) for i in supplied) \
                or len(supplied) != len(set(supplied)) \
                or not all(i in evidence_ids for i in supplied):
            raise ValueError("worker result references unknown evidence ids")
        order_ids = {snapshot["replacement_id"], snapshot["sales_order_id"]}
        affected = result["affected_order_ids"]
        if not isinstance(affected, list) \
                or not all(isinstance(i, str) for i in affected) \
                or len(affected) != len(set(affected)) \
                or set(affected) != order_ids:
            raise ValueError("worker result must list exactly the affected orders")
        expected_shortage = max(0, snapshot["replacement_units"] + snapshot["sales_units"]
                                - snapshot["stock_units"])
        if not isinstance(result["shortage_units"], int) \
                or isinstance(result["shortage_units"], bool) \
                or result["shortage_units"] != expected_shortage:
            raise ValueError("worker result shortage does not match snapshot")

    def _check_revision(self, case, expected: int | None) -> None:
        if expected is not None and expected != case["revision"]:
            raise ConflictError(
                f"stale revision {expected}, current {case['revision']}")

    def _clock(self, conn, workspace_id: str) -> int:
        return conn.execute(
            "SELECT clock_hour FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()[0]

    def _clock_by_id(self, workspace_id: str) -> int:
        conn = self._conn()
        try:
            return self._clock(conn, workspace_id)
        finally:
            conn.close()

    def _task_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "case_id": row["case_id"],
            "role": row["role"],
            "status": row["status"],
            "input_revision": row["input_revision"],
            "attempt_id": row["attempt_id"],
            "attempts": row["attempts"],
            "lease_until": row["lease_until"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
        }

    def _case_dict(self, conn, case_id: str) -> dict:
        case = self._get_row(conn, "cases", case_id)
        snapshot = json.loads(case["snapshot"])
        correction = conn.execute(
            "SELECT * FROM corrections WHERE case_id = ?", (case_id,)
        ).fetchone()
        return {
            "id": case["id"],
            "workspace_id": case["workspace_id"],
            "title": case["title"],
            "state": case["state"],
            "revision": case["revision"],
            "synthetic": True,
            "policy_version": case["policy_version"],
            "clock_hour": self._clock(conn, case["workspace_id"]),
            "snapshot": snapshot,
            "evidence": snapshot["evidence"],
            "obligations": [
                {"id": o["id"], "kind": o["kind"], "source_id": o["source_id"],
                 "due_hour": o["due_hour"], "status": o["status"]}
                for o in conn.execute(
                    "SELECT * FROM obligations WHERE case_id = ?", (case_id,)
                ).fetchall()
            ],
            "options": json.loads(case["options"]) if case["options"] else [],
            "selected_plan_id": case["selected_plan_id"],
            "attention_reasons": json.loads(case["attention_reasons"]) if case["attention_reasons"] else [],
            "reservations": [
                {"id": r["id"], "kind": r["kind"], "qty": r["qty"],
                 "start_hour": r["start_hour"], "end_hour": r["end_hour"],
                 "state": r["state"]}
                for r in conn.execute(
                    "SELECT * FROM reservations WHERE case_id = ?", (case_id,)
                ).fetchall()
            ],
            "tasks": [
                self._task_dict(t) for t in conn.execute(
                    "SELECT * FROM tasks WHERE case_id = ?", (case_id,)
                ).fetchall()
            ],
            "actions": [
                {"id": a["id"], "idempotency_key": a["idempotency_key"],
                 "connector": a["connector"], "payload": json.loads(a["payload"]),
                 "payload_hash": a["payload_hash"], "status": a["status"],
                 "external_ref": a["external_ref"],
                 "attempts": [
                     {"id": t["id"], "n": t["n"], "status": t["status"],
                      "detail": t["detail"]}
                     for t in conn.execute(
                         "SELECT * FROM action_attempts WHERE action_id = ? ORDER BY n",
                         (a["id"],),
                     ).fetchall()
                 ]}
                for a in conn.execute(
                    "SELECT * FROM actions WHERE case_id = ?", (case_id,)
                ).fetchall()
            ],
            "events": [
                {"id": e["id"], "kind": e["kind"], "at_hour": e["at_hour"],
                 "payload": json.loads(e["payload"])}
                for e in conn.execute(
                    "SELECT * FROM events WHERE case_id = ? ORDER BY at_hour, rowid",
                    (case_id,),
                ).fetchall()
            ],
            "evaluation": json.loads(case["evaluation"]) if case["evaluation"] else None,
            "correction": (
                {"id": correction["id"], "state": correction["state"],
                 "prev_version": correction["prev_version"],
                 "new_version": correction["new_version"],
                 "evidence": json.loads(correction["evidence"]),
                 "proposal": json.loads(correction["proposal"])}
                if correction else None
            ),
        }
