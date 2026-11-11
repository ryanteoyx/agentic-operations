# MVP contract v1

The core and Hermes builders implement this contract. Change it only through the coordinator. All business data is synthetic. Initial supported runtime is Python 3.11.

## Packaging

All installable runtime code lives inside `plugin/hermes_ops/`. No runtime imports may refer to repository siblings. `manufacturing_ops` is a private, dependency-light Python package; Hermes adapters wrap it.

The core entrypoint is:

```python
class OpsService:
    def __init__(self, data_dir: Path): ...
    def seed_demo(self, scenario_id: str = "cutoff", workspace_id: str | None = None) -> dict: ...
    def list_cases(self) -> list[dict]: ...
    def get_case(self, case_id: str) -> dict: ...
    def plan(self, case_id: str, expected_revision: int | None = None) -> dict: ...
    def select_plan(self, case_id: str, plan_id: str, expected_revision: int) -> dict: ...
    def execute(self, case_id: str, crash_after_external: bool = False) -> dict: ...
    def reconcile(self, case_id: str) -> dict: ...
    def advance(self, case_id: str, hours: int) -> dict: ...
    def evaluate(self, case_id: str) -> dict: ...
    def activate_correction(self, case_id: str, expected_policy_version: int) -> dict: ...
    def playbook(self) -> dict: ...
    def create_task(self, case_id: str, role: str = "supplier-review") -> dict: ...
    def start_task(self, task_id: str, attempt_id: str, handle: dict) -> dict: ...
    def finish_task(self, task_id: str, attempt_id: str, input_revision: int, result: dict) -> dict: ...
    def fail_task(self, task_id: str, attempt_id: str, reason: str) -> dict: ...
```

This deliberately reduces the master plan's future service surface to one sprint's implementation. Methods return JSON-serializable data, never live database objects. `ValueError` represents invalid input; a domain `ConflictError` represents stale state; unknown IDs raise `KeyError`. UI adapters map these to 422, 409, and 404.

`seed_demo` creates a fresh independent synthetic workspace by default; supplying an existing workspace ID is idempotent. It returns the initial case object. Repeating a source trigger within that workspace cannot create another case. Fresh workspaces are separate virtual manufacturers, not a reset of the same company's inventory. Use explicitly created sibling cases in one workspace to test resource contention.

`plan` evaluates and persists candidates but does not reserve or execute. It returns the updated case. `select_plan` checks versions and current resource availability, reserves, and creates the stable action intent atomically. It returns the updated case. `execute` may only use a selected, feasible plan. `reconcile` never blindly retries an unknown effect.

`advance` advances the selected workspace's synthetic clock by a nonnegative number of whole hours and creates due simulated source events; it is only available for demo data. Repeated advances/events deduplicate by source event identity. `evaluate` returns the case with its evaluation, and incomplete evidence is explicit. `activate_correction` activates only the evidence-backed supplier-cutoff estimate; it cannot increase spending or change customer priority.

`playbook` returns the active global demo estimate version, constraints, and correction history. A new workspace captures the current version; existing cases retain theirs. Runtime state belongs in `data_dir`, never the install tree.

## Required case response

```json
{
  "id": "case-stable-id",
  "workspace_id": "demo-workspace",
  "title": "Supplier delay threatens an order and warranty replacement",
  "state": "OPEN",
  "revision": 1,
  "synthetic": true,
  "policy_version": 1,
  "clock_hour": 0,
  "snapshot": {},
  "evidence": [],
  "obligations": [],
  "options": [],
  "selected_plan_id": null,
  "reservations": [],
  "tasks": [],
  "actions": [],
  "events": [],
  "evaluation": null,
  "correction": null
}
```

Each option has `id`, `label`, `feasible`, `reasons`, `supplier_id`, `incremental_cost_minor`, `purchase_value_minor`, `predicted_receipt_hour`, `predicted_replacement_ship_hour`, `predicted_sales_ship_hour`, and `inventory_after_original_receipt_units`. An infeasible option stays visible; no `selected` flag is inferred from array order.

Each event has `id`, `kind`, `at_hour`, `payload`. Each action has `id`, `idempotency_key`, `payload_hash`, `status`, `external_ref`, `attempts`. Task responses include `id`, `case_id`, `role`, `status`, `input_revision`, `attempt_id`, `result`, and `error`. Never return raw worker capability handles to the UI.

## Synthetic fixture and deterministic calculation

Base instant: `2026-11-16T08:00:00Z` (16:00 Asia/Singapore), synthetic clock hour 0.

| Input | Value |
| --- | --- |
| Company | Orange, synthetic |
| Currency | SGD; all monetary values integer cents |
| Product | PUMP-A; BOM-A revision A |
| Component | CTRL-01; one unit per assembly |
| Usable stock | 6 units |
| Warranty replacement | WR-104, 4 units, ship by hour 24 |
| Sales order | SO-208, 8 units, ship by hour 60 |
| Assembly capacity | One continuous station, 4 hours per unit |
| Original delayed PO | PO-ORIGINAL, 8 units, receipt hour 96, remains due |
| New shortage order | 6 units at 5000 cents each |
| Delegated incremental spend limit | 15000 cents |
| Economy approved supplier | SUP-ECO; predicted lead 24 h; cutoff 15:00 Singapore |
| Economy incremental expedite cost | 6000 cents |
| Priority approved supplier | SUP-PRI; confirmed lead 30 h |
| Priority incremental expedite cost | 14000 cents |
| Unapproved supplier | SUP-UNKNOWN; lead 8 h; incremental cost 2000 cents |

Version 1 omits the economy supplier's missed-cutoff effect. Its predicted receipt is hour 24, but the actual order placed at 16:00 arrives at hour 48. Version 2 uses the confirmed cutoff and predicts hour 48. The original prediction is never edited after learning this.

Assembly: reserve four stock units for the replacement first, then use the remaining two for the sales order. Replacement ships at hour 16. Two sales units finish by hour 24. After six purchased components arrive, the remaining six sales units require 24 hours.

For receipt hour `r`, sales shipment is `max(24, r) + 24`.

Candidate expected results:

| Plan | Receipt h | Replacement ship h | Sales ship h | Cost cents | Feasibility |
| --- | --- | --- | --- | --- | --- |
| wait | 96 | 16 | 120 | 0 incremental | Reject: sales deadline |
| economy, v1 | 24 predicted | 16 | 48 predicted | 6000 | Feasible under v1 evidence |
| economy, actual/v2 | 48 | 16 | 72 | 6000 | Misses/rejects sales deadline |
| priority | 30 | 16 | 54 | 14000 | Feasible |
| unapproved | 8 | 16 | 48 | 2000 | Reject: unapproved supplier |

Within feasible choices, order by incremental cost, then deterministic option ID. If none is feasible, return `NEEDS_ATTENTION` with reasons. Do not weaken deadlines, supplier approval, or spending limits.

Version 1 chooses economy; the observed sales delay is 24 hours relative to its prediction and 12 hours relative to its deadline. Version 2 chooses priority; actual and predicted sales ship at hour 54. In both expedite plans, the original 8-unit order still arrives at hour 96, leaving 8 units of extra inventory. The additional shortage purchase principal is 30000 cents, separate from the expedite surcharge. Do not call 6000 or 14000 the total PO value.

No real ROI/working-capital claim is made. A later cash model must separately represent purchase principal, incremental costs, inventory, invoice timing, and collected cash.

## Persistence and concurrency

Use `operations.db` and independent `sim_erp.db` under the data root. Operations tables cover workspace clock/stock/capacity revision, case snapshots, reservations, tasks, action intents/attempts, events/observations, policy versions, and corrections. Use SQLite foreign keys and short write transactions. Request-local connections only.

Store immutable original snapshot/policy/prediction. Mutable case revision increments when accepted state changes. `select_plan` must compare the supplied revision and the planning resource snapshot against current availability, then reserve atomically. Two cases in the same workspace cannot reserve the same six units or assembly interval.

Action identity is fixed when selecting the plan. The simulated ERP has a UNIQUE key on `idempotency_key` and validates `payload_hash`; repeated matching execution returns the same PO. Different payload for the same key fails.

Commit local PREPARED intent before external execution. Commit the simulated ERP order independently. With `crash_after_external=True`, only the owned test/demo child process exits after that commit and before local acknowledgement; never terminate the Hermes host. This flag must not be exposed through public tools or HTTP requests.

A fresh process reopens the stores and reconciles the unfinished action by key. It records the existing PO reference and a `reconciled` event. Unknown external outcomes remain `NEEDS_ATTENTION`.

Case closes only when actual simulated source events resolve both shipment obligations. Outcome evaluation preserves forecast error and may report a closed but late case. Expediting cannot cancel the original replenishment without an explicit action.

## Worker contract

The initial worker reads only case evidence and returns:

```json
{
  "summary": "Short factual explanation",
  "evidence_ids": ["supplier-delay", "bom-a", "stock-ctrl-01"],
  "affected_order_ids": ["WR-104", "SO-208"],
  "shortage_units": 6
}
```

Validate all IDs and the shortage against the snapshot. No worker result can activate corrections, execute purchases, alter constraints, or assert that future observations occurred. The cutoff observation is introduced later by the simulated acknowledgement/receipt evidence, not by granting a worker hidden future data.

Create a durable task before launch. `attempt_id` is unique per attempt. Accept a result only for the active attempt and unchanged input revision. Failure records remain inspectable. Model unavailable means an explicit failed/unavailable task, not fabricated success.

Only use public `ctx.subagent_lifecycle` in an active agent turn. HTTP handlers cannot launch it directly. UI may queue/display task intent and instruct the user to invoke the agent tool.

## Acceptance scenarios

- Happy path, duplicate trigger, invalid quantity/supplier/unit, no feasible plan.
- Same-workspace stock/capacity race and stale revision.
- Duplicate action, mismatched payload, uncertain lookup.
- Hard exit after external commit; fresh-process restart; exactly one matching ERP PO.
- Worker failure, stale result, restart with unavailable handle.
- Version 1 outcome is sales hour 72, forecast error +24 h, deadline miss +12 h.
- Version 2 selects priority and observes sales hour 54; original v1 forecast remains hour 48.
- Different temporary profile/data roots do not share business state.
- Installed plugin copy works outside this repository.
