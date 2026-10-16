FROM python:3.12-slim
WORKDIR /app
COPY . .
# Standard library only; matplotlib is optional (chart is skipped if absent)
CMD ["sh", "-c", "python data/generate_logs.py && python -m pipeline.ingest && python -m pipeline.report && cat reports/slo_report.md"]
