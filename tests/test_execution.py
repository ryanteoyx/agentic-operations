from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin" / "hermes_ops"))

from manufacturing_ops import ConflictError, OpsService
from manufacturing_ops.execution import idempotency_key, payload_hash
from manufacturing_ops.sim.erp import SimulatedERP


def workspace_stock(data_dir: Path) -> int:
    conn = sqlite3.connect(str(Path(data_dir) / "operations.db"))
    try:
        return conn.execute("SELECT stock_units FROM workspaces").fetchone()[0]
    finally:
        conn.close()


def set_action_status(data_dir: Path, case_id: str, status: str):
    conn = sqlite3.connect(str(Path(data_dir) / "operations.db"))
    try:
        conn.execute("UPDATE actions SET status = ? WHERE case_id = ?", (status, case_id))
        conn.execute(
            "INSERT INTO action_attempts (id, action_id, n, status)"
            " SELECT 'm-' || id, id, 1, 'IN_FLIGHT' FROM actions WHERE case_id = ?",
            (case_id,),
        )
        conn.commit()
    finally:
        conn.close()


class ErpIdentityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_duplicate_key_same_payload_returns_same_po(self):
        erp = SimulatedERP(Path(self.dir.name) / "sim_erp.db")
        payload = {"type": "purchase_order", "units": 6}
        h = payload_hash(payload)
        first = erp.execute("key-1", payload, h, 0, 48)
        second = erp.execute("key-1", payload, h, 0, 48)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(erp.count_orders("key-1"), 1)

    def test_same_key_different_payload_rejected(self):
        erp = SimulatedERP(Path(self.dir.name) / "sim_erp.db")
        erp.execute("key-1", {"units": 6}, payload_hash({"units": 6}), 0, 48)
        with self.assertRaises(ValueError):
            erp.execute("key-1", {"units": 7}, payload_hash({"units": 7}), 0, 48)


class ExecutionFlowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.service = OpsService(Path(self.dir.name))
        case = self.service.seed_demo()
        self.case_id = case["id"]
        case = self.service.plan(self.case_id)
        self.service.select_plan(self.case_id, "economy", case["revision"])

    def tearDown(self):
        self.dir.cleanup()

    def test_execute_confirms_po_and_reopen_idempotent(self):
        case = self.service.execute(self.case_id)
        action = case["actions"][0]
        self.assertEqual(action["status"], "CONFIRMED")
        self.assertTrue(action["external_ref"].startswith("PO-"))
        self.assertEqual(case["state"], "OBSERVING")
        again = OpsService(Path(self.dir.name)).execute(self.case_id)
        self.assertEqual(again["actions"][0]["external_ref"], action["external_ref"])

    def test_stock_consumed_once_on_acknowledgement(self):
        case = self.service.execute(self.case_id)
        self.assertEqual(workspace_stock(self.dir.name), 0)
        stock = [r for r in case["reservations"] if r["kind"] == "stock"]
        self.assertEqual(stock[0]["state"], "CONSUMED")
        self.service.execute(self.case_id)
        self.service.reconcile(self.case_id)
        self.assertEqual(workspace_stock(self.dir.name), 0)

    def test_assembly_released_and_original_supply_arrives(self):
        self.service.execute(self.case_id)
        self.service.advance(self.case_id, 200)
        case = self.service.get_case(self.case_id)
        self.assertEqual(case["state"], "CLOSED")
        assembly = [r for r in case["reservations"] if r["kind"] == "assembly"]
        self.assertEqual(assembly[0]["state"], "RELEASED")
        self.assertEqual(workspace_stock(self.dir.name), 8)
        kinds = [e["kind"] for e in case["events"]]
        self.assertIn("original_receipt", kinds)
        self.assertIn("supplier_cutoff_confirmed", kinds)

    def test_prepared_execute_after_clock_advances_rejected(self):
        conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"))
        conn.execute("UPDATE workspaces SET clock_hour = 3")
        conn.commit()
        conn.close()
        with self.assertRaises(ConflictError):
            self.service.execute(self.case_id)

    def test_connector_exception_persists_uncertain(self):
        with patch.object(self.service.erp, "execute",
                          side_effect=RuntimeError("connector blew up")):
            with self.assertRaises(RuntimeError):
                self.service.execute(self.case_id)
        case = self.service.get_case(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "UNCERTAIN")
        self.assertEqual(case["state"], "NEEDS_ATTENTION")
        self.assertIn("connector blew up", case["attention_reasons"][0])

    def test_reconcile_unknown_outcome_fails_closed(self):
        set_action_status(self.dir.name, self.case_id, "IN_FLIGHT")
        case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "NEEDS_ATTENTION")
        self.assertEqual(case["state"], "NEEDS_ATTENTION")

    def test_reconcile_prepared_action_untouched(self):
        case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "PREPARED")
        self.assertNotEqual(case["state"], "NEEDS_ATTENTION")

    def test_reconcile_payload_mismatch_fails_closed(self):
        set_action_status(self.dir.name, self.case_id, "IN_FLIGHT")
        case = self.service.get_case(self.case_id)
        key = case["actions"][0]["idempotency_key"]
        erp = SimulatedERP(Path(self.dir.name) / "sim_erp.db")
        conn = sqlite3.connect(str(Path(self.dir.name) / "sim_erp.db"))
        try:
            conn.execute(
                "INSERT INTO purchase_orders (id, action_key, payload_hash, payload, status, receipt_hour, created_hour)"
                " VALUES ('PO-X', ?, 'deadbeef', '{}', 'CONFIRMED', 48, 0)", (key,))
            conn.commit()
        finally:
            conn.close()
        case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "NEEDS_ATTENTION")
        self.assertEqual(case["state"], "NEEDS_ATTENTION")

    def test_lookup_runs_outside_operations_write_lock(self):
        def probe(key):
            conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"),
                                   timeout=0.1)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.rollback()
            finally:
                conn.close()
            return self.service.erp.__class__.lookup(self.service.erp, key)

        self.service.execute(self.case_id)
        set_action_status(self.dir.name, self.case_id, "IN_FLIGHT")
        with patch.object(self.service.erp, "lookup", side_effect=probe):
            case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "CONFIRMED")

    def test_no_close_before_observed_events(self):
        self.service.execute(self.case_id)
        case = self.service.advance(self.case_id, 16)
        self.assertNotEqual(case["state"], "CLOSED")
        case = self.service.advance(self.case_id, 30)
        self.assertNotEqual(case["state"], "CLOSED")
        case = self.service.advance(self.case_id, 60)
        self.assertEqual(case["state"], "CLOSED")
        obligation_states = {o["source_id"]: o["status"] for o in case["obligations"]}
        self.assertEqual(obligation_states["WR-104"], "RESOLVED")
        self.assertEqual(obligation_states["SO-208"], "RESOLVED")

    def test_execute_without_selection_rejected(self):
        fresh = OpsService(Path(self.dir.name) / "other")
        case = fresh.seed_demo()
        with self.assertRaises(ConflictError):
            fresh.execute(case["id"])

    def test_advance_requires_confirmed_action_and_is_monotonic(self):
        with self.assertRaises(ConflictError):
            self.service.advance(self.case_id, 4)
        case = self.service.get_case(self.case_id)
        self.assertEqual(case["clock_hour"], 0)
        case = self.service.execute(self.case_id)
        case = self.service.advance(self.case_id, 16)
        kinds = [(e["kind"], e["at_hour"]) for e in case["events"]]
        self.assertIn(("shipment", 16), kinds)
        self.assertNotIn("erp_receipt", {e["kind"] for e in case["events"]})
        case = self.service.advance(self.case_id, 32)
        kinds = {e["kind"] for e in case["events"]}
        self.assertIn("erp_receipt", kinds)
        self.assertNotEqual(case["state"], "CLOSED")
        case = self.service.advance(self.case_id, 24)
        self.assertEqual(case["state"], "CLOSED")
        event_count = len(case["events"])
        case = self.service.advance(self.case_id, 0)
        self.assertEqual(len(case["events"]), event_count)
        self.assertEqual(case["state"], "CLOSED")
        assembly = [r for r in case["reservations"] if r["kind"] == "assembly"]
        self.assertEqual(assembly[0]["state"], "RELEASED")

    def test_uncertain_lookup_then_late_commit_reconciles(self):
        conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"))
        conn.execute("UPDATE actions SET status = 'IN_FLIGHT'")
        conn.execute("UPDATE cases SET state = 'EXECUTING'")
        conn.commit()
        conn.close()
        case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "NEEDS_ATTENTION")
        self.assertEqual(case["state"], "NEEDS_ATTENTION")
        action = self.service.get_case(self.case_id)["actions"][0]
        erp = SimulatedERP(Path(self.dir.name) / "sim_erp.db")
        erp.execute(action["idempotency_key"], action["payload"],
                    action["payload_hash"], 0, 48)
        case = self.service.reconcile(self.case_id)
        self.assertEqual(case["actions"][0]["status"], "CONFIRMED")
        self.assertEqual(case["state"], "OBSERVING")
        self.assertEqual(case["attention_reasons"], [])
        self.assertEqual(erp.count_orders(action["idempotency_key"]), 1)

class CrashRecoveryTests(unittest.TestCase):
    CHILD = (
        "import sys; sys.path.insert(0, {pkg!r});"
        "from manufacturing_ops import OpsService;"
        "s = OpsService({data!r});"
        "c = s.seed_demo();"
        "c = s.plan(c['id']);"
        "s.select_plan(c['id'], 'economy', c['revision']);"
        "s.execute(c['id'], crash_after_external=True)"
    )

    def test_hard_exit_after_erp_commit_recovers_one_po(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "profile"
            env = dict(os.environ)
            child = subprocess.run(
                [sys.executable, "-c",
                 self.CHILD.format(pkg=str(REPO / "plugin" / "hermes_ops"),
                                   data=str(data_dir))],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(child.returncode, 73, child.stderr)
            service = OpsService(data_dir)
            case = service.list_cases()[0]
            self.assertEqual(case["actions"][0]["status"], "IN_FLIGHT")
            case = service.reconcile(case["id"])
            action = case["actions"][0]
            self.assertEqual(action["status"], "CONFIRMED")
            self.assertTrue(action["external_ref"].startswith("PO-"))
            erp = SimulatedERP(data_dir / "sim_erp.db")
            self.assertEqual(
                erp.count_orders(action["idempotency_key"]), 1)
            self.assertIn("reconciled", {e["kind"] for e in case["events"]})
            again = service.reconcile(case["id"])
            self.assertEqual(
                again["actions"][0]["external_ref"], action["external_ref"])


if __name__ == "__main__":
    unittest.main()
