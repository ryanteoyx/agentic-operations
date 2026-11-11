# Backlog (Linear-ready)

Until the native Linear integration is connected, this file is the actionable
backlog. When imported into Linear, use project **Agentic Operations** with
milestones `M0 — shortage demo and submission` (OPS-001–013) and
`M1 — pilot-ready shared operations` (OPS-014+), labels `HARNESS`, `CORE`,
`HERMES`, `DEMO`, `EVAL`, `CONNECTORS`, and workflow
`Backlog -> Ready -> In Progress -> In Review -> Done` plus `Blocked`.

Do not auto-start the entire backlog. Only ready, dependency-satisfied issues
enter the two-builder work-in-progress limit.

## Issues

| ID | Priority | Owner | Depends on | Acceptance |
| --- | --- | --- | --- | --- |
| OPS-001 | P0 | Coordinator | None | Harness docs, valid Wiki JSON, skills, brief, reproducible commands committed |
| OPS-002 | P0 | Coordinator | None | Verified Hermes backup, upgrade, rollback record, API and host smoke |
| OPS-003 | P0 | Coordinator + A | OPS-001 | Contract/schema/fixture v1 frozen with hand-checkable expected choices |
| OPS-004 | P0 | A | OPS-003 | Persistent cases, snapshots, transitions, duplicate-trigger protection |
| OPS-005 | P0 | A | OPS-004 | Feasible option evaluation; stock/capacity/budget failures explicit |
| OPS-006 | P0 | A | OPS-005 | Atomic reservations, stable action keys, separate simulated ERP |
| OPS-007 | P0 | A | OPS-006 | Process interruption and fresh-process reconciliation create one ERP order |
| OPS-008 | P0 | B | OPS-002, OPS-003 | Installed-copy plugin loads; tools/backend import the same packaged core |
| OPS-009 | P0 | B | OPS-008, OPS-004 | Real active-turn investigation worker; persisted task/result and stale-result checks |
| OPS-010 | P0 | B | OPS-005, OPS-008 | Usable case view shows evidence/options/actions/error states |
| OPS-011 | P0 | A | OPS-007 | Observed outcome, immutable original forecast, tested correction, second case |
| OPS-012 | P0 | Coordinator | OPS-007–011 | Thesis, truthful demo under 90 seconds, final-commit install validation |
| OPS-013 | P0 | Coordinator | OPS-012 | Public source and catalog PR; prepared X/form materials and submission status |
| OPS-014 | P1 | Coordinator | Working release | Native Linear connection, imported issues, synced skill verified on one ticket |
| OPS-015 | P1 | Coordinator | Public repo | DeepWiki indexed and Review exercised on a real PR |
| OPS-016 | P1 | Coordinator | Stable setup commands | Cloud blueprint builds and fresh session passes smoke |
| OPS-017 | P1 | Coordinator | OPS-014–016 | Bounded CI/scenario/weekly automations tested with deduplication |
| OPS-018 | P2 | A | Pilot data access | First real connector with provenance, incremental sync, dry-run and reconciliation |
| OPS-019 | P2 | A/B | Multiple users or unattended pilot | Shared PostgreSQL workspace, authentication, durable scheduler, migrations |

## Ownership

| Owner | Files/responsibility | Integration dependency |
| --- | --- | --- |
| Coordinator | `docs/`, `.devin/`, root config/CI, contract decisions, release | Freezes contracts and first fixture before builder divergence |
| Builder A | `manufacturing_ops/models.py`, store/schema, decision, execution, evaluation, sim; core tests | Produces shared service behavior |
| Builder B | entrypoint/bootstrap, tools/workers/CLI, dashboard/Desktop, plugin smoke tests | Implements against the frozen service interface |

Builder B may use contract fixtures before the backend is complete. Mock
responses must be removed from the demonstration before release. Neither
builder silently changes shared signatures — the coordinator owns contract and
schema changes.

Use branch names such as `feat/case-runtime` and `feat/hermes-surface`.
Integrate small working increments. Keep one person/session responsible for
migrations and release metadata. Local subagents share a filesystem — use
separate Git worktrees or separate Cloud sessions with their own branches.

## Handoff contract

Each worker hands back: commit/branch, owned files, behavior implemented, tests
run, remaining limitation, and any changed public interface. The coordinator
reruns the combined vertical scenario after integration.
