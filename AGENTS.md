# Agentic Operations

- Runtime code is self-contained in `plugin/hermes_ops/`; the installed plugin must not depend on repository siblings.
- Read `docs/contracts.md` before changing service interfaces, fixtures, or state transitions.
- All demo business data is synthetic. Never publish credentials, Hermes backups, session databases, or company documents.
- Tools, commands, and UI use the same core services. Agents cannot bypass constraints or write authoritative observations.
- Persist action intent before connector execution; reconcile uncertain results before retrying. Preserve stable logical action identity.
- Keep model calls and connector waits outside database transactions.
- Monetary values use integer minor units; times and quantities have explicit units.
- Use `.devin/skills/implement-case-feature` for features, `parallel-workstreams` for concurrent work, and `prepare-demo` for releases.
- Verification commands and setup status are recorded in `docs/devin-harness.md`; do not claim checks or account connections that have not run.
- Preserve existing comments unless explicitly asked to change them.
