# Research sources

Primary references inspected during planning (audit of 12 November 2026) and
the limits of what each one supports. Sources back the architectural choices;
they do not validate product claims.

## Devin

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
- Local skill/configuration/plugin documentation under
  `/Applications/Devin.app/Contents/Resources/app/extensions/windsurf/devin/share/devin/docs`
  (read during planning).

## Hermes

- [v0.23.1 release](https://github.com/NousResearch/hermes-agent/releases/tag/v0.23.1)
- [Plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
- [Public plugin API](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/public-api)
- [Subagent lifecycle](https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api)
- [Plugin LLM access](https://hermes-agent.nousresearch.com/docs/developer-guide/plugin-llm-access)
- [Observer hooks](https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks)
- [Desktop SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk)
- [Catalog submission](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission)
- [Updating](https://hermes-agent.nousresearch.com/docs/getting-started/updating)
- [Official examples](https://github.com/NousResearch/hermes-example-plugins)
- Source read at v0.23.1: `agent/subagent_lifecycle.py`,
  `plugins/plugin_storage.py`, `hermes_cli/plugins_context.py`,
  `hermes_cli/plugins_loader.py`, `hermes_cli/web_server_dashboard.py`, and
  `plugin-catalog/README.md`.
- Installed source read at `/Users/ryanteoyx/.hermes/hermes-agent`:
  `AGENTS.md`, plugin loader/examples, update parser/implementation, and
  plugin LLM/dashboard documentation.

Evidence limit: published API existence still requires installed-host
validation. The installed Hermes is a June 2026 detached checkout that lacks
`agent/subagent_lifecycle.py` and `plugins/plugin_storage.py`; the current docs
cannot be applied to it without upgrading.

## Product / research

- [Percepta: Agentic Operations Research](https://www.percepta.ai/blog/agentic-operations-research)
- [McKinsey: Powering supply chain with agentic AI](https://www.mckinsey.com/capabilities/operations/our-insights/powering-supply-chain-with-agentic-ai)
- [BCG: Agentic AI in industrial goods](https://www.bcg.com/publications/2025/agentic-ai-industrial-goods-driving-change)
- [Temporal activity idempotency](https://docs.temporal.io/activity-definition)
- [OR-Tools job shop](https://developers.google.com/optimization/scheduling/job_shop)
- [ERPNext license](https://github.com/frappe/erpnext/blob/develop/license.txt) — GPLv3
- [Odoo Community license](https://github.com/odoo/odoo/blob/master/LICENSE) — LGPLv3 (other editions/addons may differ)

### What each research source supports

| Source | Supported insight | Product implication | Evidence limit |
| --- | --- | --- | --- |
| Percepta Agentic OR | Tighten the formulation/solution/outcome loop; represent decision-relevant operational state | Version case evidence, constraints, predictions, and outcomes | Research agenda; not proof this MVP is a learned world model |
| McKinsey agentic supply chain | Cross-system ATP/CTP and execution are a practical bottleneck | Use a shortage spanning orders, stock, supply, and capacity | Reported consulting examples do not establish our ROI |
| BCG industrial goods | Agents can expose and orchestrate algorithms and scenario tools | Keep deterministic planning accessible through a business interface | Vendor/client reports are not controlled comparisons |
| Temporal documentation | Retried activities need idempotent effects | Preserve connector action identity and reconcile uncertainty | A workflow engine alone cannot guarantee exactly-once effects |
| Hermes source/docs | Extensible tools, UI, model access, and ephemeral worker lifecycle | Reuse the host; build durable business state explicitly | Published API existence still requires installed-host validation |

## Event / context

- [User-supplied Nous announcement](https://x.com/nousresearch/status/2118094256438936062)
- [Indexed announcement mirror](https://nitter.gq/NousResearch/status/2118094256438936062) — corroborated the announcement; direct X/oEmbed retrieval did not return a usable post during the audit
- [Submission form supplied in prior context](https://form.typeform.com/to/FwJLvOln) — acceptance status unverified
- [User-supplied Percepta article](https://percepta.ai/blog/shared-intelligence-for-the-decisions-we-depend-on) — original content not retrieved in the audit
- [User-supplied Athul thread](https://x.com/apjacob03/status/2120287800591315244) — original content not retrieved in the audit

The Percepta shared-intelligence URL and the Athul X post remain here as
supplied context until their original content can be retrieved. Do not
fabricate additional X insights, and do not treat the long pasted research
summary as verified documentation.
