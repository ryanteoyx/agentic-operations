# Devin development harness

This document describes how the development harness for this repository is set
up and operated: GitHub, Linear, DeepWiki, Devin skills, Devin Review,
automations, and Cloud environments.

The harness builds and maintains the software. The product runtime (Hermes and
the plugin's own services) runs manufacturing decision cases. A manufacturer's
operations must never depend on a Devin coding conversation staying open.

## Status vocabulary

Every component below carries exactly one status:

- **Prepared** — configuration exists in this repository or is documented as a
  planned step, but no external service has been connected or exercised.
- **Connected** — the external service/account has been linked, but the link has
  not been exercised end to end.
- **Verified** — a real end-to-end exercise succeeded (e.g. a test PR received a
  Review run, a synced label launched a session, a fresh Cloud session booted
  and passed smoke).

Documentation of intent is not a connection; a connection is not a verification.

## Current setup status

| Component | Status | Evidence / next step |
| --- | --- | --- |
| GitHub repository `ryanteoyx/agentic-operations` | Prepared | Initial scaffold lookup returned 404 and local `gh` auth was available; current remote publication is a release-owner check, not established by that earlier lookup |
| Devin GitHub App on this repo | Prepared | CLI auth does not establish the App connection; connect after repo creation |
| CI / branch protection | Prepared | `.github/workflows/ci.yml` now defines bounded Python 3.11/3.14 contract jobs; no hosted CI run or branch protection is verified; add required checks only after the first successful run |
| Linear project "Agentic Operations" | Prepared | Native Devin Linear integration remains unverified — `docs/backlog.md` is the actionable backlog; a verified Mobbin MCP does not establish Linear access |
| DeepWiki | Prepared | `.devin/wiki.json` must use object-array `repo_notes` and `pages`; index after code is pushed and check a generated answer against source |
| Devin skills | Prepared | Repo-local skills under `.devin/skills/`; organization registration needed before synced Linear labels can select them |
| Devin Review | Prepared | Enroll repo/author after GitHub App connection; verify on a real test PR |
| Automations | Prepared | Configure after the first working release |
| Cloud environment blueprint | Prepared | Generate `environment.yaml` via the Declarative Repo Setup skill once commands/deps are stable; verify with a fresh Cloud session |
| Mobbin MCP | Verified | Exercised through the user's OAuth connection, configured at user level; no credentials or account configuration belong in this repository |
| Aside CLI | Verified | Working persistent REPL; this is a development aid, not a runtime service or model-worker proof |
| Impeccable source scan | Verified | Impeccable 4.8.2 read-only source CLI scan reported 0 findings after the microtext fix; this is not UI usability or production-security verification |

Verification is limited to the exercise named in each row. Linear, DeepWiki,
Devin Review, and Cloud account workflows remain unverified. No new hooks were
installed. Product implementation and its separate verification record are
listed below; do not infer an external account connection from working code.

## Operating instructions

### GitHub

- Create the public repository `ryanteoyx/agentic-operations` (assuming name
  availability) and push `main`.
- Connect the Devin GitHub App to the repository for platform write features;
  local `gh` authentication alone does not establish this connection.
- The contract CI workflow is present. Add a PR template and configure required
  status checks **after** a first successful CI run. Require passing checks on
  `main`.
- Configure reviewer requirements only if a real eligible reviewer/approval
  workflow exists — a bot review is not automatically a valid required
  approving review (important for a solo maintainer).
- Keep one logical issue/PR per independent change.
- Keep backups, credentials, session data, generated SQLite files, caches, and
  personal/company documents outside the public tree.
- Original code has an MIT `LICENSE`, retaining notices for any reused code.
  Verify copied examples and dependencies before publishing.

### Linear

- One project: **Agentic Operations**. Initial milestones:
  `M0 — shortage demo and submission`, `M1 — pilot-ready shared operations`.
- Use parent issues/labels for `HARNESS`, `CORE`, `HERMES`, `DEMO`, `EVAL`,
  `CONNECTORS`. Labels are not architectural enforcement.
- Workflow: `Backlog -> Ready -> In Progress -> In Review -> Done`, plus
  `Blocked`.
- Every implementation issue includes: objective and business behavior, owned
  files/modules and dependency issues, contract version, acceptance checks,
  explicit exclusions, expected artifact/testing evidence, and links to its
  branch/PR and decision document.
- Connect through Devin's **native Linear integration**; do not add a redundant
  Linear MCP. Sync the four skill labels through the integration UI. A
  repo-local skill may need to be registered in an organization plugin before
  it can be selected as a synced default — verify its presence first.
- Choose one automatic ticket-start mechanism initially: **assignment to
  Devin**. Use manual skill labels intentionally; do not attach an automation
  to the same assignment/label event, which could launch duplicate sessions.
  Independent ticket assignments start independent sessions; they do not
  inherently create a coordinating parent or manage shared contracts.
- Until connected, `docs/backlog.md` is the actionable backlog. Do not hold
  development for OAuth, and do not claim issues exist in Linear when they only
  exist in Markdown.

### DeepWiki

- DeepWiki documents the **code**; the product's Company Playbook describes
  manufacturing policies. Keep them separate.
- `.devin/wiki.json` is maintained by the coordinator. `repo_notes` must be an
  array of objects and `pages` an array of page objects — the earlier
  string/string-array shape is invalid.
- When `pages` is present, only the listed pages are generated; include every
  intended topic.
- After pushing code, index the repository/default branch in Devin and check a
  generated answer against actual source. Indexing is separate from a working
  Cloud environment.

### Skills

- Keep `AGENTS.md` short: source locations, invariants, commands, pointers to
  skills. Do not paste the whole research brief into every session.
- Available repo-local skills: `implement-case-feature`, `parallel-workstreams`,
  `prepare-demo`, `weekly-ops-review` under `.devin/skills/`.
- New reusable Devin guidance should use **Skills/Plugins** — Knowledge and
  Playbooks are migrating; do not build around them.
- For reuse across Cloud/Linear later, package canonical skill sources in a
  Devin plugin or register reviewed versions at organization scope. Avoid
  manually maintaining divergent copies.
- A separate team marketplace repository is unnecessary for the first sprint.

### Devin Review

- Enroll the connected repository and author in Review.
- Use automatic review initially; the coordinator resolves findings.
- Enable Auto-Fix only after the first integration if desired, with bot
  responses set to **Selected only** and `devin-ai-integration[bot]` allowed.
- Assign one writer to a PR branch while fixes are running; do not respond to
  every bot.
- Configure a finite per-PR review budget in the account's actual billing
  units — do not assume a specific ACU amount; inspect billing first.
- Verify a real test PR receives a review; documentation alone is not setup
  completion.

### Automations (after the first working release)

| Automation | Trigger | Result | Initial bounds |
| --- | --- | --- | --- |
| Broken CI repair | A failed relevant CI check on an open project PR | Diagnose or amend the existing PR | One active repair per PR; at most two attempts per failure chain |
| Nightly scenario regression | Schedule in Asia/Singapore | Publish a test artifact; create an issue only for a new failure | One run, finite session budget |
| Weekly development review | Weekly Schedule trigger | Proposed skill/docs/backlog improvements | One proposal batch; no unbounded child-session fanout |
| Dependency maintenance | Weekly schedule or dependency PR | Bounded updates plus installation/scenario checks | Avoid overlapping repair writers |

Use **Automations with Schedule triggers** for new scheduled work; legacy
Scheduled Sessions is not the preferred setup. Use invocation limits and
queueing — a per-automation concurrency limit is not a global organization
limit, and queue overflow can drop events, so the issue/CI system remains the
durable source of work.

### Cloud setup

- Once commands and dependencies are stable, invoke the Declarative Repo Setup
  skill to generate and verify `environment.yaml`. Include Python, the tested
  Hermes reference, dependency installation, and actual smoke commands. Do not
  invent a blueprint format or label an unbuilt YAML a working snapshot.
- Verification requires a fresh Cloud session to boot and run the documented
  checks. Any required account-level blueprint approval happens on a concrete
  generated configuration.

## Corrected assumptions (from planning audit, 12 Nov 2026)

1. DeepWiki `repo_notes`/`pages` are arrays of objects, not strings.
2. Prefer Skills/Plugins over Knowledge and Playbooks for reusable guidance.
3. Prefer Automations Schedule triggers over legacy Scheduled Sessions.
4. Parallel Linear ticket assignments start independent sessions; they do not
   create a coordinating parent.
5. A bot review is not automatically a valid required approving review;
   configure branch protection to match the real account.
6. Inspect the account's billing units before setting limits; no universal ACU
   default exists.
7. Hermes observer hooks fail open — required validations live in service
   transactions, not hooks.
8. Persisted agent handles/chat history do not make child execution
   restartable; persist business work and reconcile its effects.
9. Runtime plugin modules must live inside the installed plugin tree.

## References

- [Linear integration](https://docs.devin.ai/integrations/linear)
- [DeepWiki configuration](https://docs.devin.ai/work-with-devin/deepwiki)
- [Repository indexing](https://docs.devin.ai/onboard-devin/index-repo)
- [GitHub integration](https://docs.devin.ai/integrations/gh)
- [Devin Review](https://docs.devin.ai/work-with-devin/devin-review)
- [Review Auto-Fix](https://docs.devin.ai/use-cases/gallery/devin-review-autofix)
- [Automations](https://docs.devin.ai/product-guides/automations)
- [Advanced capabilities](https://docs.devin.ai/work-with-devin/advanced-capabilities)
- [Environment blueprints](https://docs.devin.ai/onboard-devin/environment/blueprints)
- [Blueprint reference](https://docs.devin.ai/onboard-devin/environment/blueprint-reference)

## Product verification record

Recorded checks for release preparation on 12 November 2026.

The current UI names the product **Agentic Operations**, company **Orange**,
and suppliers **Banana · economy**, **Grapefruit · priority**, and
**Plum · unapproved**; stable business IDs are unchanged. Its charcoal/teal/
ice-cyan palette references Transcelestial, and the information hierarchy
references Linear/Shopify examples through Mobbin. The four tabs are
Overview/Plan/Activity/Outcome, with a contextual primary action and public,
redacted **Download case** JSON. Design references are not independent
usability or production-security evidence.

### Tests already run

The repository-wide command is:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

| Scope | Environment | Actual result |
| --- | --- | --- |
| Core contracts | Python 3.11 and Python 3.14 | 48 passed on each |
| Combined core and adapter suite | Python 3.11.15 | 58 total: 57 passed, 1 optional FastAPI test skipped because host dependencies were absent |
| That single previously skipped FastAPI test | Existing Hermes PM environment, Python 3.14.9 | Passed separately; this was not a rerun of the complete suite under that interpreter |

Coverage includes constrained planning, stale revisions, shared-resource
reservation checks, stable action identity, owned-process interruption and
fresh-process recovery, original forecasts and v2 correction, installed-copy
loading, profile separation, public schemas, standalone HTTP boundaries, and
bounded worker success/failure/timeout/staleness. Model calls in tests use
stubs; these results do not establish live provider access.

The checked fixture expectations are v1 sales forecast **h48**, observation
**h72**, forecast error **+24 hours**, deadline miss **12 hours** against h60;
v2 priority forecast/observation **h54**; and warranty shipment **h16**.
Crash recovery uses an owned-process exit **73** after simulated ERP commit,
then a fresh process reconciles **one matching PO**. The original v1 forecast
is immutable. These are tested fixture contracts, not final release-SHA
measurement or capture results.

### Native Hermes checks already run

Host reference: **Hermes 0.23.1+2046.gb5f15a6**, source revision
**`b5f15a6d31`**, with an isolated profile.

- Plugin validator passed for the updated dashboard bundle; the plugin was enabled.
- `agentic_operations` registered **11 tools**.
- `hermes ops seed`, `hermes ops list`, and `hermes ops playbook` were exercised.
- Native HTTP checks for plugin UI
  (`/api/plugins/agentic-operations/ui`), plugin health
  (`/api/plugins/agentic-operations/health`), and the host toolsets endpoint
  returned **401 anonymously** and **200 with normal host authentication**.
  The host auth boundary was not bypassed.
- The `#plugin/hermes_ops` repository-subdirectory install syntax was checked
  against the host's `plugins_cmd._resolve_git_url`. This is not proof of an
  installation from the exact published release revision.

**Native browser workflow passed** at `http://127.0.0.1:8770/operations` under
the isolated Hermes profile. The IIFE entry loads the embedded plugin UI
through the public SDK, and API requests use `SDK.authedFetch`. The real-host
browser flow `/operations` → iframe → seed → plan → select → execute →
observe → correction completed with all requests returning **200**, no
authenticated **401s**, and no JavaScript errors. Anonymous access to
`/api/plugins/agentic-operations/ui` remained **401**. Screenshot:
`artifacts/native-pilot/native-operations.png`.

Native **Desktop** integration is not implemented. Live provider/model
investigation was **not attempted**: the isolated profile has no provider
credentials. `ops_investigate` is a bounded no-tools model task, not autonomous
subagent execution. Its 60-second model wait, 90-second durable attempt lease,
and two-attempt core checks do not provide automatic redispatch or a public
resume control; each new tool request creates a new task.

### CI scope and reproducibility

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs only the contract
suite on `ubuntu-latest` with Python **3.11** and **3.14**. Jobs have a
10-minute timeout, read-only repository permission, and cancel superseded runs
in the same workflow/ref group. There are no unbounded background jobs or
dependency-install steps.

Action revisions were checked against their GitHub commit references:

- `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` — v4.2.2.
- `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` — v5.6.0.

The optional FastAPI route test skips when host dependencies are not available.
The standalone product is standard-library-only; the separate native-host
result above covers the skipped test's host environment. No GitHub Actions
success or required branch check is claimed before an actual hosted run.

The deterministic reproduction command is:

```sh
python3 demo/run_demo.py --artifacts ./artifacts/recovery-proof
```

It uses fresh temporary data by default and writes stage JSON plus
`result.json`. The clean installed release measurement passed on 12 November
2026; the evidence is recorded below. Optional video capture/render tooling is described in
[`demo/video/README.md`](../demo/video/README.md), separate from product
dependencies.

### Documentation/CI checks performed

`git diff --check` and whitespace/final-newline checks passed, including checks
of the new operator guide and CI workflow. The existing Ruby/Psych parser
accepted the workflow, and a read-only comparison confirmed the SHA-pinned
YAML matched the specified configuration without installing dependencies.
Local Markdown links and heading anchors resolved, including the company
deployment guide.

### Published release verification — 12 November 2026

Release source: **`dd4a6cf563a03b65231e30f3b32338ab1fe5a113`**.
The source was published at approximately 04:17 SGT. The release and video
were published at **05:19 SGT**, before the requested 05:30 delivery deadline.

| Gate | Recorded result and evidence |
| --- | --- |
| Exact public install | URL/subdirectory install with `--ref` set to the full SHA and `--enable`, in fresh `artifacts/release/hermes-home`; installer metadata recorded `pinned: true` and the matching revision. Installed package bytes matched the source. |
| Hermes validator | `hermes plugins validate <installed-root> --install-deps` passed on the existing Hermes v0.23.1+ source environment (`b5f15a6d31`). Security scan safe; registration and declarations matched; no core overrides. The URL install carried the expected “custom/unreviewed source” notice. |
| Installed readiness | `hermes tools list` showed enabled `agentic_operations`; `hermes ops list` returned an empty workspace before the scenario. |
| Actual recovery | `capture.py` used the clean installed runtime and a fresh synthetic namespace. Owned child exited 73 after ERP commit; fresh recovery process exited 0; one purchase order existed for the original action. |
| Outcomes | V1 sales: forecast h48, observed h72, +24h forecast error, 12h late. V2 sales: forecast and observed h54, no lateness. Both warranty commitments met; original v1 prediction preserved. |
| UI evidence | All nine checkpoint screenshots, case identities, source/recording hashes, and measurements reviewed. Zero browser console, HTTP, or request errors. |
| Hosted CI | [Python 3.11 and 3.14 passed](https://github.com/ryanteoyx/agentic-operations/actions/runs/43095080567) for the exact release SHA. |
| Video | Hyperframes 0.9.34, two workers, no fallback: 82.000 seconds, 2460 frames, 1920×1080 at 30fps, H.264/yuv420p and stereo AAC/48kHz. Decode, narration/caption provenance, and visual checks passed. Final entrant listening remains part of X-post approval. |
| Publication | [v0.1.0 release, MP4, and evidence](https://github.com/ryanteoyx/agentic-operations/releases/tag/v0.1.0). GitHub asset digest matched local video SHA-256 `7ec42d9a5d9d4f5d466ef940ff9f24e0518d2e75ce70a0f595de4f288a1170c0`. |
| Catalog | [PR #153990](https://github.com/NousResearch/hermes-agent/pull/153990), verified **OPEN**, not draft, at 05:19 SGT. Maintainer review and merge remain pending. |

Local records are under `artifacts/release/verification/` and
`artifacts/video/capture-release/`. The public release evidence omits local
paths and includes the measured results and reviewed editorial cuts.
The original automatic video-offset calculation included encoder tail time;
the delivered edit uses corrected cuts matched to the approved screenshots.
Frozen recording and business measurements were not changed. See the
[video tooling limitation](../demo/video/README.md#published-v010-video).

The X account was reported temporarily limited. No X post or final Typeform
submission has been made. Entrant listening/approval and a working authenticated
posting surface remain necessary. Linear, Review, and other account-level
connections are still governed by the setup status above.

This release uses only synthetic ERP actions and SQLite on a single host.
Production ERP connectors, Temporal, Postgres, shared company memory, RBAC,
and Desktop integration are not implemented. The
[company deployment guide](company-deployment.md) describes architecture and
readiness requirements, not installed production infrastructure. Synthetic
fixture outcomes are not ROI evidence. Impeccable's zero-finding source scan
does not establish UI usability or production security.
