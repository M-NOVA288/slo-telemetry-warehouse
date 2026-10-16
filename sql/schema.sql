-- Star schema for request telemetry (runs on SQLite locally; Snowflake version in sql/snowflake/).
-- Grain of fact_request: one row per unique event_id.

CREATE TABLE IF NOT EXISTS dim_service (
    service_key   INTEGER PRIMARY KEY,
    service_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_endpoint (
    endpoint_key  INTEGER PRIMARY KEY,
    service_key   INTEGER NOT NULL REFERENCES dim_service(service_key),
    endpoint_path TEXT NOT NULL,
    UNIQUE (service_key, endpoint_path)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,          -- YYYYMMDD
    calendar_date TEXT NOT NULL,
    day_of_week   INTEGER NOT NULL              -- 0 = Sunday
);

CREATE TABLE IF NOT EXISTS fact_request (
    event_id      TEXT PRIMARY KEY,             -- natural key: makes reloads idempotent
    date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    event_hour    INTEGER NOT NULL,
    endpoint_key  INTEGER NOT NULL REFERENCES dim_endpoint(endpoint_key),
    status_code   INTEGER NOT NULL,
    is_good       INTEGER NOT NULL,             -- 1 if status_code < 500
    duration_ms   REAL NOT NULL,
    trace_id      TEXT,
    loaded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine (
    source_file   TEXT NOT NULL,
    line_number   INTEGER NOT NULL,
    raw_line      TEXT NOT NULL,
    reason        TEXT NOT NULL,
    loaded_at     TEXT NOT NULL,
    PRIMARY KEY (source_file, line_number)      -- re-running a load does not re-quarantine the same line
);

CREATE TABLE IF NOT EXISTS load_audit (
    run_id          TEXT PRIMARY KEY,
    source_file     TEXT NOT NULL,
    lines_read      INTEGER NOT NULL,
    rows_inserted   INTEGER NOT NULL,
    duplicates      INTEGER NOT NULL,
    quarantined     INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slo_target (
    service_name      TEXT PRIMARY KEY,
    availability_slo  REAL NOT NULL,            -- e.g. 0.995
    latency_slo_ms    REAL NOT NULL,            -- p95 threshold
    latency_slo_share REAL NOT NULL             -- share of requests that must be under threshold
);

CREATE INDEX IF NOT EXISTS ix_fact_date ON fact_request(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_endpoint ON fact_request(endpoint_key);
