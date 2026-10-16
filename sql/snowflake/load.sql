-- Snowflake load: stage JSON logs, then MERGE into the fact table so reloads never duplicate rows.
-- Not executed in CI; mirrors the logic in pipeline/ingest.py.

CREATE FILE FORMAT IF NOT EXISTS JSONL_FORMAT TYPE = JSON STRIP_OUTER_ARRAY = FALSE;
CREATE STAGE IF NOT EXISTS LOG_STAGE FILE_FORMAT = JSONL_FORMAT;

-- PUT file://data/sample_logs.jsonl @LOG_STAGE;   (run from SnowSQL)

COPY INTO RAW_LOGS (PAYLOAD, SOURCE_FILE)
FROM (SELECT $1, METADATA$FILENAME FROM @LOG_STAGE)
ON_ERROR = CONTINUE;                                  -- unparseable lines are skipped and reported

-- Valid, de-duplicated events (one row per EVENT_ID).
CREATE OR REPLACE TEMPORARY TABLE STG_EVENTS AS
SELECT
    PAYLOAD:event_id::STRING                     AS EVENT_ID,
    PAYLOAD:timestamp::TIMESTAMP_TZ              AS EVENT_TS,
    PAYLOAD:service::STRING                      AS SERVICE_NAME,
    PAYLOAD:endpoint::STRING                     AS ENDPOINT_PATH,
    TRY_TO_NUMBER(PAYLOAD:status_code::STRING)   AS STATUS_CODE,
    TRY_TO_DOUBLE(PAYLOAD:duration_ms::STRING)   AS DURATION_MS,
    PAYLOAD:trace_id::STRING                     AS TRACE_ID
FROM RAW_LOGS
WHERE STATUS_CODE IS NOT NULL AND DURATION_MS IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY EVENT_ID ORDER BY LOADED_AT) = 1;

MERGE INTO FACT_REQUEST f
USING (
    SELECT s.EVENT_ID,
           TO_NUMBER(TO_CHAR(s.EVENT_TS, 'YYYYMMDD')) AS DATE_KEY,
           HOUR(s.EVENT_TS)                            AS EVENT_HOUR,
           e.ENDPOINT_KEY,
           s.STATUS_CODE,
           s.STATUS_CODE < 500                         AS IS_GOOD,
           s.DURATION_MS,
           s.TRACE_ID
    FROM STG_EVENTS s
    JOIN DIM_SERVICE  d ON d.SERVICE_NAME = s.SERVICE_NAME
    JOIN DIM_ENDPOINT e ON e.SERVICE_KEY = d.SERVICE_KEY AND e.ENDPOINT_PATH = s.ENDPOINT_PATH
) src
ON f.EVENT_ID = src.EVENT_ID
WHEN NOT MATCHED THEN INSERT
    (EVENT_ID, DATE_KEY, EVENT_HOUR, ENDPOINT_KEY, STATUS_CODE, IS_GOOD, DURATION_MS, TRACE_ID, LOADED_AT)
VALUES
    (src.EVENT_ID, src.DATE_KEY, src.EVENT_HOUR, src.ENDPOINT_KEY, src.STATUS_CODE, src.IS_GOOD,
     src.DURATION_MS, src.TRACE_ID, CURRENT_TIMESTAMP());
