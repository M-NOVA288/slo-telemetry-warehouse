# Data Dictionary

## Source: structured JSON log line (log contract)
| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| event_id | string | Yes | Unique id for one request event; natural key for de-duplication | `evt-0000123` |
| timestamp | ISO 8601 string | Yes | When the request completed, with UTC offset | `2026-09-09T15:12:44+00:00` |
| service | string | Yes | Service that handled the request | `checkout` |
| endpoint | string | Yes | Route path | `/api/checkout` |
| status_code | integer | Yes | HTTP status returned | `200`, `503` |
| duration_ms | number | Yes | Server-side duration in milliseconds, ≥ 0 | `182.4` |
| trace_id | string | No | OpenTelemetry trace id linking related spans | `9f2c...` |
| level | string | No | Log level | `info`, `error` |

Lines that fail the contract are written to `quarantine`, not dropped.

## Warehouse tables
### fact_request (grain: one row per unique event)
| Column | Type | Description |
|---|---|---|
| event_id | text, PK | From source; guarantees idempotent loads |
| date_key | integer, FK → dim_date | UTC date as YYYYMMDD |
| event_hour | integer | UTC hour 0–23, used for burn-rate windows |
| endpoint_key | integer, FK → dim_endpoint | Endpoint (and through it, service) |
| status_code | integer | HTTP status |
| is_good | integer | 1 if status_code < 500, else 0 (availability SLI definition) |
| duration_ms | real | Request duration |
| trace_id | text | Optional trace id |
| loaded_at | text | UTC time the row was loaded |

### dim_service
| Column | Type | Description |
|---|---|---|
| service_key | integer, PK | Surrogate key |
| service_name | text, unique | e.g. `checkout` |

### dim_endpoint
| Column | Type | Description |
|---|---|---|
| endpoint_key | integer, PK | Surrogate key |
| service_key | integer, FK → dim_service | Owning service |
| endpoint_path | text | Route path; unique per service |

### dim_date
| Column | Type | Description |
|---|---|---|
| date_key | integer, PK | YYYYMMDD |
| calendar_date | text | ISO date |
| day_of_week | integer | 0 = Sunday |

### slo_target
| Column | Type | Description |
|---|---|---|
| service_name | text, PK | Service |
| availability_slo | real | Target share of good requests, e.g. 0.995 |
| latency_slo_ms | real | Latency threshold |
| latency_slo_share | real | Share of requests that must be under the threshold |

### quarantine
| Column | Type | Description |
|---|---|---|
| source_file, line_number | text, integer (composite PK) | Where the bad line came from; PK makes reloads idempotent |
| raw_line | text | Original line (first 2,000 characters) |
| reason | text | e.g. `unparseable_json`, `missing_status_code`, `bad_type_duration_ms` |
| loaded_at | text | UTC time quarantined |

### load_audit
| Column | Type | Description |
|---|---|---|
| run_id | text, PK | UUID per load run |
| source_file | text | File loaded |
| lines_read, rows_inserted, duplicates, quarantined | integer | Reconciles: read = inserted + duplicates + quarantined |
| started_at, finished_at | text | UTC run window |

## Metric definitions
| Metric | Definition |
|---|---|
| Availability | good requests ÷ all requests |
| Latency within SLO | requests with duration ≤ threshold ÷ all requests |
| p95 latency | smallest duration at or above the 95th percentile rank |
| Error budget | all requests × (1 − availability SLO) |
| Budget consumed | bad requests ÷ error budget |
| Burn rate | (bad ÷ all in the hour) ÷ (1 − availability SLO); page ≥ 14.4×, ticket ≥ 6×, minimum 3 bad requests |
