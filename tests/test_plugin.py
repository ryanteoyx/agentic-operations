from __future__ import annotations

import contextvars
import http.client
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module_at(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Context:
    def __init__(self, llm=None):
        self.tools = {}
        self.commands = {}
        self.llm = llm

    def register_tool(self, **tool):
        self.tools[tool["name"]] = tool

    def register_cli_command(self, **command):
        self.commands[command["name"]] = command


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = tempfile.TemporaryDirectory(prefix="ops-installed-test-")
        cls.root = Path(cls.bundle.name)
        cls.plugin = cls.root / "plugin" / "hermes_ops"
        shutil.copytree(ROOT / "plugin" / "hermes_ops", cls.plugin)
        if not (cls.plugin / "manufacturing_ops" / "service.py").exists():
            external = os.environ.get("OPS_TEST_CORE_DIR")
            if not external:
                cls.bundle.cleanup()
                raise unittest.SkipTest("Core not integrated yet; set OPS_TEST_CORE_DIR to the actual manufacturing_ops package")
            source = Path(external)
            if not (source / "service.py").is_file():
                raise RuntimeError("OPS_TEST_CORE_DIR must contain the actual core service.py")
            shutil.copytree(source, cls.plugin / "manufacturing_ops", dirs_exist_ok=True)
            for name in ("tools.py", "workers.py", "cli.py"):
                shutil.copy2(ROOT / "plugin" / "hermes_ops" / "manufacturing_ops" / name, cls.plugin / "manufacturing_ops" / name)
        shutil.copytree(ROOT / "demo", cls.root / "demo")
        cls.entry = module_at("ops_test_installed", cls.plugin / "__init__.py", package=True)
        cls.runtime = sys.modules["ops_test_installed.runtime_loader"]
        cls.core = cls.runtime.load_core()
        cls.serve = module_at("ops_test_serve", cls.root / "demo" / "serve.py")

    @classmethod
    def tearDownClass(cls):
        cls.bundle.cleanup()

    def setUp(self):
        self.data = tempfile.TemporaryDirectory(prefix="ops-data-test-")
        self.addCleanup(self.data.cleanup)
        self.ops = self.core.OpsService(Path(self.data.name))

    def test_installed_loader_is_cached_and_does_not_modify_sys_path(self):
        before = list(sys.path)
        self.assertIs(self.core, self.runtime.load_core())
        independent = module_at("ops_test_dashboard", self.plugin / "dashboard" / "plugin_api.py")
        self.assertIs(independent.runtime.load_core(), self.core)
        self.assertEqual(before, sys.path)
        self.assertTrue(str(Path(self.core.__file__).resolve()).startswith(str(self.plugin.resolve())))
        with tempfile.TemporaryDirectory() as separate:
            installed = Path(separate) / "hermes_ops"
            shutil.copytree(self.plugin, installed)
            other = module_at("ops_test_separate_runtime", installed / "runtime_loader.py")
            self.assertIsNot(other.load_core(), self.core)
            self.assertIs(other.load_core(), other.load_core())
            self.assertEqual(before, sys.path)

    def test_registration_and_all_tool_contracts(self):
        ctx = Context()
        self.entry.register(ctx)
        self.assertEqual(set(ctx.tools), {
            "ops_seed_demo", "ops_list_cases", "ops_case", "ops_investigate", "ops_plan",
            "ops_select_plan", "ops_execute", "ops_reconcile", "ops_advance_demo",
            "ops_evaluate", "ops_activate_correction",
        })
        self.assertIn("ops", ctx.commands)
        for tool in ctx.tools.values():
            self.assertFalse(tool["schema"]["parameters"]["additionalProperties"])
            self.assertNotIn("crash_after_external", json.dumps(tool["schema"]))
        storage = types.ModuleType("plugins.plugin_storage")
        profile = contextvars.ContextVar("test_profile", default=Path(self.data.name))
        requested = []

        def plugin_data_dir(name):
            requested.append(name)
            return profile.get()

        storage.plugin_data_dir = plugin_data_dir
        with patch.dict(sys.modules, {"plugins": types.ModuleType("plugins"), "plugins.plugin_storage": storage}):
            case = json.loads(ctx.tools["ops_seed_demo"]["handler"]({}))
            self.assertTrue(case["synthetic"])
            self.assertEqual(len(json.loads(ctx.tools["ops_list_cases"]["handler"]({}))), 1)
            with tempfile.TemporaryDirectory() as other:
                token = profile.set(Path(other))
                try:
                    self.assertEqual(json.loads(ctx.tools["ops_list_cases"]["handler"]({})), [])
                finally:
                    profile.reset(token)
            self.assertEqual(len(json.loads(ctx.tools["ops_list_cases"]["handler"]({}))), 1)
            error = json.loads(ctx.tools["ops_execute"]["handler"]({"case_id": case["id"], "crash_after_external": True}))
            self.assertEqual(error["status"], 422)
        self.assertTrue(requested)
        self.assertEqual(set(requested), {"agentic-operations"})

    def test_validation_is_closed_and_typed(self):
        for operation, arguments in (
            ("advance", {"case_id": "x", "hours": True}),
            ("advance", {"case_id": "x", "hours": -1}),
            ("advance", {"case_id": "x", "hours": 8761}),
            ("select", {"case_id": "x", "plan_id": "economy"}),
            ("seed", {"scenario_id": "real-company"}),
            ("case", {"case_id": "../other"}),
            ("execute", {"case_id": "x", "crash_after_external": True}),
        ):
            with self.subTest(operation=operation, arguments=arguments):
                with self.assertRaises(ValueError):
                    self.runtime.validate(operation, arguments)
        for raw in ('{"hours":1,"hours":2}', '{"hours":NaN}', "[] trailing"):
            with self.assertRaises(ValueError):
                self.runtime.strict_json(raw)

    def test_tools_hide_future_supplier_cutoff_without_removing_observed_evidence(self):
        ctx = Context()
        self.entry.register(ctx)
        storage = types.ModuleType("plugins.plugin_storage")
        storage.plugin_data_dir = lambda name: Path(self.data.name)

        def call(name, **arguments):
            return json.loads(ctx.tools[name]["handler"](arguments))

        with patch.dict(sys.modules, {"plugins": types.ModuleType("plugins"), "plugins.plugin_storage": storage}):
            case = call("ops_seed_demo")
            raw = self.ops.get_case(case["id"])
            self.assertTrue(any(s["cutoff_delay_hours"] > 0 for s in raw["snapshot"]["suppliers"]))
            self.assertTrue(all("cutoff_delay_hours" not in s for s in case["snapshot"]["suppliers"]))
            self.assertEqual(self.runtime.public_data(raw), case)
            self.assertTrue(all("cutoff_delay_hours" in s for s in raw["snapshot"]["suppliers"]))
            self.assertEqual(raw["snapshot"], self.ops.get_case(case["id"])["snapshot"])
            case = call("ops_plan", case_id=case["id"], expected_revision=case["revision"])
            case = call("ops_select_plan", case_id=case["id"], plan_id="economy", expected_revision=case["revision"])
            case = call("ops_execute", case_id=case["id"])
            self.assertEqual(case["actions"][0]["status"], "CONFIRMED")
            cutoff = next(e for e in case["events"] if e["kind"] == "supplier_cutoff_confirmed")
            self.assertEqual(cutoff["payload"]["cutoff_delay_hours"], 24)
            self.assertTrue(cutoff["payload"]["source_po"])
            call("ops_advance_demo", case_id=case["id"], hours=96)
            case = call("ops_evaluate", case_id=case["id"])
            self.assertEqual(case["correction"]["evidence"]["cutoff_delay_hours"], 24)
            self.assertEqual(case["correction"]["proposal"]["cutoff_delay_hours"], 24)
            self.assertTrue(all("cutoff_delay_hours" not in s for s in case["snapshot"]["suppliers"]))
            self.assertTrue(all("cutoff_delay_hours" in s for s in self.ops.get_case(case["id"])["snapshot"]["suppliers"]))

    def test_python_cli_runs_outside_repository(self):
        env = {**os.environ, "PYTHONPATH": str(self.plugin.parent), "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "hermes_ops.manufacturing_ops.cli", "--data-dir", self.data.name, "seed"],
            cwd=self.data.name, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["synthetic"])

    def test_fastapi_routes_if_host_dependencies_are_available(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("Host FastAPI/test client dependencies unavailable; stdlib HTTP integration is covered")
        dashboard = module_at("ops_test_fastapi", self.plugin / "dashboard" / "plugin_api.py")
        app = FastAPI()
        app.include_router(dashboard.router, prefix=dashboard.API_PREFIX)
        storage = types.ModuleType("plugins.plugin_storage")
        storage.plugin_data_dir = lambda name: Path(self.data.name)
        with patch.dict(sys.modules, {"plugins": types.ModuleType("plugins"), "plugins.plugin_storage": storage}):
            with TestClient(app) as client:
                ui = client.get(dashboard.API_PREFIX + "/ui")
                self.assertEqual(ui.status_code, 200)
                config = json.loads(re.search(r"const CONFIG = (.*?);", ui.text)[1])
                self.assertEqual(config["api"], dashboard.API_PREFIX)
                url = dashboard.API_PREFIX + "/demo/seed"
                self.assertEqual(client.post(url, json={}).status_code, 403)
                headers = {"X-Ops-CSRF": config["csrf"], "Origin": "http://testserver"}
                case = client.post(url, json={}, headers=headers)
                self.assertEqual(case.status_code, 200, case.text)
                self.assertTrue(case.json()["synthetic"])
                self.assertTrue(all("cutoff_delay_hours" not in s for s in case.json()["snapshot"]["suppliers"]))
                self.assertEqual(client.get(dashboard.API_PREFIX + "/cases").json()[0]["id"], case.json()["id"])
                self.assertEqual(client.post(url, json={}, headers={**headers, "Origin": "https://foreign.invalid"}).status_code, 403)
                self.assertEqual(client.post(url, json={"blob": "x" * 65536}, headers=headers).status_code, 413)

    def start_server(self):
        server = self.serve.create_server(self.data.name, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.server = server
        status, html, headers = self.request("GET", "/", parse=False)
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["Cache-Control"])
        match = re.search(r"const CONFIG = (.*?);", html)
        self.csrf = json.loads(match[1])["csrf"]
        return server

    def request(self, method, path, body=None, headers=None, parse=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        effective = {"Content-Type": "application/json"}
        if hasattr(self, "csrf"):
            effective["X-Ops-CSRF"] = self.csrf
        effective.update(headers or {})
        raw = json.dumps(body).encode() if body is not None else None
        connection.request(method, path, body=raw, headers=effective)
        response = connection.getresponse()
        data = response.read().decode()
        result = (response.status, json.loads(data) if parse else data, dict(response.getheaders()))
        connection.close()
        return result

    def post(self, path, body=None):
        status, payload, _ = self.request("POST", path, {} if body is None else body)
        self.assertEqual(status, 200, payload)
        return payload

    def test_real_http_v1_correction_v2_workflow(self):
        self.start_server()
        status, health, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["synthetic"])
        first = self.post("/api/demo/seed")
        self.assertTrue(all("cutoff_delay_hours" not in s for s in first["snapshot"]["suppliers"]))
        self.assertTrue(all("cutoff_delay_hours" in s for s in self.ops.get_case(first["id"])["snapshot"]["suppliers"]))

        def workflow(case, plan_id, receipt, sales):
            base = "/api/cases/" + case["id"]
            case = self.post(base + "/plan", {"expected_revision": case["revision"]})
            option = next(o for o in case["options"] if o["id"] == plan_id)
            self.assertTrue(option["feasible"])
            self.assertEqual(option["predicted_receipt_hour"], receipt)
            case = self.post(base + "/select", {"plan_id": plan_id, "expected_revision": case["revision"]})
            case = self.post(base + "/execute")
            action = case["actions"][0]
            if plan_id == "economy":
                cutoff = next(e for e in case["events"] if e["kind"] == "supplier_cutoff_confirmed")
                self.assertEqual(cutoff["payload"]["cutoff_delay_hours"], 24)
            repeated = self.post(base + "/execute")
            self.assertEqual(action["external_ref"], repeated["actions"][0]["external_ref"])
            self.post(base + "/reconcile")
            self.post(base + "/advance", {"hours": 96})
            result = self.post(base + "/evaluate")
            self.assertTrue(result["evaluation"]["complete"])
            self.assertEqual(result["evaluation"]["actual_sales_ship_hour"], sales)
            return result

        first = workflow(first, "economy", 24, 72)
        self.assertEqual(first["evaluation"]["sales_forecast_error_hours"], 24)
        self.assertEqual(first["evaluation"]["sales_late_hours"], 12)
        self.assertEqual(first["correction"]["evidence"]["cutoff_delay_hours"], 24)
        self.assertEqual(first["correction"]["proposal"]["cutoff_delay_hours"], 24)
        self.post("/api/cases/" + first["id"] + "/correction", {"expected_policy_version": 1})
        second = self.post("/api/demo/seed")
        self.assertEqual(second["policy_version"], 2)
        second = workflow(second, "priority", 30, 54)
        self.assertEqual(second["evaluation"]["sales_late_hours"], 0)
        status, preserved, _ = self.request("GET", "/api/cases/" + first["id"])
        self.assertEqual(status, 200)
        self.assertEqual(preserved["evaluation"]["predicted_sales_ship_hour"], 48)

    def test_http_security_and_error_mapping(self):
        self.start_server()
        self.assertEqual(self.request("GET", "/api/health", headers={"Host": "attacker.invalid"})[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Origin": "https://attacker.invalid"}, parse=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/demo/seed", {}, {"X-Ops-CSRF": ""})[0], 403)
        self.assertEqual(self.request("POST", "/api/demo/seed", {}, {"Origin": "http://localhost:9999"})[0], 403)
        self.assertEqual(self.request("POST", "/api/demo/seed", {"padding": "x" * 65536})[0], 413)
        self.assertEqual(self.request("POST", "/api/demo/seed", {}, {"Content-Type": "text/plain"})[0], 415)
        case = self.post("/api/demo/seed")
        base = "/api/cases/" + case["id"]
        self.assertEqual(self.request("GET", "/api/cases/unknown")[0], 404)
        self.assertEqual(self.request("POST", base + "/advance", {"hours": -1})[0], 422)
        self.assertEqual(self.request("POST", base + "/execute", {"crash_after_external": True})[0], 422)
        self.assertEqual(self.request("POST", base + "/investigate", {})[0], 404)
        self.post(base + "/plan", {"expected_revision": case["revision"]})
        self.assertEqual(self.request("POST", base + "/plan", {"expected_revision": case["revision"]})[0], 409)
        _, _, headers = self.request("GET", "/api/cases")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_worker_has_minimal_input_and_durable_task_before_call(self):
        self.entry.register(Context())
        workers = sys.modules[self.core.__name__ + ".workers"]
        case = self.ops.seed_demo()
        supplied = workers.worker_input(case)
        self.assertEqual(set(supplied), {"evidence", "stock_units", "orders", "bom"})
        self.assertNotIn("cutoff", json.dumps(supplied).lower())
        self.assertNotIn("suppliers", supplied)
        expected = {
            "summary": "Twelve assemblies require twelve components; six usable components leave a shortage of six.",
            "evidence_ids": ["supplier-delay", "bom-a", "stock-ctrl-01"],
            "affected_order_ids": ["WR-104", "SO-208"], "shortage_units": 6,
        }
        outer = self

        class LLM:
            def complete_structured(self, **kwargs):
                tasks = outer.ops.get_case(case["id"])["tasks"]
                outer.assertEqual(tasks[0]["status"], "RUNNING")
                outer.assertTrue(tasks[0]["attempt_id"])
                outer.assertEqual(kwargs["instructions"], workers.WORKER_PROMPT)
                outer.assertEqual(kwargs["timeout"], 60)
                outer.assertEqual(json.loads(kwargs["input"][0]["text"]), supplied)
                outer.assertNotIn("tools", kwargs)
                return types.SimpleNamespace(text=json.dumps(expected))

        result = workers.investigate(Context(LLM()), self.ops, case["id"])
        self.assertFalse(result["actual_subagent"])
        self.assertEqual(result["task"]["status"], "SUCCEEDED")
        self.assertEqual(result["task"]["result"], expected)
        self.assertNotIn("handle", result["task"])
        for invalid in (
            {**expected, "shortage_units": True},
            {**expected, "affected_order_ids": ["WR-104"]},
            {**expected, "evidence_ids": ["hidden-cutoff"]},
            {**expected, "execute": True},
        ):
            with self.assertRaises(ValueError):
                workers.validate_result(json.dumps(invalid), supplied)
        with self.assertRaises(ValueError):
            workers.validate_result("```json\n" + json.dumps(expected) + "\n```", supplied)

    def test_worker_unavailable_timeout_and_stale_results_are_failed(self):
        self.entry.register(Context())
        workers = sys.modules[self.core.__name__ + ".workers"]
        case = self.ops.seed_demo()
        missing = workers.investigate(Context(), self.ops, case["id"])
        self.assertEqual(missing["task"]["status"], "FAILED")

        class Slow:
            def complete_structured(self, **kwargs):
                time.sleep(.1)
                return types.SimpleNamespace(text="{}")

        with patch.object(workers, "WAIT_SECONDS", .01):
            timed_out = workers.investigate(Context(Slow()), self.ops, case["id"])
        self.assertEqual(timed_out["task"]["status"], "FAILED")
        ops = self.ops

        class Stale:
            def complete_structured(self, **kwargs):
                ops.plan(case["id"])
                return types.SimpleNamespace(text=json.dumps({
                    "summary": "Six components are missing.", "evidence_ids": ["stock-ctrl-01"],
                    "affected_order_ids": ["WR-104", "SO-208"], "shortage_units": 6,
                }))

        stale = workers.investigate(Context(Stale()), self.ops, case["id"])
        self.assertEqual(stale["task"]["status"], "FAILED")
        self.assertIn("stale", stale["task"]["error"])
        time.sleep(.12)
        self.assertTrue(all(t["status"] == "FAILED" for t in self.ops.get_case(case["id"])["tasks"]))


if __name__ == "__main__":
    unittest.main()
