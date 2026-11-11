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

## Current status (initial scaffold)

| Component | Status | Evidence / next step |
| --- | --- | --- |
| GitHub repository `ryanteoyx/agentic-operations` | Prepared | `gh` CLI is authenticated locally as `ryanteoyx`; the proposed repo lookup returned 404, so creation is still required |
| Devin GitHub App on this repo | Prepared | CLI auth does not establish the App connection; connect after repo creation |
| CI / branch protection | Prepared | Add CI and PR template first; add required status checks after a first successful CI run |
| Linear project "Agentic Operations" | Prepared | MCP discovery found no connected servers; native Devin Linear integration not yet connected — `docs/backlog.md` is the actionable backlog until it is |
| DeepWiki | Prepared | `.devin/wiki.json` must use object-array `repo_notes` and `pages`; index after code is pushed and check a generated answer against source |
| Devin skills | Prepared | Repo-local skills under `.devin/skills/`; organization registration needed before synced Linear labels can select them |
| Devin Review | Prepared | Enroll repo/author after GitHub App connection; verify on a real test PR |
| Automations | Prepared | Configure after the first working release |
| Cloud environment blueprint | Prepared | Generate `environment.yaml` via the Declarative Repo Setup skill once commands/deps are stable; verify with a fresh Cloud session |

Nothing in this table is connected or verified yet. Until a component reaches
**Verified**, do not claim it works.

## Operating instructions

### GitHub

- Create the public repository `ryanteoyx/agentic-operations` (assuming name
  availability) and push `main`.
- Connect the Devin GitHub App to the repository for platform write features;
  local `gh` authentication alone does not establish this connection.
- Add CI, a PR template, and required status checks **after** a first
  successful CI run. Require passing checks on `main`.
- Configure reviewer requirements only if a real eligible reviewer/approval
  workflow exists — a bot review is not automatically a valid required
  approving review (important for a solo maintainer).
- Keep one logical issue/PR per independent change.
- Keep backups, credentials, session data, generated SQLite files, caches, and
  personal/company documents outside the public tree.
- Proposed license for original code: MIT, retaining notices for any reused
  code. Verify copied examples and dependencies before publishing.

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
- Planned repo-local skills: `implement-case-feature`, `parallel-workstreams`,
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
