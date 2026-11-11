# Agentic Operations — synthetic manufacturing control room

A self-contained Hermes plugin for a supplier-shortage decision case. Tools, the browser UI, and the CLI call the same `OpsService`. The model does not implement business rules or write observations.

## Run the browser demo

From a complete checkout (adapter and `manufacturing_ops` core integrated):

```sh
python3 demo/serve.py --port 8765 --data-dir /tmp/orange-demo
```

Open `http://127.0.0.1:8765`. This server uses Python's standard library. No package installation, API key, Hermes startup, CDN, npm build, or outbound network connection is needed. An explicit data directory is required.

The command shape, HTML response, health endpoint, real HTTP workflow, and restart-independent installed-copy imports were exercised. Python 3.11 is supported; the adapter tests passed on Python 3.11.15.

1. **Seed demo case** creates an independent virtual manufacturer and opens the Overview tab.
2. **Compare recovery plans** (Plan tab) evaluates candidates; rejected suppliers and missed deadlines stay visible. **Approve** the recommended plan to reserve stock and persist the action intent.
3. **Place simulated order** (Activity tab) executes against the independent simulated ERP; **Recover purchase order** reconciles the same logical action when the outcome is uncertain.
4. **Observe simulated outcome** (Outcome tab) advances the clock and evaluates: v1 economy forecasts sales shipment at h48 but observes h72, a +24-hour forecast error and 12-hour deadline miss.
5. **Activate corrected estimate**, then **Start next case**. The new workspace captures v2: economy becomes infeasible and priority forecasts/observes sales shipment at h54.
6. Advancing to at least h96 also observes the original replenishment, which was never cancelled.

Costs are SGD integer cents. SGD 60/140 are incremental expedite surcharges, not total purchase values. The additional six-component purchase principal is SGD 300. No real ROI, working-capital, or cash-flow claim is made.

## Hermes integration

The complete installed directory must contain this adapter **and** `manufacturing_ops/__init__.py`, `service.py`, the core's supporting modules, and its synthetic fixture. Copying only the adapter files is not an installation. Runtime code never imports a repository sibling and does not mutate global `sys.path`.

`plugin.yaml` requires Hermes `>=0.23.1`. `register(ctx)` registers eleven public tools and the `ops` CLI parser. It registers no hooks, overrides, or privileged capability requests:

| Tool | Purpose |
| --- | --- |
| `ops_seed_demo` | Fresh workspace or idempotent explicit workspace ID |
| `ops_list_cases`, `ops_case` | Inspect persisted state |
| `ops_investigate` | One bounded no-tools evidence-review model task |
| `ops_plan`, `ops_select_plan` | Evaluate, then reserve at an expected revision |
| `ops_execute`, `ops_reconcile` | Durable synthetic action and outcome lookup |
| `ops_advance_demo` | Advance the synthetic clock |
| `ops_evaluate` | Compare original forecast with source observations |
| `ops_activate_correction` | Evidence-backed estimate update with policy-version check |

Tool handlers return JSON strings. Request schemas reject unknown properties; quantities, IDs, and revisions are bounded. There is no public crash flag.

The host dashboard API is mounted at `/api/plugins/agentic-operations`. The manifest registers a native **Operations** tab at `/operations`: its `dist/index.js` entry loads the plugin UI into an iframe via the supported `window.__HERMES_PLUGIN_SDK__` bridge, and the embedded page issues all API calls through `SDK.authedFetch`, so normal host session-token authentication applies with no tokens stored or copied by the plugin. The iframe is styling isolation only, not a security boundary. This is web-dashboard integration; the Desktop app is a separate surface the plugin does not extend. Verified end-to-end under an isolated profile: the Operations tab is discoverable, the embedded workspace completes the seed→plan→select→execute→observe→correction flow over authenticated API calls, and anonymous requests remain 401.

Hermes data resolves **per call** through `plugins.plugin_storage.plugin_data_dir("agentic-operations")`. There is no process-global profile data root. The host FastAPI router inherits the dashboard's authentication; the standalone server does not import or require FastAPI.

Registration was tested against a context stub matching the installed public API. The FastAPI router test runs only when host FastAPI dependencies are present and is otherwise skipped. `hermes plugins validate` passed against the local Hermes source checkout at `b5f15a6` (v0.23.1+); plugin discovery, enable, and the `ops` CLI were smoke-tested under an isolated profile. Validate each deployed copy against its exact published commit SHA. No default Hermes installation or global settings were changed.

## Evidence review is not an autonomous subagent

The inspected host lifecycle implementation converts an empty `allowed_toolsets` tuple to inherited parent tools and does not support the required arbitrary blocked-tool set. Launching that worker would not satisfy the no-tools requirement.

This adapter therefore uses the approved `ctx.llm.complete_structured` fallback, labelled `bounded_model_task` and `actual_subagent: false`. It uses only the active host model; it never reads credentials or imports private agent classes.

The supplied review prompt is preserved verbatim. Input contains only the original supplied evidence, usable stock, both order IDs/quantities, and the BOM component quantity. Hidden supplier cutoff data is excluded.

Task creation and attempt start commit before the model call. The host request timeout is 60 seconds, and a separate 60-second bounded wait prevents late results from being accepted. The worker thread explicitly inherits context variables; only the waiting caller can persist a result. Timeouts/unavailability fail the durable task. The fallback API offers no remote cancellation handle: a provider may continue an already-sent request after timeout, but its result is discarded and cannot change the case.

Worker attempts carry a 90-second durable lease. An expired RUNNING attempt becomes INTERRUPTED when the service next opens or reads cases, and can be reclaimed with a new attempt ID. Each task allows at most two attempts. A restart does not automatically redispatch model work.

Strict raw JSON validation rejects markdown, duplicate/unknown keys, unknown citations, missing order IDs, and incorrect shortage quantities. The core checks attempt identity and input revision again when accepting the result. Only the active-turn tool path invokes a model; HTTP has no worker-launch endpoint. **Investigate** in the browser refreshes actual state and explains how to invoke the Hermes tool. It never claims a model is running.

## Python CLI

The module CLI was exercised from outside the repository against a copied, complete installed subtree:

```sh
PYTHONPATH=plugin python3 -m hermes_ops.manufacturing_ops.cli --data-dir /tmp/orange-demo seed
```

It exposes seed, list, case, plan, select, execute, reconcile, advance, evaluate, correction, and playbook operations. The same parser is registered with Hermes; model investigation is intentionally tool-only.

## API and local-server boundaries

GET: `/api/health`, `/api/cases`, `/api/cases/{id}`, `/api/playbook`.

POST: `/api/demo/seed`, `/api/cases/{id}/plan`, `/select`, `/execute`, `/reconcile`, `/advance`, `/evaluate`, `/correction`.

The standalone listener binds **only `127.0.0.1`**. It rejects non-loopback Host values, foreign Origin values, cross-site fetches, and mutations lacking the process-local `X-Ops-CSRF` token embedded in the served HTML. JSON bodies are limited to 64 KiB; transfer-encoded requests are refused. There is no CORS support and no filesystem-serving endpoint. Do not expose it through a public reverse proxy.

Unknown IDs return 404; invalid input 422; stale-state conflicts 409. Responses never expose worker capability handles or Python tracebacks. Local browser access is not a protection against another process already running as the same user.

All demo business data is synthetic. SQLite state belongs only in the explicit data root or the active Hermes profile's plugin storage, never the installation tree. No real ERP is connected and no real supplier order is placed.

## Checks and integration boundary

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Run from the repository root; the adapter tests exercise the real integrated `manufacturing_ops` core, not a mock. The combined suite (core plus adapter) passed on Python 3.11.15: 57 tests passed, 1 skipped (the optional FastAPI route test, skipped when host FastAPI dependencies are unavailable). Coverage includes stdlib route security and error mapping, complete v1/correction/v2 HTTP outcomes, installed-copy loader caching/no `sys.path` changes, profile separation, tool registration/closed schemas, outside-repository CLI, and bounded worker success/failure/timeout/staleness. Model calls use a context stub in tests; no live model invocation was made.

Native web dashboard interaction passed under the isolated Hermes profile. Revision-specific release evidence is recorded in the [release notes](https://github.com/ryanteoyx/agentic-operations/releases).
