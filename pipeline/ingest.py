"""
Idempotent ingest: JSON log lines -> validated, de-duplicated star schema in SQLite.

  - Validates every line against the log contract (required fields and types)
  - Sends bad lines to a quarantine table with a reason, instead of failing the load
  - Uses event_id as the natural key, so re-running the load never creates duplicates
  - Writes one load_audit row per run (lines read, inserted, duplicates, quarantined)

Run: python -m pipeline.ingest data/sample_logs.jsonl warehouse.db
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "sql" / "schema.sql"

REQUIRED = {
    "event_id": str, "timestamp": str, "service": str, "endpoint": str,
    "status_code": int, "duration_ms": (int, float),
}
SLO_TARGETS = [  # service, availability SLO, latency threshold ms, share that must be under it
    ("checkout", 0.995, 800.0, 0.95),
    ("analyzer", 0.999, 800.0, 0.95),
    ("webhooks", 0.999, 500.0, 0.95),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def validate(line):
    """Return (record, None) if valid, else (None, reason)."""
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None, "unparseable_json"
    if not isinstance(rec, dict):
        return None, "not_an_object"
    for field, typ in REQUIRED.items():
        if field not in rec:
            return None, f"missing_{field}"
        if isinstance(rec[field], bool) or not isinstance(rec[field], typ):
            return None, f"bad_type_{field}"
    try:
        datetime.fromisoformat(rec["timestamp"])
    except ValueError:
        return None, "bad_timestamp"
    if rec["duration_ms"] < 0:
        return None, "negative_duration"
    return rec, None


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text())
    con.executemany("INSERT OR IGNORE INTO slo_target VALUES (?, ?, ?, ?)", SLO_TARGETS)
    return con


def key(con, table, key_col, where, values, insert_cols, insert_vals):
    row = con.execute(f"SELECT {key_col} FROM {table} WHERE {where}", values).fetchone()
    if row:
        return row[0]
    cur = con.execute(f"INSERT INTO {table} ({insert_cols}) VALUES ({','.join('?' * len(insert_vals))})",
                      insert_vals)
    return cur.lastrowid


def ingest(source, db_path):
    started = now()
    con = connect(db_path)
    stats = {"lines_read": 0, "rows_inserted": 0, "duplicates": 0, "quarantined": 0}
    with con:
        for i, line in enumerate(Path(source).read_text().splitlines(), start=1):
            if not line.strip():
                continue
            stats["lines_read"] += 1
            rec, reason = validate(line)
            if reason:
                con.execute("INSERT OR IGNORE INTO quarantine VALUES (?, ?, ?, ?, ?)",
                            (Path(source).name, i, line[:2000], reason, now()))
                stats["quarantined"] += 1
                continue
            ts = datetime.fromisoformat(rec["timestamp"]).astimezone(timezone.utc)
            date_key = int(ts.strftime("%Y%m%d"))
            con.execute("INSERT OR IGNORE INTO dim_date VALUES (?, ?, ?)",
                        (date_key, ts.date().isoformat(), int(ts.strftime("%w"))))
            svc = key(con, "dim_service", "service_key", "service_name = ?", (rec["service"],),
                      "service_name", (rec["service"],))
            ep = key(con, "dim_endpoint", "endpoint_key", "service_key = ? AND endpoint_path = ?",
                     (svc, rec["endpoint"]), "service_key, endpoint_path", (svc, rec["endpoint"]))
            cur = con.execute(
                "INSERT OR IGNORE INTO fact_request VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rec["event_id"], date_key, ts.hour, ep, rec["status_code"],
                 1 if rec["status_code"] < 500 else 0, float(rec["duration_ms"]), rec.get("trace_id"), now()))
            if cur.rowcount == 1:
                stats["rows_inserted"] += 1
            else:
                stats["duplicates"] += 1
        con.execute("INSERT INTO load_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), str(source), stats["lines_read"], stats["rows_inserted"],
                     stats["duplicates"], stats["quarantined"], started, now()))
    con.close()
    return stats


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "sample_logs.jsonl")
    db = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "warehouse.db")
    s = ingest(src, db)
    print(f"read {s['lines_read']:,} lines: inserted {s['rows_inserted']:,}, "
          f"duplicates skipped {s['duplicates']:,}, quarantined {s['quarantined']:,}")
