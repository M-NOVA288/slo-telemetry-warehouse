# Product Brief: SLO Telemetry Warehouse

## Problem
Engineering and business teams argue about reliability using anecdotes. Logs exist, but nobody can answer three questions quickly and with one shared number:

1. Are we meeting our reliability targets this period?
2. How much error budget is left before we must pause feature work?
3. Which incidents actually mattered to customers?

## Users
| Persona | Need | What they use |
|---|---|---|
| Engineering lead | Decide whether to ship features or fix reliability | Error-budget table, burn-rate alerts |
| On-call engineer | Get paged only for real, customer-impacting problems | Burn-rate alerts with severity |
| Product owner | Prioritize NFRs and tech debt against features with data | SLO report, backlog links |
| Business stakeholder / analyst | Track service health in their own BI tool | CSV exports for Power BI or Tableau |

## Outcomes and KPIs
| Outcome | KPI | Target |
|---|---|---|
| One trusted reliability number | Services with an agreed SLO and daily SLI | 100% of in-scope services |
| Data you can trust | Malformed lines quarantined (not dropped silently); duplicates removed | 0 duplicates in the fact table |
| Fewer false pages | Pages per incident | 1 incident = 1 alert window, no single-error pages |
| Faster decisions | Time to produce the weekly SLO report | Under 1 minute, fully automated |

## Scope
**In:** structured JSON logs from three services; validation, quarantine and idempotent loading; star schema; SLIs, error budget, burn-rate alerts; Markdown report, chart and BI exports; Snowflake DDL and MERGE load.

**Out (this release):** real-time streaming, multiwindow (5-minute) burn rates, alert delivery to a pager, live Snowflake deployment.

## SLOs in scope
| Service | Availability SLO | Latency SLO |
|---|---|---|
| checkout | 99.5% of requests succeed | 95% under 800 ms |
| analyzer | 99.9% | 95% under 800 ms |
| webhooks | 99.9% | 95% under 500 ms |
