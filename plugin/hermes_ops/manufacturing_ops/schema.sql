CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    currency TEXT NOT NULL,
    timezone TEXT NOT NULL,
    base_instant TEXT NOT NULL,
    stock_units INTEGER NOT NULL,
    clock_hour INTEGER NOT NULL DEFAULT 0,
    policy_version INTEGER NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL,
    trigger_key TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    snapshot TEXT NOT NULL,
    options TEXT,
    prediction TEXT,
    evaluation TEXT,
    selected_plan_id TEXT,
    attention_reasons TEXT,
    created_hour INTEGER NOT NULL,
    UNIQUE (workspace_id, trigger_key)
);

CREATE TABLE IF NOT EXISTS obligations (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    due_hour INTEGER NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    case_id TEXT NOT NULL REFERENCES cases(id),
    kind TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    start_hour INTEGER,
    end_hour INTEGER,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    input_revision INTEGER NOT NULL,
    attempt_id TEXT,
    handle TEXT,
    lease_until REAL,
    result TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    connector TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    external_ref TEXT
);

CREATE TABLE IF NOT EXISTS action_attempts (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(id),
    n INTEGER NOT NULL,
    status TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    case_id TEXT REFERENCES cases(id),
    kind TEXT NOT NULL,
    at_hour INTEGER NOT NULL,
    payload TEXT NOT NULL,
    source_event_key TEXT,
    UNIQUE (workspace_id, source_event_key)
);

CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    state TEXT NOT NULL,
    evidence TEXT NOT NULL,
    proposal TEXT NOT NULL,
    prev_version INTEGER NOT NULL,
    new_version INTEGER,
    UNIQUE (case_id)
);
