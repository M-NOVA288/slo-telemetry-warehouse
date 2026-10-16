"""
Generate synthetic structured JSON logs (OpenTelemetry-style fields) for three services over 14 days.

Built-in realism for the pipeline to handle:
  - an availability incident on checkout (day 9, 3 hours of elevated 5xx)
  - a latency regression on analyzer (days 11-12)
  - ~2% duplicate deliveries (same event_id, as from retried log shipping)
  - ~0.5% malformed records (missing fields, bad types, unparseable lines)

Deterministic (seeded). Output: data/sample_logs.jsonl
Run: python data/generate_logs.py
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 7
DAYS = 14
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
OUT = Path(__file__).with_name("sample_logs.jsonl")

SERVICES = {
    # service: (endpoints, requests per hour, base latency ms, base error rate)
    "checkout": (["/api/checkout", "/api/checkout/confirm"], 60, 180, 0.002),
    "analyzer": (["/api/analyze", "/api/analyze/report"], 80, 320, 0.0005),
    "webhooks": (["/api/webhooks/stripe"], 40, 90, 0.0004),
}


def main():
    rng = random.Random(SEED)
    lines = []
    n = 0
    for day in range(DAYS):
        for hour in range(24):
            ts_hour = START + timedelta(days=day, hours=hour)
            for svc, (endpoints, per_hour, base_lat, base_err) in SERVICES.items():
                load = per_hour * (1.4 if 14 <= hour <= 20 else 0.8)
                for _ in range(int(rng.gauss(load, load * 0.1))):
                    n += 1
                    err = base_err
                    lat = rng.lognormvariate(0, 0.45) * base_lat
                    if svc == "checkout" and day == 8 and 15 <= hour < 18:
                        err = 0.08                      # incident window
                    if svc == "analyzer" and day in (10, 11):
                        lat *= 2.6                      # latency regression
                    status = rng.choice([500, 502, 503]) if rng.random() < err else 200
                    rec = {
                        "event_id": f"evt-{n:07d}",
                        "timestamp": (ts_hour + timedelta(seconds=rng.uniform(0, 3599))).isoformat(),
                        "service": svc,
                        "endpoint": rng.choice(endpoints),
                        "status_code": status,
                        "duration_ms": round(lat, 1),
                        "trace_id": f"{rng.getrandbits(64):016x}",
                        "level": "error" if status >= 500 else "info",
                    }
                    lines.append(json.dumps(rec))
                    if rng.random() < 0.02:             # duplicate delivery
                        lines.append(json.dumps(rec))
                    r = rng.random()
                    if r < 0.002:                        # missing required field
                        bad = dict(rec); bad.pop("status_code"); lines.append(json.dumps(bad))
                    elif r < 0.004:                      # bad type
                        bad = dict(rec); bad["duration_ms"] = "slow"; bad["event_id"] += "-x"
                        lines.append(json.dumps(bad))
                    elif r < 0.005:                      # unparseable line
                        lines.append('{"event_id": "broken"')
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines):,} lines ({n:,} unique events) to {OUT}")


if __name__ == "__main__":
    main()
