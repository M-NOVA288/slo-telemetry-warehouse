# Product Backlog

Prioritized with WSJF (Weighted Shortest Job First): **(business value + time criticality + risk reduction) ÷ job size**, each scored 1–10. Higher goes first. Every item is typed so features, NFRs, technical debt and spikes compete on the same scale.

| ID | Type | Item | Value | Time | Risk | Size | WSJF | Status |
|---|---|---|---|---|---|---|---|---|
| PB-01 | Feature | Load structured logs into a star schema | 9 | 8 | 6 | 3 | 7.7 | Done |
| PB-02 | NFR | Idempotent loads: reruns never duplicate events | 7 | 7 | 9 | 2 | 11.5 | Done |
| PB-03 | NFR | Quarantine malformed lines with a reason, never drop silently | 6 | 6 | 9 | 2 | 10.5 | Done |
| PB-04 | Feature | Daily availability and latency SLIs per service | 9 | 7 | 5 | 2 | 10.5 | Done |
| PB-05 | Feature | Error-budget report per service | 9 | 8 | 7 | 2 | 12.0 | Done |
| PB-06 | Feature | Hourly burn-rate alerts with page / ticket severity | 8 | 7 | 8 | 3 | 7.7 | Done |
| PB-07 | Tech debt | Minimum-volume guard on alerts (single errors paged on-call in quiet hours) | 6 | 8 | 7 | 1 | 21.0 | Done |
| PB-08 | Feature | CSV exports for Power BI and Tableau | 7 | 5 | 3 | 1 | 15.0 | Done |
| PB-09 | NFR | Load audit trail: lines read, inserted, duplicates, quarantined per run | 5 | 4 | 8 | 1 | 17.0 | Done |
| PB-10 | Feature | Snowflake DDL and MERGE-based load | 7 | 4 | 5 | 3 | 5.3 | Done (not deployed) |
| PB-11 | NFR | CI: tests run on every push; container build | 5 | 5 | 8 | 2 | 9.0 | Done |
| PB-12 | Spike | Multiwindow burn rate (5-minute + 1-hour) to cut detection time | 7 | 5 | 6 | 3 | 6.0 | Next |
| PB-13 | Feature | Send page-severity alerts to a pager webhook | 8 | 5 | 5 | 3 | 6.0 | Next |
| PB-14 | Spike | Streaming ingest (Snowpipe) vs hourly batch: cost and latency | 6 | 3 | 5 | 3 | 4.7 | Later |
| PB-15 | Tech debt | Move SLO targets from code into a reviewed config file | 4 | 3 | 5 | 1 | 12.0 | Next |

## Decisions log
- **PB-07 came from the first real run.** Without a guard, hourly burn rate above 14.4× flagged 17 hours, mostly one or two stray errors in a quiet hour on the 99.9% services. Requiring at least 3 bad requests and splitting page (≥14.4×) from ticket (≥6×) left exactly the 3 hours of the real checkout incident.
- **PB-02 uses the event's natural key** (`event_id`) rather than a hash of the line, so a re-shipped log line with different whitespace is still recognized as a duplicate.
