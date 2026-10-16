"""
SLO report: runs the named queries in sql/sli_queries.sql against the warehouse and writes
  - reports/slo_report.md         plain-English summary for stakeholders
  - exports/*.csv                 tidy tables ready for Power BI or Tableau
  - reports/slo_dashboard.png     availability and p95 latency by day (if matplotlib is installed)

Run: python -m pipeline.report warehouse.db
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "sql" / "sli_queries.sql"


def load_queries():
    text = QUERIES.read_text()
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def run(con, sql):
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()


def write_csv(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)


def build(db_path, out_root=ROOT):
    con = sqlite3.connect(db_path)
    q = load_queries()
    results = {name: run(con, sql) for name, sql in q.items()}
    audit = con.execute("SELECT lines_read, rows_inserted, duplicates, quarantined FROM load_audit "
                        "ORDER BY finished_at DESC LIMIT 1").fetchone()
    totals = con.execute("SELECT (SELECT COUNT(*) FROM fact_request), (SELECT COUNT(*) FROM load_audit), "
                         "(SELECT COUNT(DISTINCT line_number) FROM quarantine)").fetchone()
    reasons = con.execute("SELECT reason, COUNT(*) FROM quarantine GROUP BY reason ORDER BY 2 DESC").fetchall()
    targets = {r[0]: r[1:] for r in con.execute("SELECT * FROM slo_target")}
    con.close()

    for name, (cols, rows) in results.items():
        write_csv(Path(out_root) / "exports" / f"{name}.csv", cols, rows)

    eb_cols, eb_rows = results["error_budget"]
    burn_cols, burn_rows = results["hourly_burn"]
    p95_cols, p95_rows = results["daily_p95"]
    lines = ["# SLO Report", "",
             f"**Warehouse:** {totals[0]:,} unique events from {totals[1]} load run(s); "
             f"{totals[2]:,} malformed source lines quarantined.", "",
             f"**Latest load run:** {audit[0]:,} lines read, {audit[1]:,} new events inserted, "
             f"{audit[2]:,} duplicates skipped, {audit[3]:,} lines quarantined.", ""]
    if reasons:
        lines.append("Quarantine reasons: " + ", ".join(f"{r} ({n})" for r, n in reasons) + ".")
        lines.append("")
    lines += ["## Error budget (14 days)", "",
              "| Service | Availability SLO | Availability | Bad requests | Budget | Budget used | Status |",
              "|---|---|---|---|---|---|---|"]
    for svc, slo, req, bad, budget, used, avail in eb_rows:
        status = "Exhausted" if used >= 1 else ("At risk" if used >= 0.75 else "Healthy")
        lines.append(f"| {svc} | {slo:.1%} | {avail:.3%} | {bad:,} | {budget:,.0f} | {used:.0%} | {status} |")
    lines += ["", "## Latency (p95 vs threshold)", "", "| Service | Threshold | Worst day | Worst p95 |", "|---|---|---|---|"]
    by_svc = {}
    for svc, day, p95 in p95_rows:
        if svc not in by_svc or p95 > by_svc[svc][1]:
            by_svc[svc] = (day, p95)
    for svc, (day, p95) in sorted(by_svc.items()):
        thr = targets[svc][1]
        flag = " (breach)" if p95 > thr else ""
        lines.append(f"| {svc} | {thr:.0f} ms | {day} | {p95:.0f} ms{flag} |")
    lines += ["", "## Burn-rate alerts (hourly; page at 14.4x, ticket at 6x, minimum 3 bad requests)", ""]
    if burn_rows:
        lines += ["| Service | Date | Hour (UTC) | Requests | Bad | Burn rate | Severity |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {s} | {d} | {h:02d}:00 | {n} | {bad} | {b}x | {sev} |" for s, d, h, n, bad, b, sev in burn_rows]
    else:
        lines.append("None.")
    report = Path(out_root) / "reports" / "slo_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n")

    try:
        _chart(results, targets, Path(out_root) / "reports" / "slo_dashboard.png")
    except ImportError:
        pass
    return results


def _chart(results, targets, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    colors = {"analyzer": "#2a78d6", "checkout": "#eb6834", "webhooks": "#1baf7a"}
    ink, muted, surf = "#0b0b0b", "#52514e", "#fcfcfb"
    _, sli = results["daily_sli"]; _, p95 = results["daily_p95"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 8), facecolor=surf)
    for ax in (a1, a2):
        ax.set_facecolor(surf)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color("#cccccc"); ax.spines["bottom"].set_color("#cccccc")
        ax.tick_params(colors=muted); ax.grid(axis="y", color="#e6e6e3"); ax.set_axisbelow(True)
    days = sorted({r[1] for r in sli}); idx = list(range(1, len(days) + 1))
    for svc in sorted({r[0] for r in sli}):
        av = {r[1]: r[4] for r in sli if r[0] == svc}
        pv = {r[1]: r[2] for r in p95 if r[0] == svc}
        xs = [i for i, d in zip(idx, days) if d in av]           # skip days with no data for this service
        color = colors.get(svc, muted)
        a1.plot(xs, [av[days[i - 1]] for i in xs], color=color, linewidth=2, marker="o", markersize=4, label=svc)
        a2.plot(xs, [pv[days[i - 1]] for i in xs], color=color, linewidth=2, marker="o", markersize=4, label=svc)
    a1.axhline(0.995, color=muted, linestyle="--", linewidth=1)
    a1.text(len(days) + 0.25, 0.995, "99.5% SLO", color=muted, va="bottom", fontsize=9)
    a1.yaxis.set_major_formatter(PercentFormatter(1, decimals=2))
    a1.set_title("Daily availability by service", loc="left", color=ink, fontsize=12, fontweight="bold")
    a2.axhline(800, color=muted, linestyle="--", linewidth=1)
    a2.text(len(days) + 0.25, 800, "800 ms SLO", color=muted, va="bottom", fontsize=9)
    a2.set_title("Daily p95 latency by service (ms)", loc="left", color=ink, fontsize=12, fontweight="bold")
    for ax in (a1, a2):
        ax.set_xticks(idx); ax.set_xticklabels([d[5:] for d in days], fontsize=8, color=muted)
        ax.set_xlim(0.5, len(days) + 1.6)
    a1.legend(frameon=False, loc="lower left", labelcolor=ink, fontsize=9, ncol=3)
    a2.legend(frameon=False, loc="upper left", labelcolor=ink, fontsize=9, ncol=3)
    fig.text(0.01, 0.005, "Synthetic demo data.", color=muted, fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 1)); fig.savefig(path, dpi=150, facecolor=surf)


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "warehouse.db")
    build(db)
    print("wrote reports/slo_report.md, reports/slo_dashboard.png and exports/*.csv")
