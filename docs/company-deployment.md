# Deploying Agentic Operations with Hermes

This release supports a **controlled, single-company synthetic pilot**. Hermes
loads the plugin, exposes its tools and CLI, and serves an authenticated
Operations dashboard. The manufacturing service keeps durable cases in SQLite
and writes only to a simulated ERP.

It is not yet a live ERP integration, a multi-tenant service, or an approved
autonomous purchasing system. Those deployments require the gates below.
Installing Hermes in a container does not, by itself, satisfy those gates.

## Readiness of this release

| Surface | Status and evidence |
| --- | --- |
| Hermes plugin loading and capabilities | Local validator passed on Hermes 0.23.1+2046.gb5f15a6. Validate the final published SHA again before promotion. |
| Tools and CLI | Eleven tools registered; `hermes ops seed`, `list`, and `playbook` exercised under an isolated home. |
| Native web dashboard | Operations tab uses the public dashboard SDK and its authenticated fetch helper. Native seed → plan → purchase → observe → correction workflow passed; anonymous plugin requests remained HTTP 401. |
| Durable business state | Cases, reservations, action intents, observations, task attempts, and policy versions persist in SQLite. Tests cover interruption recovery and contention. |
| Model investigation | Bounded, no-tools host-model request; results require valid citations, attempt identity, and the original input revision. Tested with a model stub. A live provider call has not been verified. |
| External execution | Simulated ERP only. Its stable action identity supports reconciliation after an uncertain result. This is not a guarantee for an arbitrary ERP API. |
| Process supervision | Supported Hermes commands were inspected. Native dashboard processes were started and verified. Company service-manager installation and failure recovery remain deployment acceptance checks. |
| Docker / Kubernetes | Architecture and operating requirements below. Local Docker client exists, but its daemon was unavailable; Compose and kubectl were unavailable. No container or cluster deployment is claimed. |
| Temporal, Postgres, shared retrieval memory | Proposed production components. They are not dependencies or implemented integrations in this release. |
| Company authorization and connectors | Actor-level business permissions, company identity integration, production connectors, and tenant isolation must be implemented and tested before company writes. |

## What Hermes does in the company

Hermes is the agent runtime and plugin host. An operator asks for an investigation
or opens a decision case. Hermes may summarize cited evidence, request a
deterministic plan, and explain the available choices. The plugin service owns
the constraints and durable records. A model response cannot create an
authoritative receipt, rewrite a forecast, or expand spending authority.

The production target separates these responsibilities:

```text
Company identity / approved ingress
                 |
        Operations application
       /          |             \
Business policy   Case service   Workflow coordinator
and approvals     + ledger       (Temporal, proposed)
       \          |             /          |
        Authorized action intent      Bounded task
                 |                         |
        Connector execution gateway    Hermes worker
                 |                     + approved plugin
           ERP / CRM / MRP                  |
                 |                  ACL-filtered evidence
        Verified source observations       |
                 +---- Outcome evaluation -+
```

The connector gateway authorizes the **specific action and payload** against an
approved case revision, policy version, tenant, amount, supplier, and expiry.
It issues narrowly scoped credentials or performs the write itself. A broad ERP
credential must not be available to an investigation worker.

The current plugin's `agentic_operations` toolset includes planning and synthetic
execution tools together. Before enabling real writes, split exposure by role
and enforce authorization in the service and connector gateway. Hiding a tool
from a model is useful, but is not an authorization boundary.

## Rollout stages

1. **Synthetic pilot:** use a separate Hermes home, synthetic provider settings,
   and the packaged fixtures. Exercise the entire interruption/recovery loop.
2. **Read-only shadowing:** add approved, read-only company connectors. Import
   only authorized records, preserve source versions and units, and compare
   recommendations with operator decisions. No ERP writes.
3. **Draft actions:** generate proposed actions with immutable payload hashes.
   An operator approves an exact proposal; changed evidence invalidates it.
4. **Bounded execution:** enable one connector and one action class with supplier,
   amount, quantity, customer-priority, and concurrency limits enforced outside
   the model. Require confirmed external idempotency/reconciliation semantics.
5. **Expanded autonomy:** widen a boundary only after reviewing outcome evidence,
   failures, reversibility, and ownership. A model cannot grant itself more scope.

Promote the same reviewed image, plugin commit, schema migration, and policy
configuration between stages. Record who approved promotion and the evidence
used. Keep a previous deployable version and a tested recovery procedure.

## Capability and tenant boundaries

| Role | Permitted capability | Boundary to enforce |
| --- | --- | --- |
| Investigator | Read an approved evidence packet; return cited structured findings | No ERP credentials, shell, arbitrary browser access, delegation, or business writes |
| Planner | Read current case state and evaluate alternatives | Deterministic constraints; no reservation or external execution merely from planning |
| Coordinator | Assign bounded tasks and collect validated results | Task leases, attempt limits, input revisions, deadline and cost budgets |
| Executor | Submit an approved immutable action through the connector gateway | Action-specific authorization, stable identity, payload hash, reconciliation before retry |
| Observer | Read approved source events and validate provenance | Models cannot fabricate observations or treat generated notes as ERP events |
| Policy administrator | Review and activate an allowed policy change | Version check, evidence references, approval record, constrained change surface |
| Platform operator | Install a reviewed plugin, manage services and restore backups | Separate from routine business approval; privileged access is logged |

The first row describes the implemented bounded investigation request. The
separate production roles and connector gateway are architecture requirements,
not implemented role-based access control.

Use a separate OS/container identity, Hermes home, data volume, and credential
scope per company or trust boundary. Hermes profiles organize configuration and
state; **they are not a proven tenant security boundary**. The inspected profile
creation help permits some fallback to default-profile provider logins even
with isolation-related flags. Do not place unrelated companies in one home and
assume those flags isolate credentials.

Pin and review installed plugins. A frontend plugin receives the host's public
dashboard SDK; its iframe is styling isolation, not a sandbox against a malicious
installed plugin. `plugins.isolation: host` separates plugin execution from the
main process for fault isolation; it does not replace OS-level filesystem,
credential, or network restrictions.

Disable unnecessary messaging channels, hooks, MCP servers, tools, and browser
capabilities. Enumerate the actual tools exposed to each role at launch and fail
deployment if an unexpected capability is present. Recheck after Hermes or
plugin upgrades: defaults and toolset expansion can change.

## Docker deployment

For an initial company pilot, use one dedicated Linux VM and the official Hermes
container build/deployment documentation for the reviewed Hermes revision.
Pin the image by **digest**, and the plugin by its complete Git commit SHA.
Do not use a floating `latest` or `main` tag as the production release identity.

The inspected upstream image uses **s6 supervision** and startup scripts that
prepare ownership before services drop to the Hermes user. The upstream Compose
example uses host networking and a persistent `/opt/data` mount. These are
material properties of that image:

- Preserve the supported entrypoint and supervision lifecycle. Replacing it with
  an arbitrary `python` command skips initialization.
- Do not assume `user: 10000`, `read_only: true`, or `cap_drop: ALL` works with
  that startup path. Test a deliberately hardened image before requiring those
  settings; root bootstrap and a non-root application process are different.
- Treat host networking as a pilot compatibility choice on a dedicated VM,
  with firewall restrictions and loopback dashboard binding. The production
  target is a private network with controlled ingress and egress.
- Mount only the dedicated Hermes state and approved working directories.
  Do not mount the host home, Docker socket, Kubernetes credentials, or company
  document shares wholesale.
- Set CPU, memory, PID, storage, and log-retention limits. A restart policy
  restores a process; it does not establish the outcome of an external purchase.
- Inject approved provider/connector secrets at deployment time from the
  company's secret manager. Do not bake them into images, Git, skills, prompts,
  example configuration, or demo exports.

Use the authenticated Hermes dashboard on loopback for the pilot, reached through
an approved SSH tunnel or private access service. For shared remote access,
integrate the company's identity controls and verify the host's supported
authentication mode. Do not use `--insecure` to make a reverse proxy work.

The release has no verified Docker deployment artifact yet. An IT owner should
record the image digest, startup UID/capability behavior, writable paths, mounted
secrets, exposed ports, and restart test before calling a container deployment
ready.

## Kubernetes and the control plane

Kubernetes becomes useful when the company needs independent worker identities,
admission controls, resource quotas, rollout management, and centralized
observability. It does not provide durable business workflow semantics.

Recommended production layout:

- **Control plane:** authenticated application/API, policy and approval service,
  workflow coordinator, connector gateway, and append-only audit export.
- **Worker plane:** bounded Hermes workers, separated by company/trust boundary
  and capability. Workers receive task references and approved evidence rather
  than broad database access.
- **Data plane:** Postgres for authoritative cases/action records, an evidence
  object store, and permission-filtered retrieval indexes.
- **Platform plane:** workload identity, secret manager, private ingress,
  network policy, admission policy, and monitoring.

For worker pods, require non-root execution, no privilege escalation, dropped
Linux capabilities, `RuntimeDefault` seccomp, no host namespaces, no hostPath or
container-runtime socket, and a read-only root filesystem with explicitly
writable scratch space. Disable service-account-token mounting unless the worker
actually needs the Kubernetes API. Use a worker image whose startup path has
been tested under these restrictions; do not paste this security context onto
the s6 image and assume it works.

Start with default-deny ingress/egress. Add only the required DNS, model gateway,
approved retrieval service, and connector gateway paths. Kubernetes
NetworkPolicy generally does not enforce SaaS hostname allowlists on its own;
use an approved egress proxy or suitable network-policy implementation.

Separate readiness from liveness. A healthy HTTP process is not proof of usable
database storage, a working model provider, or connector authorization. Drain
new work before termination, bound task leases, and reconcile external effects
after a replacement worker starts.

**Do not scale this SQLite release to multiple application replicas.** Use one
writer deployment and a supported persistent filesystem for a pilot. A
production horizontal-scaling release needs a tested Postgres migration,
transactional reservations, and a deliberate leader/worker ownership model.

## Temporal and multi-agent orchestration

Temporal is considered for the production durable coordinator. Adopt it when
work must survive deployments, wait hours or days for supplier responses or
human approval, enforce deadlines, and resume across workers. The current
SQLite service implements a focused recovery loop; it is not a Temporal
implementation.

A proposed workflow identity is `tenant_id:case_id`. The workflow coordinates
activities for evidence acquisition, Hermes investigation, planning,
authorization, connector execution/reconciliation, observation, and evaluation.

Keep workflow code deterministic. Model calls, connector I/O, and database
writes belong in activities. Store compact references in workflow history;
large documents and secrets belong in governed stores. Treat history as
sensitive operational data with its own access and retention controls.

The case/action ledger remains authoritative for business effects. Use a
transactional outbox to notify the workflow after committed state changes;
consumers deduplicate event identities. Avoid assuming a single transaction
spans Postgres, Temporal, and an ERP.

Activity retries require explicit semantics:

- Read-only acquisition may retry within a finite budget.
- A model task gets a fixed input revision, deadline, and attempt identity;
  expired or superseded results are rejected.
- An external write always reuses the stable logical action identity. An
  uncertain outcome triggers lookup/reconciliation, not a new action key.
- If a connector cannot establish whether an effect occurred, the case moves
  to operator attention. Temporal retry does not make an unsafe connector safe.

Multi-agent roles exchange typed results with evidence references through the
case service. They do not communicate authority by writing conversational notes.
Set per-case concurrency, total model-call/cost budgets, maximum attempts, and
escalation deadlines. Automated policy correction must stay inside an explicitly
authorized change surface.

## Memory and company knowledge

Use three distinct stores with different authority:

1. **Business state:** authoritative orders, cases, actions, source observations,
   original forecasts, and policy versions. No semantic retrieval result can
   replace these records.
2. **Task handoff memory:** task intent, input revision, evidence IDs, validated
   findings, attempts, leases, and failure reasons. This is what another worker
   needs to resume safely.
3. **Long-term company knowledge:** approved procedures, supplier terms,
   historical cases, and reference documents with provenance and access rules.

The current plugin implements the first two for its synthetic case. Hermes
native memory can carry scoped preferences or context, but it is not a substitute
for the company record system or a cross-company authorization mechanism.

Start the shared knowledge layer with Postgres metadata plus an evidence object
store; add a vector index when semantic retrieval is needed. Add a graph
projection when real questions require traversing BOM, supplier, order, and
capacity dependencies. A graph database is not required merely because agents
are involved.

Each knowledge item should have tenant/resource identity, source revision,
content hash, observation/effective time, expiry where applicable, classification,
and ACL version. Enforce access **before retrieval and again before returning
source content**, not just when generating a citation. Apply deletion and retention
to indexes, caches, summaries, and exports as well as source documents.

Retrieved supplier/customer text remains untrusted data. It cannot change tool
permissions, spending policy, approval rules, or the interpretation of an
authoritative ERP event.

## Process control and incident response

The following command shapes were verified in local Hermes help. Execute them
only in the intended company's deployment environment/home:

```sh
hermes gateway status --deep
hermes pause --reason "Planned maintenance"
hermes plugins disable agentic-operations
hermes plugins enable agentic-operations
hermes resume
```

`pause` stops new work; it does not cancel work already running or reverse an
external action. Disabling a plugin controls loading/consent; it is not credential
revocation, compensation, or proof that an in-flight request stopped.

For a service-managed gateway, inspect the planned installation before using
`hermes gateway install`, then use the supported `start`, `stop`, `restart`, and
`status` commands. Under an external supervisor, the supported foreground shape
is `hermes gateway run --external-supervisor`. Do not run competing supervisors
or a second poller for the same messaging account.

Avoid routine use of `--all`, `--force`, or interruption flags. These can affect
other profiles or active work. In the inspected version, `dashboard --stop` and
`serve --stop` target all matching web servers, so they are unsuitable for
selectively stopping one independently owned pilot process.

An emergency procedure should:

1. Stop new dispatch and block new connector writes at the authorization gateway.
2. Revoke affected credential scope if needed; preserve logs and action identities.
3. Determine which external effects are confirmed, failed, or uncertain.
4. Reconcile uncertain effects with source systems before any retry.
5. Restore service and authorize a bounded resumption only after an operator review.

## Backup, upgrade, and rollback

For this release, preserve both `operations.db` and `sim_erp.db` and any SQLite
WAL files. Quiesce **all writers** before taking a consistent pair of database
backups; copying a live `.db` file alone is not a backup procedure. Include
configuration, plugin/image identities, and policy-version metadata. Store any
credentials separately in the approved secret-management system.

Test restoration into a fresh isolated home. Confirm the original case forecast,
action identity, confirmed purchase reference, reservations, and active policy.
Reconciliation must not create another simulated purchase.

Upgrade by pausing dispatch, draining or marking interrupted attempts, backing up,
applying a reviewed migration/release, and running readiness/recovery checks.
Retain the previous image/plugin revision. Code rollback and database rollback
are separate decisions: never erase a record of an external effect merely to
make an older schema boot.

Before real company writes, replace this pilot procedure with the company's
tested database/object-store backup, retention, recovery-time, and recovery-point
requirements. Verify connector reconciliation after restore, not only that
the application starts.

## Acceptance record before company writes

Record the owner and evidence for identity/RBAC, tenant isolation, exact exposed
tools, credential scope, connector idempotency, approval expiry, duplicate-source
handling, concurrent reservations, worker termination, restore, version rollback,
egress restrictions, budget enforcement, and audit retention. Include denied
actions and expired/stale results in acceptance testing.

A successful synthetic demonstration is one piece of that record. It does not
authorize real purchasing or establish a manufacturing ROI claim.

## References

- [Hermes dashboard extensions](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard)
- [Hermes source and deployment files](https://github.com/NousResearch/hermes-agent)
- [Temporal documentation](https://docs.temporal.io/)
- [Kubernetes security checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Service contract](contracts.md), [operator guide](operator-guide.md), and [verification record](devin-harness.md).
