---
name: parallel-workstreams
description: Coordinate independent builders with frozen contracts, disjoint ownership, and verified integration.
---

Before launching implementation workers, read `docs/contracts.md` and freeze the service signatures, fixture version, file ownership, and acceptance checks. Split by independent modules, not by vague roles.

Use distinct Git worktrees/branches or isolated Cloud sessions. Local subagents may share the same filesystem. Never assume isolation. One owner controls schema migrations, contract changes, and release metadata.

Give each worker the exact interfaces and behavior to implement, relevant files, hard edge cases, verification commands, and a definition of done. Do not delegate unresolved design choices. Limit concurrent builders to the approved budget; initially two.

Integrate in dependency order. Read each complete diff and consolidate feedback before requesting rework. Run the combined shortage-to-outcome scenario after integration. Mock-backed UI is not a finished integration.

Every handoff reports its branch/commit, owned files, checks, limitations, and any proposed contract change. Preserve active server/process state across handoffs rather than restarting work unnecessarily. Keep commits, publication, user communication, and release decisions with the coordinator.
