from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "plugin" / "hermes_ops"


def run(data_dir: Path, plugin_dir: Path = PACKAGE_ROOT, artifact_dir: Path | None = None,
        checkpoint=None) -> dict:
    plugin_dir = plugin_dir.resolve()
    sys.path.insert(0, str(plugin_dir))
    from manufacturing_ops import OpsService

    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)

    def record(stage, case, **evidence):
        captured = {"stage": stage, "case": case, "evidence": evidence, "synthetic": True}
        if artifact_dir is not None:
            (artifact_dir / f"{stage}.json").write_text(json.dumps(captured, indent=2) + "\n")
        if checkpoint is not None:
            checkpoint(stage, captured)

    service = OpsService(data_dir)
    if service.playbook()["active_version"] != 1:
        raise ValueError("Use a fresh demo data directory; this directory already has a corrected policy.")
    first = service.seed_demo()
    record("01_open", first)
    first = service.plan(first["id"], first["revision"])
    selected = next(option for option in first["options"] if option["feasible"])
    assert selected["id"] == "economy", selected
    record("02_options", first)
    first = service.select_plan(first["id"], selected["id"], first["revision"])
    record("03_selected", first)
    child_code = (
        "import sys; from pathlib import Path;"
        "sys.path.insert(0, sys.argv[1]);"
        "from manufacturing_ops import OpsService;"
        "OpsService(Path(sys.argv[2])).execute(sys.argv[3], crash_after_external=True)"
    )
    child = subprocess.run(
        [sys.executable, "-c", child_code, str(plugin_dir), str(data_dir), first["id"]],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if child.returncode != 73:
        raise RuntimeError(f"Expected injected process exit 73, got {child.returncode}: {child.stderr}")
    service = OpsService(data_dir)
    interrupted = service.get_case(first["id"])
    assert interrupted["actions"][0]["status"] == "IN_FLIGHT", interrupted["actions"]
    record("04_interrupted", interrupted, child_exit_code=child.returncode)
    recovery_code = (
        "import json, sys; from pathlib import Path;"
        "sys.path.insert(0, sys.argv[1]);"
        "from manufacturing_ops import OpsService;"
        "print(json.dumps(OpsService(Path(sys.argv[2])).reconcile(sys.argv[3])))"
    )
    recovery = subprocess.run(
        [sys.executable, "-c", recovery_code, str(plugin_dir), str(data_dir), first["id"]],
        capture_output=True, text=True, timeout=30, check=True,
    )
    recovered = json.loads(recovery.stdout)
    action = recovered["actions"][0]
    assert action["status"] == "CONFIRMED", action
    assert any(event["kind"] == "reconciled" for event in recovered["events"]), recovered
    with sqlite3.connect(data_dir / "sim_erp.db") as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM purchase_orders WHERE action_key = ?",
            (action["idempotency_key"],),
        ).fetchone()[0]
    assert count == 1, count
    repeated = service.execute(first["id"])
    assert repeated["actions"][0]["external_ref"] == action["external_ref"], repeated
    record("05_reconciled", recovered, child_exit_code=child.returncode,
           recovery_exit_code=recovery.returncode, purchase_orders_for_action=count)
    service.advance(first["id"], 96)
    first = service.evaluate(first["id"])
    observed_first = first["evaluation"]
    assert observed_first["complete"], observed_first
    assert observed_first["actual_sales_ship_hour"] == 72, observed_first
    assert observed_first["sales_forecast_error_hours"] == 24, observed_first
    assert observed_first["sales_late_hours"] == 12, observed_first
    assert first["state"] == "CLOSED", first["state"]
    assert all(item["status"] == "RESOLVED" for item in first["obligations"]), first["obligations"]
    record("06_observed", first)
    corrected = service.activate_correction(first["id"], 1)
    record("07_corrected", corrected)
    second = service.seed_demo()
    second = service.plan(second["id"], second["revision"])
    selected_second = next(option for option in second["options"] if option["feasible"])
    assert selected_second["id"] == "priority", selected_second
    record("08_v2_options", second)
    second = service.select_plan(second["id"], selected_second["id"], second["revision"])
    service.execute(second["id"])
    service.advance(second["id"], 96)
    second = service.evaluate(second["id"])
    observed_second = second["evaluation"]
    assert observed_second["complete"], observed_second
    assert observed_second["actual_sales_ship_hour"] == 54, observed_second
    assert observed_second["sales_forecast_error_hours"] == 0, observed_second
    assert observed_second["sales_late_hours"] == 0, observed_second
    record("09_v2_observed", second)
    preserved = service.get_case(first["id"])["evaluation"]
    assert preserved["predicted_sales_ship_hour"] == 48, preserved
    result = {
        "synthetic": True,
        "scenario_id": "cutoff",
        "data_dir": str(data_dir),
        "injected_child_exit": child.returncode,
        "fresh_recovery_process_exit": recovery.returncode,
        "recovered_purchase_orders_for_action": count,
        "recovered_external_ref": action["external_ref"],
        "version_1": {"case_id": first["id"], "evaluation": observed_first},
        "version_2": {"case_id": second["id"], "evaluation": observed_second},
        "policy_version": service.playbook()["active_version"],
        "original_prediction_preserved": True,
        "worker_execution": "not exercised by this deterministic demonstration",
        "limitations": [
            "Synthetic scenario; not evidence of real manufacturing ROI.",
            "Correction uses explicit simulated supplier evidence, not autonomous model training.",
            "Duplicate safety is established only for the simulated connector contract.",
        ],
    }
    if artifact_dir is not None:
        (artifact_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--plugin-dir", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    data_dir = args.data_dir or Path(tempfile.mkdtemp(prefix="agentic-ops-demo-"))
    print(json.dumps(run(data_dir, args.plugin_dir, args.artifacts), indent=2))


if __name__ == "__main__":
    main()
