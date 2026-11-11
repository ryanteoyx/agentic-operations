# Agentic Operations operator guide

This guide operates **synthetic** cases for **Orange**. It places no real
supplier orders, reads no company ERP, and demonstrates no real financial
return. Tools, CLI commands, and browser actions call the same core services.

## Open a workspace

Follow the [README quickstart](../README.md#quickstart-local-browser-demo) with
Python 3.11+ and a distinct data folder, then open http://127.0.0.1:8765.
The standalone workflow needs no Hermes process or model credentials.

The native Hermes CLI and authenticated HTTP boundary have been exercised.
In the Hermes web dashboard, open **Operations** at `/operations`. Its embedded
browser workflow passed from seed through correction using the public
`SDK.authedFetch`, with all requests returning 200 and no 401s or JavaScript
errors. Anonymous plugin UI access remains 401. The native Desktop app is not
integrated. Use a pinned release and validate it before deployment.

For a complete v1-to-v2 walkthrough, start with a fresh data directory.
Reusing a directory keeps its active policy, cases, and observations. A new
case is an independent virtual manufacturer workspace, not a reset of the
same company's resources. Seeding with an explicit existing `workspace_id`
is idempotent.

## Find the business decision

| Tab | Business question | What to inspect |
| --- | --- | --- |
| **Overview** | What is at risk and why? | Source evidence, warranty and sales obligations, usable stock, captured policy, and any recorded review task |
| **Plan** | Which recovery meets our constraints? | Feasible/rejected alternatives, shipment forecasts, supplier approval, expedite surcharge, component principal, and reservations |
| **Activity** | What did we authorize and what actually executed? | Durable action identity, status, ERP reference, attempts, and recovery events |
| **Outcome** | Did the original plan deliver? | Immutable forecast versus observed shipments, deadline misses, evidence gaps, and a proposed estimate correction |

The contextual primary button follows the current case state. **Refresh**
reloads authoritative state; it does not execute an action. **Download case**
is available once a case is selected.

## Walk through the shortage

The following numbers are **expected synthetic fixture values already covered
by tests**, not a report of the final release capture.

### 1. Seed a case

Click **Seed demo case** in the empty workspace. The sidebar's **＋ New demo
case** also creates an independent workspace.

Orange builds `PUMP-A` using one `CTRL-01` component per unit under `BOM-A`,
revision A. The opening evidence has:

- **6 usable components** on hand.
- **WR-104:** a four-unit warranty replacement due by **h24**, prioritized
  before sales.
- **SO-208:** an eight-unit sales order due by **h60**.
- **PO-ORIGINAL:** eight components delayed until **h96**.
- One continuous assembly station requiring **4 hours per unit**.
- Incremental spending authority of **15000 cents / SGD 150**.

Four stock units go to warranty first, then two to sales. Six more components
are required. Hours are offsets from the synthetic opening time
`2026-11-16T08:00:00Z` (16:00 Singapore), not live wall-clock elapsed time.

### 2. Compare recovery plans

Click **Compare recovery plans**. The **Plan** tab retains both feasible and
rejected alternatives:

| Label | Stable supplier ID / plan ID | Version 1 assessment |
| --- | --- | --- |
| Wait for original supply | Existing PO / `wait` | Reject: sales would ship h120 |
| Banana · economy | `SUP-ECO` / `economy` | Feasible under v1 evidence: sales forecast h48; SGD 60 surcharge |
| Grapefruit · priority | `SUP-PRI` / `priority` | Feasible: sales forecast h54; SGD 140 surcharge |
| Plum · unapproved | `SUP-UNKNOWN` / `unapproved` | Reject: supplier is unapproved, even though it is cheap and fast |

The recommendation chooses the least incremental cost among feasible plans,
with deterministic tie-breaking. Comparing plans **does not reserve stock or
place an order**. A rejected option is not made permissible by a model's
recommendation.

### 3. Approve Banana economy

Review both **Expedite surcharge** and **Components** in the recommended-plan
card before clicking **Approve Banana · economy** (the button also shows its
price):

- `incremental_cost_minor: 6000` means **SGD 60**, the incremental expedite
  surcharge.
- `purchase_value_minor: 30000` means **SGD 300**, the separate principal for
  six components at SGD 50 each.

The SGD 60 amount is not the total PO value. Approval is an explicit operator
decision about the displayed plan and amounts; do not infer approval from
merely viewing the recommendation.

Approval checks the current case revision and resource availability, reserves
stock and assembly capacity, and persists a **PREPARED** action intent with
stable logical identity. It does **not** yet write a purchase order to the
simulated ERP. The option table's **Select plan** uses the same selection
operation; inspect that alternative's amounts before selecting it.

### 4. Place the simulated order

In **Activity**, inspect the persisted intent, then click **Place simulated
order**. This is the separate connector execution step. Only the selected
feasible plan can execute, and its stable key and payload identify the logical
purchase.

The simulated ERP commits independently of the operations store. A confirmed
action has its ERP reference. If the outcome is uncertain, stop and
[reconcile the original action](#recover-an-uncertain-purchase); do not create
another case or purchase to work around it.

### 5. Observe the simulated outcome

Click **Observe simulated outcome**. This advances the workspace clock to at
least h72 and evaluates due simulated source events. It is not waiting 72 real
hours, and it is not asking a model to declare success.

Expected v1 observations in **Outcome**:

- Warranty ships at **h16**, before its h24 deadline.
- Sales was forecast at **h48**, but actually ships at **h72**.
- Sales is **24 hours later than forecast** and **12 hours later than the h60
  deadline**. A closed case can still be late.
- Supplier acknowledgement/receipt evidence confirms a missed 15:00 Singapore
  cutoff: the 16:00 order's receipt moves from predicted h24 to observed h48,
  a **24-hour cutoff delay**.

The original forecast remains h48. Observations are emitted by the simulated
source, never by worker text. **+24 hours**, **+72 hours**, and **Evaluate
outcome** provide separate controls; evaluation reports missing evidence
rather than inventing shipment events.

The original eight-unit replenishment was not cancelled. Advancing from h72
with **+24 hours** reaches h96 and observes that receipt, leaving eight extra
components after both obligations are fulfilled.

### 6. Activate the corrected estimate

Click **Activate corrected estimate**. The correction card also exposes
**Activate estimate v2** for the same operation.

This activates the evidence-backed supplier-cutoff estimate at the expected
policy version. It does not train a model, edit the original prediction,
raise spending authority, approve an unapproved supplier, or change warranty
priority. Existing cases retain the policy captured when they were created.

### 7. Start the next case and choose priority

Click **Start next case** (also shown as **Start next case · policy v2** on
the activated correction card), then **Compare recovery plans**.

In the new independent workspace, version 2 predicts Banana economy sales at
h72, making it infeasible against the h60 deadline. **Grapefruit · priority**
is recommended. Review its **SGD 140** incremental surcharge (`14000` cents)
and separate **SGD 300** component principal (`30000` cents), then click
**Approve Grapefruit · priority**, **Place simulated order**, and
**Observe simulated outcome**.

The expected priority forecast and observed sales shipment are both **h54**;
warranty remains **h16**. Reopen the first case to see its original h48 sales
prediction and h72 observation still intact.

## Download a case

**Download case** fetches the current public case response and saves
`orange-case-<case-id>.json`. It contains a schema version, synthetic-data flag,
export timestamp, and a case snapshot including the original prediction,
policy, alternatives, durable actions, evidence, events, and any evaluation.

This is a public, redacted snapshot, **not** a SQLite backup, migration, or
restore file. Raw worker capability handles and hidden fixture cutoff fields
are not exported. Confirmed cutoff evidence can appear once the source emits
it. Treat exports as records of the current case, not as independent proof that
a production ERP action occurred.

## Recover an uncertain purchase

Use **Recover purchase order** when the contextual action reports recovery is
needed. In an active Hermes turn, the equivalent tool is:

```text
ops_reconcile {"case_id":"CASE_ID"}
```

Or, with the Hermes CLI:

```sh
hermes ops case CASE_ID
hermes ops reconcile CASE_ID
hermes ops case CASE_ID
```

Replace `CASE_ID` with the actual ID from `hermes ops list` or the case export.
Reconciliation looks up the original stable action key and records the
existing ERP reference and a `reconciled` event. An unknown result remains
explicitly unresolved/needs attention; do not issue a new purchase as a blind
retry. Preserve the same data directory and both `operations.db` and
`sim_erp.db` across a restart.

The [recovery harness](../README.md#reproduce-the-recovery-scenario) deliberately
exits an owned process with code 73 after the simulated ERP commit, then uses
a fresh process to recover one matching PO. Crash injection is **harness-only**:
there is no public crash button, tool argument, or HTTP parameter. Do not kill
the Hermes host to demonstrate it.

## Hermes CLI and tool inputs

Read current IDs and revisions instead of guessing them:

```sh
hermes ops seed
hermes ops list
hermes ops case CASE_ID
hermes ops plan CASE_ID
hermes ops select CASE_ID economy --expected-revision REVISION
hermes ops execute CASE_ID
hermes ops advance CASE_ID --hours 72
hermes ops evaluate CASE_ID
hermes ops playbook
hermes ops correction CASE_ID --expected-policy-version POLICY_VERSION
```

Replace `REVISION` with the integer revision returned by the latest plan/read;
`POLICY_VERSION` is the current active version from `playbook`. The selection
example assumes a fresh v1 case where `economy` is feasible. Never use
`execute` in place of reconciling an uncertain action.

The corresponding tool inputs include:

```text
ops_seed_demo {"workspace_id":"orange-walkthrough"}
ops_case {"case_id":"CASE_ID"}
ops_plan {"case_id":"CASE_ID"}
ops_select_plan {"case_id":"CASE_ID","plan_id":"economy","expected_revision":REVISION}
ops_execute {"case_id":"CASE_ID"}
ops_advance_demo {"case_id":"CASE_ID","hours":72}
ops_evaluate {"case_id":"CASE_ID"}
ops_activate_correction {"case_id":"CASE_ID","expected_policy_version":POLICY_VERSION}
```

These are templates: replace the revision/version placeholders with JSON
integers before invoking a tool. `ops_seed_demo {}` creates a fresh workspace;
reusing the explicit `orange-walkthrough` ID returns that workspace instead.
The [plugin reference](../plugin/hermes_ops/README.md) lists all eleven tools.

## Optional bounded evidence review

The browser's **Review evidence in Hermes** button refreshes recorded task state
and tells you how to invoke the tool; it does **not** start a model. In an
active Hermes turn with a configured provider, use:

```text
ops_investigate {"case_id":"CASE_ID"}
```

The adapter uses public `ctx.llm.complete_structured` for one no-tools review
of supplied evidence. It reports `worker_mode: bounded_model_task` and
`actual_subagent: false`. It is not autonomous delegation, a multi-agent
orchestrator, or a purchasing agent.

- Task intent and its attempt are durable before the model call, which runs
  outside a database transaction.
- The host request timeout and caller wait are each bounded to **60 seconds**.
  Late output is discarded; a provider request already sent may continue
  remotely because this fallback has no cancellation handle.
- A running attempt has a **90-second durable lease**. Expired attempts become
  `INTERRUPTED` when the service opens or reads cases. The core enforces at most
  **two attempts per task**, active-attempt identity, and unchanged input
  revision before accepting output.
- There is **no automatic redispatch** and no public resume/retry control for
  an existing task. Calling `ops_investigate` again creates a **new task**; the
  two-attempt core limit is not a global limit on repeated user requests.
- Strict validation checks cited evidence, both order IDs, and the shortage
  quantity. A review cannot execute, change authority, activate corrections, or
  write authoritative observations.

Unavailable providers and invalid, stale, or timed-out output leave an
inspectable failure record. Live provider/model investigation has **not been
attempted** in the isolated verification profile because it lacks credentials.
Stubbed tests do not establish live model availability.

## Troubleshooting and data boundaries

| Symptom | Safe next step |
| --- | --- |
| Stale revision / HTTP 409 | Click **Refresh**, inspect current state, and compare plans again if necessary. Use the new revision; never bypass the conflict check. |
| An option is infeasible | Read its constraint reasons. Supplier approval, shipment deadlines, capacity, and spending authority are hard constraints, not suggestions. |
| Action is uncertain / needs recovery | Reconcile the original action. Preserve its key and both databases; do not create another purchase or blindly retry. |
| No provider or review failure | Read the recorded task error. Configure the host provider through normal Hermes setup if desired; the deterministic workflow remains usable. No successful model review is implied. |
| CSRF rejected after a restart / HTTP 403 | Fully reload the page for the current process-local token. Keep same-origin access; do not disable CSRF protection or copy host tokens into plugin code. |
| Native HTTP 401 | Use normal Hermes host authentication. Anonymous rejection is expected, not permission to disable authentication. |
| New case starts on policy v2 | The data directory already contains an activated correction. Use a distinct fresh directory for a v1 walkthrough; another seed does not reset policy. |
| Explicit workspace ID returns an existing case | Seeding that ID is intentionally idempotent. Omit it for a fresh independent workspace. |
| Address already in use | Reuse the intended existing demo, or start your own instance on a free port with a distinct data folder. Do not terminate an unrelated user's server. |

Operate this as one single-host service with SQLite, not a shared multi-process
company deployment. Keep business state outside the plugin installation tree;
Hermes resolves storage from the active profile, while the standalone server
requires an explicit data directory. Never reset a real user's Hermes profile
for a demo.

The loopback server is not an Internet-facing service. Host authentication is
not company RBAC, and another local process running as the same user is outside
this browser boundary. Production ERP connectors, Temporal, Postgres, shared
company memory, and RBAC are not implemented. See
[company deployment requirements](company-deployment.md) before planning a
company pilot, and [the verification record](devin-harness.md#product-verification-record)
for the exact tested scope.
