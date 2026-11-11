from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import threading
import types
from pathlib import Path

PLUGIN_ID = "agentic-operations"
PLUGIN_ROOT = Path(__file__).resolve().parent
BODY_LIMIT = 65536
ID_FIELD = {"type": "string", "minLength": 1, "maxLength": 128, "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"}
REV_FIELD = {"type": "integer", "minimum": 1, "maximum": 2147483647}
SCHEMAS = {
    "seed": ({"scenario_id": {"type": "string", "enum": ["cutoff"]}, "workspace_id": ID_FIELD}, ()),
    "list": ({}, ()),
    "case": ({"case_id": ID_FIELD}, ("case_id",)),
    "investigate": ({"case_id": ID_FIELD}, ("case_id",)),
    "plan": ({"case_id": ID_FIELD, "expected_revision": REV_FIELD}, ("case_id",)),
    "select": ({"case_id": ID_FIELD, "plan_id": ID_FIELD, "expected_revision": REV_FIELD}, ("case_id", "plan_id", "expected_revision")),
    "execute": ({"case_id": ID_FIELD}, ("case_id",)),
    "reconcile": ({"case_id": ID_FIELD}, ("case_id",)),
    "advance": ({"case_id": ID_FIELD, "hours": {"type": "integer", "minimum": 0, "maximum": 8760}}, ("case_id", "hours")),
    "evaluate": ({"case_id": ID_FIELD}, ("case_id",)),
    "correction": ({"case_id": ID_FIELD, "expected_policy_version": REV_FIELD}, ("case_id", "expected_policy_version")),
    "playbook": ({}, ()),
}
METHODS = {
    "seed": "seed_demo", "list": "list_cases", "case": "get_case", "plan": "plan",
    "select": "select_plan", "execute": "execute", "reconcile": "reconcile",
    "advance": "advance", "evaluate": "evaluate", "correction": "activate_correction",
    "playbook": "playbook",
}


def load_core():
    root = PLUGIN_ROOT.resolve()
    namespace = "_hermes_ops_" + hashlib.sha256(str(root).encode()).hexdigest()[:24]
    name = namespace + ".manufacturing_ops"
    package = sys.modules.setdefault(namespace, types.ModuleType(namespace))
    lock = package.__dict__.setdefault("_load_lock", threading.RLock())
    with lock:
        if name in sys.modules:
            return sys.modules[name]
        package.__path__ = [str(root)]
        sys.modules[namespace + ".runtime_loader"] = sys.modules[__name__]
        spec = importlib.util.spec_from_file_location(
            name, root / "manufacturing_ops" / "__init__.py",
            submodule_search_locations=[str(root / "manufacturing_ops")],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("The installed manufacturing core is missing")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            for key in list(sys.modules):
                if key == name or key.startswith(name + "."):
                    sys.modules.pop(key, None)
            raise
        return module


def service(data_dir=None):
    if data_dir is None:
        from plugins.plugin_storage import plugin_data_dir
        data_dir = plugin_data_dir(PLUGIN_ID)
    return load_core().OpsService(Path(data_dir))


def schema(operation):
    properties, required = SCHEMAS[operation]
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def validate(operation, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("Request must be a JSON object")
    properties, required = SCHEMAS[operation]
    unknown = set(arguments) - properties.keys()
    if unknown:
        raise ValueError("Unexpected request fields")
    if any(key not in arguments for key in required):
        raise ValueError("Missing required request fields: " + ", ".join(required))
    for key, value in arguments.items():
        field = properties[key]
        if field["type"] == "integer":
            if type(value) is not int or not field["minimum"] <= value <= field["maximum"]:
                raise ValueError(f"{key} must be an integer from {field['minimum']} to {field['maximum']}")
        else:
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            if "enum" in field and value not in field["enum"]:
                raise ValueError(f"Unsupported {key}")
            if not field.get("minLength", 0) <= len(value) <= field.get("maxLength", 128):
                raise ValueError(f"Invalid {key} length")
            if "pattern" in field and re.fullmatch(field["pattern"], value) is None:
                raise ValueError(f"Invalid {key}")
    return arguments


def public_data(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"handle", "capability", "capability_handle", "worker_handle"}:
                continue
            if key == "snapshot" and isinstance(item, dict) and "suppliers" in item:
                item = {
                    **item,
                    "suppliers": [
                        {name: field for name, field in supplier.items() if name != "cutoff_delay_hours"}
                        for supplier in item["suppliers"]
                    ],
                }
            result[key] = public_data(item)
        return result
    if isinstance(value, (list, tuple)):
        return [public_data(item) for item in value]
    return value


def invoke(operation, arguments, data_dir=None):
    validate(operation, arguments)
    return public_data(getattr(service(data_dir), METHODS[operation])(**arguments))


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON value")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid JSON") from exc


def error_response(exc):
    if isinstance(exc, KeyError):
        return 404, {"error": "Not found"}
    if isinstance(exc, load_core().ConflictError):
        return 409, {"error": str(exc)}
    if isinstance(exc, ValueError):
        return 422, {"error": str(exc)}
    return 500, {"error": "Operation failed; no successful outcome is implied"}


def dispatch(method, path, body=None, data_dir=None):
    if method == "GET":
        routes = {"/health": None, "/cases": "list", "/playbook": "playbook"}
        if path == "/health":
            load_core()
            return {"status": "ok", "synthetic": True, "worker_mode": "bounded_model_task", "worker_requires": "active Hermes tool invocation"}
        if path in routes:
            return invoke(routes[path], {}, data_dir)
        match = re.fullmatch(r"/cases/([^/]+)", path)
        if match:
            return invoke("case", {"case_id": match[1]}, data_dir)
    if method == "POST":
        if path == "/demo/seed":
            return invoke("seed", body, data_dir)
        match = re.fullmatch(r"/cases/([^/]+)/(plan|select|execute|reconcile|advance|evaluate|correction)", path)
        if match:
            if not isinstance(body, dict) or "case_id" in body:
                raise ValueError("Body must be an object without case_id")
            return invoke(match[2], {**body, "case_id": match[1]}, data_dir)
    raise KeyError(path)


def render_html(api_prefix, csrf_token):
    config = json.dumps({"api": api_prefix, "csrf": csrf_token}).replace("<", "\\u003c")
    return (PLUGIN_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8").replace("__OPS_CONFIG__", config)
