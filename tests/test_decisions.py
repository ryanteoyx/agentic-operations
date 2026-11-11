from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "hermes_ops"))

from manufacturing_ops import ConflictError, OpsService
from manufacturing_ops import decision
from manufacturing_ops.service import validate_snapshot


def option_map(case):
    return {o["id"]: o for o in case["options"]}


class DecisionV1Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.service = OpsService(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def test_v1_options_and_economy_prediction(self):
        case = self.service.seed_demo()
        self.assertEqual(case["state"], "OPEN")
        self.assertEqual(case["policy_version"], 1)
        case = self.service.plan(case["id"])
        self.assertEqual(case["state"], "READY")
        opts = option_map(case)
        self.assertTrue(opts["economy"]["feasible"])
        self.assertEqual(opts["economy"]["predicted_receipt_hour"], 24)
        self.assertEqual(opts["economy"]["predicted_sales_ship_hour"], 48)
        self.assertEqual(opts["economy"]["predicted_replacement_ship_hour"], 16)
        self.assertEqual(opts["economy"]["incremental_cost_minor"], 6000)
        self.assertEqual(opts["economy"]["purchase_value_minor"], 30000)
        self.assertTrue(opts["priority"]["feasible"])
        self.assertEqual(opts["priority"]["predicted_sales_ship_hour"], 54)
        self.assertFalse(opts["wait"]["feasible"])
        self.assertFalse(opts["unapproved"]["feasible"])
        self.assertIn("Supplier is not approved", opts["unapproved"]["reasons"])
        selected = self.service.select_plan(case["id"], "economy", case["revision"])
        self.assertEqual(selected["selected_plan_id"], "economy")
        self.assertEqual(len(selected["actions"]), 1)
        self.assertEqual(selected["actions"][0]["status"], "PREPARED")

    def test_replan_and_reselect_after_selection_rejected(self):
        case = self.service.seed_demo()
        case = self.service.plan(case["id"])
        case = self.service.select_plan(case["id"], "economy", case["revision"])
        with self.assertRaises(ConflictError):
            self.service.plan(case["id"])
        with self.assertRaises(ConflictError):
            self.service.select_plan(case["id"], "economy", case["revision"])
        with self.assertRaises(ConflictError):
            self.service.select_plan(case["id"], "priority", case["revision"])
        self.assertEqual(len(case["actions"]), 1)
        stock = [r for r in case["reservations"] if r["kind"] == "stock"]
        self.assertEqual(len(stock), 1)
        self.assertEqual(stock[0]["qty"], 6)
        self.service.execute(case["id"])
        with self.assertRaises(ConflictError):
            self.service.plan(case["id"])
        after = self.service.get_case(case["id"])
        self.assertEqual(len(after["actions"]), 1)
        self.assertEqual(after["selected_plan_id"], "economy")

    def test_planning_and_selection_require_clock_zero(self):
        case = self.service.seed_demo()
        conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"))
        conn.execute("UPDATE workspaces SET clock_hour = 5 WHERE id = ?",
                     (case["workspace_id"],))
        conn.commit()
        conn.close()
        with self.assertRaises(ConflictError):
            self.service.plan(case["id"])
        other = self.service.seed_demo()
        other = self.service.plan(other["id"])
        conn = sqlite3.connect(str(Path(self.dir.name) / "operations.db"))
        conn.execute("UPDATE workspaces SET clock_hour = 1 WHERE id = ?",
                     (other["workspace_id"],))
        conn.commit()
        conn.close()
        with self.assertRaises(ConflictError):
            self.service.select_plan(other["id"], "economy", other["revision"])

    def test_trigger_dedup_within_workspace(self):
        first = self.service.seed_demo()
        again = self.service.seed_demo(workspace_id=first["workspace_id"])
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(len(self.service.list_cases()), 1)
        other = self.service.seed_demo()
        self.assertNotEqual(other["workspace_id"], first["workspace_id"])
        self.assertEqual(len(self.service.list_cases()), 2)


class DecisionV2Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.service = OpsService(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def _activate_v2(self):
        case = self.service.seed_demo()
        case = self.service.plan(case["id"])
        case = self.service.select_plan(case["id"], "economy", case["revision"])
        self.service.execute(case["id"])
        self.service.advance(case["id"], 200)
        case = self.service.evaluate(case["id"])
        self.assertEqual(case["correction"]["state"], "proposed")
        self.service.activate_correction(case["id"], 1)

    def test_v2_selects_priority_at_54(self):
        self._activate_v2()
        case = self.service.seed_demo()
        self.assertEqual(case["policy_version"], 2)
        case = self.service.plan(case["id"])
        opts = option_map(case)
        self.assertFalse(opts["economy"]["feasible"])
        self.assertEqual(opts["economy"]["predicted_receipt_hour"], 48)
        self.assertTrue(opts["priority"]["feasible"])
        self.assertEqual(opts["priority"]["predicted_sales_ship_hour"], 54)
        feasible = [o["id"] for o in case["options"] if o["feasible"]]
        self.assertEqual(feasible, ["priority"])

    def test_no_feasible_when_limit_below_priority_cost(self):
        fixture = json.loads(
            (Path(__file__).resolve().parents[1]
             / "plugin" / "hermes_ops" / "manufacturing_ops" / "sim" / "manufacturer.json"
             ).read_text())
        fixture["expedite_limit_minor"] = 13999
        opts = decision.build_options(fixture, 2)
        self.assertFalse(any(o["feasible"] for o in opts))
        priority = next(o for o in opts if o["id"] == "priority")
        self.assertIn("Incremental spend exceeds delegated authority", priority["reasons"])


class SnapshotValidationTests(unittest.TestCase):
    def _fixture(self):
        return json.loads(
            (Path(__file__).resolve().parents[1]
             / "plugin" / "hermes_ops" / "manufacturing_ops" / "sim" / "manufacturer.json"
             ).read_text())

    def test_valid_fixture_passes(self):
        self.assertEqual(validate_snapshot(self._fixture())["company"], "Orange")

    def test_negative_stock_rejected(self):
        s = self._fixture()
        s["stock_units"] = -1
        with self.assertRaises(ValueError):
            validate_snapshot(s)

    def test_missing_supplier_id_rejected(self):
        s = self._fixture()
        del s["suppliers"][0]["id"]
        with self.assertRaises(ValueError):
            validate_snapshot(s)

    def test_invalid_unit_and_scenario_rejected(self):
        s = self._fixture()
        s["unit"] = "box"
        with self.assertRaises(ValueError):
            validate_snapshot(s)
        s = self._fixture()
        s["scenario_id"] = "other"
        with self.assertRaises(ValueError):
            validate_snapshot(s)
        s = self._fixture()
        s["synthetic"] = False
        with self.assertRaises(ValueError):
            validate_snapshot(s)
        s = self._fixture()
        s["components_per_unit"] = 2
        with self.assertRaises(ValueError):
            validate_snapshot(s)

    def test_unknown_seed_scenario_rejected(self):
        service = OpsService(Path(tempfile.mkdtemp()))
        with self.assertRaises(ValueError):
            service.seed_demo(scenario_id="other")

    def test_noninteger_quantity_rejected(self):
        s = self._fixture()
        s["sales_units"] = "8"
        with self.assertRaises(ValueError):
            validate_snapshot(s)


class ReservationRaceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def _sibling_case(self, workspace_id: str, trigger_suffix: str) -> str:
        db = self.dir_path / "operations.db"
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT snapshot, policy_version FROM cases WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            case_id = "sibling-" + trigger_suffix
            conn.execute(
                "INSERT INTO cases (id, workspace_id, title, state, revision, trigger_key, policy_version, snapshot, created_hour)"
                " VALUES (?, ?, ?, 'OPEN', 1, ?, ?, ?, 0)",
                (case_id, workspace_id, "sibling case", "trigger:" + trigger_suffix,
                 row[1], row[0]),
            )
            conn.commit()
            return case_id
        finally:
            conn.close()

    def test_same_workspace_stock_reserved_once(self):
        service_a = OpsService(self.dir_path)
        service_b = OpsService(self.dir_path)
        first = service_a.seed_demo()
        second_id = self._sibling_case(first["workspace_id"], "b")
        first = service_a.plan(first["id"])
        second = service_b.plan(second_id)
        first = service_a.select_plan(first["id"], "economy", first["revision"])
        stock = [r for r in first["reservations"] if r["kind"] == "stock"]
        self.assertEqual(stock[0]["qty"], 6)
        with self.assertRaises(ConflictError):
            service_b.select_plan(second["id"], "priority", second["revision"])

    def test_partial_stock_availability_rejected_cleanly(self):
        service = OpsService(self.dir_path)
        case = service.seed_demo()
        conn = sqlite3.connect(str(self.dir_path / "operations.db"))
        conn.execute("UPDATE workspaces SET stock_units = 5")
        conn.commit()
        conn.close()
        case = service.plan(case["id"])
        with self.assertRaises(ConflictError):
            service.select_plan(case["id"], "economy", case["revision"])
        after = service.get_case(case["id"])
        self.assertEqual(after["reservations"], [])
        self.assertEqual(after["actions"], [])
        self.assertIsNone(after["selected_plan_id"])

    def test_assembly_interval_conflict_with_sufficient_stock(self):
        service_a = OpsService(self.dir_path)
        service_b = OpsService(self.dir_path)
        first = service_a.seed_demo()
        conn = sqlite3.connect(str(self.dir_path / "operations.db"))
        conn.execute("UPDATE workspaces SET stock_units = 12")
        conn.commit()
        conn.close()
        second_id = self._sibling_case(first["workspace_id"], "cap")
        first = service_a.plan(first["id"])
        second = service_b.plan(second_id)
        service_a.select_plan(first["id"], "economy", first["revision"])
        with self.assertRaises(ConflictError):
            service_b.select_plan(second["id"], "priority", second["revision"])

    def test_concurrent_select_reserves_stock_once(self):
        service_a = OpsService(self.dir_path)
        service_b = OpsService(self.dir_path)
        first = service_a.seed_demo()
        second_id = self._sibling_case(first["workspace_id"], "race")
        first = service_a.plan(first["id"])
        second = service_b.plan(second_id)
        barrier = threading.Barrier(3)
        results = {}

        def attempt(service, case_id, plan_id, rev, name):
            barrier.wait()
            try:
                service.select_plan(case_id, plan_id, rev)
                results[name] = "ok"
            except ConflictError:
                results[name] = "conflict"

        t1 = threading.Thread(target=attempt, args=(
            service_a, first["id"], "economy", first["revision"], "a"))
        t2 = threading.Thread(target=attempt, args=(
            service_b, second_id, "priority", second["revision"], "b"))
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()
        self.assertEqual(sorted(results.values()), ["conflict", "ok"])
        conn = sqlite3.connect(str(self.dir_path / "operations.db"))
        rows = conn.execute(
            "SELECT qty FROM reservations WHERE kind = 'stock' AND state = 'HELD'"
        ).fetchall()
        conn.close()
        self.assertEqual([r[0] for r in rows], [6])

    def test_stale_revision_select_rejected(self):
        service = OpsService(self.dir_path)
        case = service.seed_demo()
        case = service.plan(case["id"])
        with self.assertRaises(ConflictError):
            service.select_plan(case["id"], "economy", case["revision"] + 9)
        with self.assertRaises(ValueError):
            service.select_plan(case["id"], "unapproved", case["revision"])


if __name__ == "__main__":
    unittest.main()
