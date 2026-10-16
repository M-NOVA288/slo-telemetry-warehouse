# SLO Report

**Warehouse:** 58,372 unique events from 2 load run(s); 276 malformed source lines quarantined.

**Latest load run:** 59,797 lines read, 0 new events inserted, 59,521 duplicates skipped, 276 lines quarantined.

Quarantine reasons: bad_type_duration_ms (118), missing_status_code (104), unparseable_json (54).

## Error budget (14 days)

| Service | Availability SLO | Availability | Bad requests | Budget | Budget used | Status |
|---|---|---|---|---|---|---|
| analyzer | 99.9% | 99.954% | 12 | 26 | 46% | Healthy |
| checkout | 99.5% | 99.706% | 57 | 97 | 59% | Healthy |
| webhooks | 99.9% | 99.938% | 8 | 13 | 62% | Healthy |

## Latency (p95 vs threshold)

| Service | Threshold | Worst day | Worst p95 |
|---|---|---|---|
| analyzer | 800 ms | 2026-09-12 | 1787 ms (breach) |
| checkout | 800 ms | 2026-09-08 | 398 ms |
| webhooks | 500 ms | 2026-09-12 | 201 ms |

## Burn-rate alerts (hourly; page at 14.4x, ticket at 6x, minimum 3 bad requests)

| Service | Date | Hour (UTC) | Requests | Bad | Burn rate | Severity |
|---|---|---|---|---|---|---|
| checkout | 2026-09-09 | 16:00 | 73 | 8 | 21.92x | page |
| checkout | 2026-09-09 | 15:00 | 86 | 8 | 18.6x | page |
| checkout | 2026-09-09 | 17:00 | 83 | 6 | 14.46x | page |
