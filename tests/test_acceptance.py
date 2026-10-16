"""Acceptance tests. Each test name carries the AC id from docs/user_stories.md."""
import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.ingest import ingest
from pipeline.report import build, load_queries

T0 = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def event(i, service="checkout", status=200, ms=100.0, minutes=0, endpoint="/api/checkout"):
    return {"event_id": f"t-{i}", "timestamp": (T0 + timedelta(minutes=minutes)).isoformat(),
            "service": service, "endpoint": endpoint, "status_code": status, "duration_ms": ms}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = str(self.tmp / "w.db")

    def write(self, lines, name="logs.jsonl"):
        p = self.tmp / name
        p.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines) + "\n")
        return p

    def q(self, sql):
        con = sqlite3.connect(self.db)
        rows = con.execute(sql).fetchall()
        con.close()
        return rows

    def named(self, name):
        con = sqlite3.connect(self.db)
        rows = con.execute(load_queries()[name]).fetchall()
        con.close()
        return rows


class TrustworthyData(Fixture):
    def test_AC_1_1_duplicates_load_once(self):
        e = event(1)
        ingest(self.write([e, e, e, event(2)]), self.db)
        self.assertEqual(self.q("SELECT COUNT(*) FROM fact_request")[0][0], 2)

    def test_AC_1_2_reload_inserts_nothing(self):
        src = self.write([event(i) for i in range(50)])
        first = ingest(src, self.db)
        second = ingest(src, self.db)
        self.assertEqual(first["rows_inserted"], 50)
        self.assertEqual(second["rows_inserted"], 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM fact_request")[0][0], 50)

    def test_AC_1_3_bad_lines_quarantined_with_reason(self):
        missing = event(2); missing.pop("status_code")
        badtype = event(3); badtype["duration_ms"] = "slow"
        ingest(self.write([event(1), '{"broken"', missing, badtype]), self.db)
        reasons = sorted(r[0] for r in self.q("SELECT reason FROM quarantine"))
        self.assertEqual(reasons, ["bad_type_duration_ms", "missing_status_code", "unparseable_json"])
        self.assertEqual(self.q("SELECT event_id FROM fact_request"), [("t-1",)])

    def test_AC_1_4_audit_reconciles(self):
        e = event(1)
        ingest(self.write([e, e, event(2), "not json"]), self.db)
        read, ins, dup, qua = self.q("SELECT lines_read, rows_inserted, duplicates, quarantined FROM load_audit")[0]
        self.assertEqual((read, ins, dup, qua), (4, 2, 1, 1))
        self.assertEqual(read, ins + dup + qua)


class ReliabilityAtAGlance(Fixture):
    def test_AC_2_1_availability_is_good_over_total(self):
        lines = [event(i) for i in range(98)] + [event(98, status=503), event(99, status=500)]
        ingest(self.write(lines), self.db)
        row = [r for r in self.named("daily_sli") if r[0] == "checkout"][0]
        self.assertEqual((row[2], row[3]), (100, 98))
        self.assertAlmostEqual(row[4], 0.98)

    def test_AC_2_2_budget_over_100_percent_when_exceeded(self):
        # checkout SLO 99.5% -> budget on 1,000 requests is 5; 12 failures exceed it.
        lines = [event(i, status=503 if i < 12 else 200) for i in range(1000)]
        ingest(self.write(lines), self.db)
        row = [r for r in self.named("error_budget") if r[0] == "checkout"][0]
        self.assertGreater(row[5], 1.0)

    def test_AC_2_3_latency_regression_breaches_p95(self):
        lines = [event(i, service="analyzer", endpoint="/api/analyze", ms=1500.0 if i % 10 < 2 else 200.0)
                 for i in range(200)]
        ingest(self.write(lines), self.db)
        p95 = [r for r in self.named("daily_p95") if r[0] == "analyzer"][0][2]
        self.assertGreater(p95, 800)


class PagesOnlyForRealIncidents(Fixture):
    def test_AC_3_1_sustained_spike_pages(self):
        lines = [event(i, status=503 if i < 8 else 200, minutes=i % 60) for i in range(80)]
        ingest(self.write(lines), self.db)
        alerts = self.named("hourly_burn")
        self.assertTrue(any(a[0] == "checkout" and a[6] == "page" for a in alerts))

    def test_AC_3_2_single_error_does_not_alert(self):
        lines = [event(i, service="webhooks", endpoint="/api/webhooks/stripe",
                       status=503 if i == 0 else 200, minutes=i) for i in range(30)]
        ingest(self.write(lines), self.db)
        self.assertEqual(self.named("hourly_burn"), [])


class BIExports(Fixture):
    def test_AC_4_1_csv_per_query(self):
        lines = [event(i, status=503 if i < 8 else 200, minutes=i % 60) for i in range(80)]
        ingest(self.write(lines), self.db)
        build(self.db, out_root=self.tmp)
        for name in load_queries():
            with (self.tmp / "exports" / f"{name}.csv").open() as f:
                rows = list(csv.reader(f))
            self.assertGreaterEqual(len(rows), 2, name)


if __name__ == "__main__":
    unittest.main()
