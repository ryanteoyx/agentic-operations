from __future__ import annotations


class ConflictError(Exception):
    pass


CASE_STATES = (
    "OPEN",
    "INVESTIGATING",
    "READY",
    "EXECUTING",
    "OBSERVING",
    "NEEDS_ATTENTION",
    "CANCELLED",
    "CLOSED",
)

TASK_STATES = (
    "PENDING",
    "CLAIMED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "INTERRUPTED",
    "CANCELLED",
    "NEEDS_ATTENTION",
)

ACTION_STATES = (
    "PREPARED",
    "IN_FLIGHT",
    "CONFIRMED",
    "UNCERTAIN",
    "RECONCILING",
    "RETRYABLE_FAILED",
    "NEEDS_ATTENTION",
    "CANCELLED",
)
