from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin" / "hermes_ops"))

from manufacturing_ops import ConflictError, OpsService


def run_case(service: OpsService, plan_id: str):
    case = service.seed_demo()
    case = service.plan(case["id"])
    case = service.select_plan(case["id"], plan_id, case["revision"])
    service.execute(case["id"])
    service.advance(case["id"], 200)
    return service.get_case(case["id"])


class OutcomeV1Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.service = OpsService(Path(self.dir.name))
        self.case = run_case(self.service, "economy")

    def tearDown(self):
        self.dir.cleanup()

    def test_v1_outcome_values(self):
        case = self.service.evaluate(self.case["id"])
        ev = case["evaluation"]
        self.assertTrue(ev["complete"])
        self.assertEqual(ev["actual_receipt_hour"], 48)
        self.assertEqual(ev["actual_sales_ship_hour"], 72)
        self.assertEqual(ev["sales_forecast_error_hours"], 24)
        self.assertEqual(ev["sales_late_hours"], 12)
        self.assertFalse(ev["sales_on_time"])
        self.assertTrue(ev["replacement_on_time"])
        self.assertEqual(case["state"], "CLOSED")

    def test_incomplete_evidence_is_explicit(self):
        service = OpsService(Path(self.dir.name) / "partial")
        case = service.seed_demo()
        case = service.plan(case["id"])
        service.select_plan(case["id"], "economy", case["revision"])
        service.execute(case["id"])
        service.advance(case["id"], 16)
        ev = service.evaluate(case["id"])["evaluation"]
        self.assertFalse(ev["complete"])
        self.assertIn("receipt_hour", ev["missing"])
        self.assertIn("sales_ship_hour", ev["missing"])

    def test_correction_proposed_and_activated(self):
        case = self.service.evaluate(self.case["id"])
        self.assertEqual(case["correction"]["state"], "proposed")
        self.assertEqual(case["correction"]["prev_version"], 1)
        case = self.service.activate_correction(self.case["id"], 1)
        self.assertEqual(case["correction"]["state"], "activated")
        self.assertEqual(case["correction"]["new_version"], 2)
        self.assertEqual(self.service.playbook()["active_version"], 2)
        prediction = self.service.get_case(self.case["id"])["evaluation"]
        self.assertEqual(prediction["predicted_sales_ship_hour"], 48)

    def test_stale_policy_version_rejected(self):
        self.service.evaluate(self.case["id"])
        with self.assertRaises(ConflictError):
            self.service.activate_correction(self.case["id"], 7)


    def test_second_v1_correction_cannot_activate(self):
        self.service.evaluate(self.case["id"])
        other = run_case(self.service, "economy")
        other = self.service.evaluate(other["id"])
        self.assertEqual(other["correction"]["state"], "proposed")
        self.service.activate_correction(self.case["id"], 1)
        with self.assertRaises(ConflictError):
            self.service.activate_correction(other["id"], 2)
        with self.assertRaises(ConflictError):
            self.service.activate_correction(other["id"], 1)
        self.assertEqual(self.service.playbook()["active_version"], 2)

    def test_correction_evidence_references_events(self):
        case = self.service.evaluate(self.case["id"])
        evidence = case["correction"]["evidence"]
        event_ids = {e["id"] for e in case["events"]}
        self.assertTrue(set(evidence["event_ids"]).issubset(event_ids))
        self.assertEqual(evidence["supplier_id"], "SUP-ECO")


class OutcomeV2Tests(unittest.TestCase):
    def test_v2_priority_outcome_and_preserved_v1_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = OpsService(Path(tmp))
            v1 = run_case(service, "economy")
            v1 = service.evaluate(v1["id"])
            service.activate_correction(v1["id"], 1)
            v2 = run_case(service, "priority")
            v2 = service.evaluate(v2["id"])
            ev = v2["evaluation"]
            self.assertEqual(v2["policy_version"], 2)
            self.assertEqual(ev["actual_sales_ship_hour"], 54)
            self.assertEqual(ev["sales_forecast_error_hours"], 0)
            self.assertEqual(ev["sales_late_hours"], 0)
            self.assertTrue(ev["sales_on_time"])
            old = service.get_case(v1["id"])
            self.assertEqual(old["evaluation"]["predicted_sales_ship_hour"], 48)


class IsolationTests(unittest.TestCase):
    def test_two_data_roots_do_not_share_state(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            sa = OpsService(Path(a))
            sb = OpsService(Path(b))
            case_a = sa.seed_demo()
            sb.seed_demo()
            self.assertEqual(len(sa.list_cases()), 1)
            self.assertEqual(len(sb.list_cases()), 1)
            with self.assertRaises(KeyError):
                sb.get_case(case_a["id"])


class WorkerTaskTests(unittest.TestCase):
    RESULT = {
        "summary": "Supplier delay creates a six unit shortage.",
        "evidence_ids": ["supplier-delay", "bom-a", "stock-ctrl-01"],
        "affected_order_ids": ["WR-104", "SO-208"],
        "shortage_units": 6,
    }

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.service = OpsService(Path(self.dir.name))
        self.case = self.service.seed_demo()

    def tearDown(self):
        self.dir.cleanup()

    def test_task_lifecycle_success(self):
        task = self.service.create_task(self.case["id"])
        self.assertEqual(task["status"], "PENDING")
        task = self.service.start_task(task["id"], "attempt-1", {"handle": "x"})
        self.assertEqual(task["status"], "RUNNING")
        task = self.service.finish_task(
            task["id"], "attempt-1", task["input_revision"], self.RESULT)
        self.assertEqual(task["status"], "SUCCEEDED")
        self.assertEqual(task["result"]["shortage_units"], 6)

    def test_invalid_result_rejected(self):
        task = self.service.create_task(self.case["id"])
        self.service.start_task(task["id"], "a1", {})
        bad = dict(self.RESULT, shortage_units=3)
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        bad = dict(self.RESULT, evidence_ids=["fabricated"])
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        bad = dict(self.RESULT, evidence_ids=[])
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        bad = dict(self.RESULT, affected_order_ids=["WR-104"])
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        bad = dict(self.RESULT, shortage_units=True)
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        bad = dict(self.RESULT, extra="field")
        with self.assertRaises(ValueError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], bad)
        current = self.service.get_case(self.case["id"])["tasks"][0]
        self.assertEqual(current["status"], "RUNNING")

    def test_stale_revision_result_rejected(self):
        task = self.service.create_task(self.case["id"])
        self.service.start_task(task["id"], "a1", {})
        with self.assertRaises(ConflictError):
            self.service.finish_task(
                task["id"], "a1", task["input_revision"] + 5, self.RESULT)

    def test_forged_current_revision_rejected(self):
        task = self.service.create_task(self.case["id"])
        started = self.service.start_task(task["id"], "a1", {})
        planned = self.service.plan(self.case["id"])
        self.assertNotEqual(planned["revision"], started["input_revision"])
        with self.assertRaises(ConflictError):
            self.service.finish_task(
                task["id"], "a1", planned["revision"], self.RESULT)

    def test_wrong_attempt_and_failure_reason(self):
        task = self.service.create_task(self.case["id"])
        self.service.start_task(task["id"], "a1", {})
        with self.assertRaises(ConflictError):
            self.service.finish_task(task["id"], "a2", task["input_revision"], self.RESULT)
        task = self.service.fail_task(task["id"], "a1", "model unavailable")
        self.assertEqual(task["status"], "FAILED")
        self.assertEqual(task["error"], "model unavailable")
        with self.assertRaises(ConflictError):
            self.service.finish_task(task["id"], "a1", task["input_revision"], self.RESULT)
        with self.assertRaises(ConflictError):
            self.service.start_task(task["id"], "a1", {})
        task = self.service.start_task(task["id"], "a2", {})
        self.assertEqual(task["status"], "RUNNING")
        self.assertEqual(task["attempts"], 2)
        self.service.fail_task(task["id"], "a2", "interrupted")
        with self.assertRaises(ConflictError):
            self.service.start_task(task["id"], "a3", {})

    def test_lease_reclaim_and_active_conflict(self):
        task = self.service.create_task(self.case["id"])
        started = self.service.start_task(task["id"], "a1", {"h": 1})
        self.assertIsNotNone(started["lease_until"])
        self.assertNotIn("handle", started)
        with self.assertRaises(ConflictError):
            self.service.start_task(task["id"], "a2", {})
        conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"))
        try:
            conn.execute("UPDATE tasks SET lease_until = ? WHERE id = ?",
                         (time.time() - 1, task["id"]))
            conn.commit()
        finally:
            conn.close()
        reopened = OpsService(Path(self.dir.name))
        tasks = reopened.get_case(self.case["id"])["tasks"]
        self.assertEqual(tasks[0]["status"], "INTERRUPTED")
        with self.assertRaises(ConflictError):
            reopened.finish_task(task["id"], "a1", started["input_revision"], self.RESULT)
        reclaimed = reopened.start_task(task["id"], "a2", {})
        self.assertEqual(reclaimed["status"], "RUNNING")
        self.assertEqual(reclaimed["attempt_id"], "a2")
        self.assertEqual(reclaimed["attempts"], 2)

    def test_task_role_and_closed_case_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_task(self.case["id"], role="planner")
        case = self.service.plan(self.case["id"])
        self.service.select_plan(self.case["id"], "economy", case["revision"])
        self.service.execute(self.case["id"])
        self.service.advance(self.case["id"], 200)
        with self.assertRaises(ConflictError):
            self.service.create_task(self.case["id"])


if __name__ == "__main__":
    unittest.main()
