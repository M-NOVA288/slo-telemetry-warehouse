-- name: daily_sli
-- Availability and latency SLIs per service per day.
SELECT
    s.service_name,
    d.calendar_date,
    COUNT(*)                                             AS requests,
    SUM(f.is_good)                                       AS good_requests,
    ROUND(1.0 * SUM(f.is_good) / COUNT(*), 5)            AS availability,
    ROUND(1.0 * SUM(CASE WHEN f.duration_ms <= t.latency_slo_ms THEN 1 ELSE 0 END) / COUNT(*), 5)
                                                         AS latency_within_slo
FROM fact_request f
JOIN dim_endpoint e ON e.endpoint_key = f.endpoint_key
JOIN dim_service  s ON s.service_key  = e.service_key
JOIN dim_date     d ON d.date_key     = f.date_key
JOIN slo_target   t ON t.service_name = s.service_name
GROUP BY s.service_name, d.calendar_date
ORDER BY s.service_name, d.calendar_date;

-- name: daily_p95
-- p95 latency per service per day using window functions.
WITH ranked AS (
    SELECT
        s.service_name,
        d.calendar_date,
        f.duration_ms,
        ROW_NUMBER() OVER (PARTITION BY s.service_name, d.calendar_date ORDER BY f.duration_ms) AS rn,
        COUNT(*)     OVER (PARTITION BY s.service_name, d.calendar_date)                       AS n
    FROM fact_request f
    JOIN dim_endpoint e ON e.endpoint_key = f.endpoint_key
    JOIN dim_service  s ON s.service_key  = e.service_key
    JOIN dim_date     d ON d.date_key     = f.date_key
)
SELECT service_name, calendar_date, MIN(duration_ms) AS p95_ms
FROM ranked
WHERE rn >= 0.95 * n
GROUP BY service_name, calendar_date
ORDER BY service_name, calendar_date;

-- name: error_budget
-- Error budget for the whole window: allowed bad requests vs actual, per service.
SELECT
    s.service_name,
    t.availability_slo,
    COUNT(*)                                                        AS requests,
    COUNT(*) - SUM(f.is_good)                                       AS bad_requests,
    ROUND(COUNT(*) * (1 - t.availability_slo), 1)                   AS budget_requests,
    ROUND((COUNT(*) - SUM(f.is_good)) / (COUNT(*) * (1 - t.availability_slo)), 4)
                                                                    AS budget_consumed,
    ROUND(1.0 * SUM(f.is_good) / COUNT(*), 5)                       AS availability
FROM fact_request f
JOIN dim_endpoint e ON e.endpoint_key = f.endpoint_key
JOIN dim_service  s ON s.service_key  = e.service_key
JOIN slo_target   t ON t.service_name = s.service_name
GROUP BY s.service_name, t.availability_slo
ORDER BY s.service_name;

-- name: hourly_burn
-- Hourly burn rate = bad share / allowed bad share.
-- Severity: page at >= 14.4x (2% of a 30-day budget in one hour), ticket at >= 6x.
-- Guard: at least 3 bad requests in the hour, so one stray error in a quiet hour cannot page anyone.
SELECT
    s.service_name,
    d.calendar_date,
    f.event_hour,
    COUNT(*)                     AS requests,
    COUNT(*) - SUM(f.is_good)    AS bad_requests,
    ROUND((1.0 * (COUNT(*) - SUM(f.is_good)) / COUNT(*)) / (1 - t.availability_slo), 2) AS burn_rate,
    CASE WHEN (1.0 * (COUNT(*) - SUM(f.is_good)) / COUNT(*)) / (1 - t.availability_slo) >= 14.4
         THEN 'page' ELSE 'ticket' END AS severity
FROM fact_request f
JOIN dim_endpoint e ON e.endpoint_key = f.endpoint_key
JOIN dim_service  s ON s.service_key  = e.service_key
JOIN dim_date     d ON d.date_key     = f.date_key
JOIN slo_target   t ON t.service_name = s.service_name
GROUP BY s.service_name, d.calendar_date, f.event_hour
HAVING bad_requests >= 3 AND burn_rate >= 6
ORDER BY burn_rate DESC;
