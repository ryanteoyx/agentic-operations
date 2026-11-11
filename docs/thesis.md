# Durable decision cases for manufacturing operations

## Thesis

Manufacturing agents need a durable unit of decision and accountability, not just better conversations. A **decision case** connects fragmented operating evidence, constrained alternatives, delegated work, external effects, and observed outcomes. Agents can assist formulation while deterministic application services preserve constraints and the execution history.

The initial product is one Hermes plugin. Its first case spans a supplier delay, BOM requirements, usable stock, a warranty replacement, a sales commitment, purchasing, production capacity, and shipment outcomes. It does not replace an ERP or claim to model an entire factory.

## Why this boundary

CRM, ERP, and production systems may each be internally consistent while cross-department decisions remain unresolved. A sales promise depends on materials, quality release, capacity, and supplier behavior; a purchasing action changes cash and inventory exposure; a return creates another fulfillment obligation.

The missing object is the cross-system situation and its outstanding obligations. A chat transcript is not enough: it does not reserve stock, reconcile an uncertain purchase order, or distinguish “the agent finished” from “the customer received the replacement.”

Percepta's Agentic Operations Research agenda motivates a tighter formulation–solution–outcome loop. McKinsey's supply-chain discussion highlights cross-system available-to-promise and capable-to-promise decisions. BCG describes agents orchestrating algorithms and scenario tools. These support the product direction, not a claim that this prototype has achieved their reported outcomes. See [sources and evidence limits](research-sources.md).

## What is reused and what is built

Hermes supplies model access, tool registration, child-agent lifecycle, and interface extension points. SQLite supplies local transactions. The application adds case state, evidence/policy versions, shared resource reservations, logical action identity, reconciliation, observations, and correction history.

A worker is replaceable. Its task intent and accepted result persist independently. An external effect is not assumed absent just because the worker or host failed before acknowledging it.

## Demonstration method

The synthetic manufacturer has six components but needs twelve: four for a warranty replacement and eight for a sales order. The first estimate misses an economy supplier's order cutoff. The plan appears feasible but the observed sales shipment is late.

The demonstration deliberately terminates an owned process after the simulated ERP commits a purchase order and before the operations service records acknowledgement. A fresh process finds the same order by stable action identity rather than creating another.

After observing the receipt and shipments, the application proposes a versioned cutoff correction. A subsequent independent synthetic case uses the corrected estimate and chooses the faster approved supplier. Original predictions remain available.

The expected values and constraints are frozen in [contracts](contracts.md). The executable measurement recipe is `demo/run_demo.py`; its output distinguishes synthetic outcomes from actual worker execution.

## Results

Measured results will be added after the integrated demonstration runs. Expected fixture values are not represented as executed test results.

## What this does not establish

- Real manufacturing ROI, labor savings, or working-capital improvement.
- Generalization beyond the synthetic scenario.
- A learned world model, calibrated superforecasting, or reinforcement learning.
- Universal exactly-once external effects; connector idempotency and lookup support remain necessary.
- Unattended availability or production multi-user deployment.

The versioned correction is an explainable estimate update based on explicit supplier evidence. It is not unrestricted self-modification. A higher spending limit or changed customer priority would require a separate operating-policy decision.

## Next experiment

Compare a simple operational heuristic, the deterministic case system, and an agent-assisted case system on the same versioned scenarios. Measure formulation accuracy, constraint violations, duplicate effects, recovery, case lead time, forecast error, incremental cost, inventory exposure, and human interventions separately.

Use held-out variants for stock changes, supplier cutoffs, budget exhaustion, partial shipments, and conflicting cases. Then run read-only shadow recommendations with one manufacturer's real source data. Only observed business outcomes and a defensible comparison can support an impact claim.
