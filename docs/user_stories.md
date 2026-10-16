# User Stories and Acceptance Criteria

Each acceptance criterion (AC) has an automated test with the same ID in `tests/test_acceptance.py`.

## US-1 Trustworthy data (PB-01, PB-02, PB-03, PB-09)
**As an** analyst, **I want** every valid event loaded exactly once and every bad line explained, **so that** the reliability numbers can be trusted.

- **AC-1.1** *Given* a log file with duplicate deliveries of the same `event_id`, *when* it is loaded, *then* the fact table holds one row per unique `event_id`.
- **AC-1.2** *Given* a file that was already loaded, *when* it is loaded again, *then* 0 new rows are inserted and the fact table row count is unchanged.
- **AC-1.3** *Given* lines with invalid JSON, a missing required field, or a wrong data type, *when* they are loaded, *then* each goes to `quarantine` with a reason and no such line reaches the fact table.
- **AC-1.4** *Given* any load run, *when* it finishes, *then* one `load_audit` row records lines read = inserted + duplicates + quarantined.

## US-2 Reliability at a glance (PB-04, PB-05)
**As an** engineering lead, **I want** availability, latency and error budget per service, **so that** I can decide whether to ship features or fix reliability.

- **AC-2.1** *Given* loaded events, *when* the daily SLI query runs, *then* availability equals good requests ÷ all requests for each service and day.
- **AC-2.2** *Given* a service whose bad requests exceed its allowed budget, *when* the error-budget query runs, *then* budget consumed is above 100%.
- **AC-2.3** *Given* a latency regression, *when* the p95 query runs, *then* the affected days show p95 above the latency threshold.

## US-3 Pages only for real incidents (PB-06, PB-07)
**As an** on-call engineer, **I want** to be paged only when customers are affected, **so that** alerts stay meaningful.

- **AC-3.1** *Given* an hour with a sustained error spike, *when* burn rates are computed, *then* that hour is flagged with severity `page`.
- **AC-3.2** *Given* an hour with a single error on a low-traffic service, *when* burn rates are computed, *then* no alert is raised.

## US-4 Use my own BI tool (PB-08)
**As a** business stakeholder, **I want** the SLO tables as CSV, **so that** I can build dashboards in Power BI or Tableau.

- **AC-4.1** *Given* a completed report run, *when* I open `exports/`, *then* each query has a CSV with a header row and at least one data row.
