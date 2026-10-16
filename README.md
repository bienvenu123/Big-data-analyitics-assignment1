# Smart Energy Grid Analytics — Assignment I

This workspace contains a reproducible implementation foundation for the October 2026 assignment. The supplied generator is copied unchanged as `smart_meter_simulator.py`. The assignment itself calls for machine-specific evidence (running services, timings, query plans and dashboard screenshots); those measurements must be collected on the machine that hosts your PostgreSQL/TimescaleDB and Grafana/Dash setup.

## Setup

Use a Python environment and install `requirements.txt`. Install/start EMQX and PostgreSQL with TimescaleDB 2.10+ on your machine, create an assignment database, and set a password-free connection string in the environment:

```powershell
$env:DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:5432/assignment'
$env:MQTT_HOST = 'localhost'
$env:MQTT_PORT = '1883'
```

Keep actual credentials out of this repository. Run `psql $env:DATABASE_URL -f schema.sql`, then load metadata with `python pipeline.py meters`.

## Execution order

1. Create database structures: `psql $env:DATABASE_URL -f schema.sql`; `python pipeline.py meters`.
2. Pilot: in terminal 1 run `python subscriber.py --limit 2000 --truncate`; after it connects, run `python publisher.py --limit 2000` in terminal 2. Both use QoS 1; their output files record generated/acknowledged and received/stored counts. For a one-command replay, `python pipeline.py pilot` starts both clients in one process and checks all four counts.
3. Full historical capture: `python pipeline.py capture --table energy_readings`. This inserts in bounded batches, commits progressively, logs progress, and checks the count against `dataset_info()`.
4. Run diagnostics and benchmark queries in `sql/quality_and_workloads.sql`. Review duplicate conflicts and then clean using `sql/clean.sql`. Do not fill gaps with zero. Populate comparison tables and run `ANALYZE` as instructed in the SQL notes.
5. Create the two additional continuous aggregate definitions with `sql/aggregates.sql` (the 15-minute view is in `schema.sql`), then run `python refresh_aggregates.py` after raw data is loaded. The program records full refresh time/size before installing refresh policies. Use `sql/reset_aggregates.sql` only when intentionally repeating the initially-empty-view experiment.
6. Run `python benchmark.py --tables energy_readings energy_readings_3h energy_readings_week` for the warm-up plus five-run comparison, then `python explain_plans.py --tables energy_readings energy_readings_3h energy_readings_week`. These save every run, summary and actual Q5 plans under `results/`.
7. Run `python compression_experiment.py` to build the two paused-policy one-day compressed tables, copy one source chunk at a time and record per-chunk compression times. Run `python benchmark.py --tables energy_readings energy_time_compressed energy_meter_compressed` for Section 4.3.
8. Run `python analyze_anomalies.py` and `python analyze_forecast.py` after the cleaned dataset exists. They write flags, validation scores, test predictions, peak-hour errors, plot and metrics under `results/`.
9. Run `python analyze_utility.py` for the daily/weekly, demand-peak, group energy, completeness, arrival-latency analyses and charts.
10. Run `python freshness_test.py` for the 6.2 old-hour/new-hour delayed-arrival comparison. It records the actual CAT times and stage snapshots under `results/`.
11. Start `python dashboard.py` for the Raw and Aggregate Dash tabs. Each exposes the five required panels, full-day date filters and selected meter; Raw queries the base table and Aggregate queries the three continuous aggregates. Queries run on each refresh without result caching.
12. Run `python dashboard_compare.py` for the assignment’s 22–29 September, all-region, meter-1000000000 numerical comparison.
13. Capture evidence, time ten dashboard refreshes per mode, and finish the report. Record CAT execution times, settings and outputs; do not invent results.

The historical stream has 10,696,848 emitted dictionaries. It can require substantial time and disk; check free space before capture. Re-running `capture` truncates its selected destination first. The generator yields in event-time order and all full-stream records are inserted, including deliberate copies.

## Files

- `pipeline.py`: idempotent meter metadata load, bounded direct PostgreSQL historical load, and MQTT pilot.
- `publisher.py` and `subscriber.py`: the standalone MQTT clients used for the separate-process pilot.
- `schema.sql`: base tables, hypertable and indexes.
- `sql/quality_and_workloads.sql`: quality counts, requested Q1–Q5, and utility-data queries.
- `docs/data_dictionary.md`: table/column types, definitions and units.
- `docs/environment_details.md`: recorded host, Docker, database and session settings (physical disk media type still requires manual verification).
- `docs/management_recommendation.md`: measured management recommendation draft (under 500 words).
- `docs/measured_findings.md`: observed assignment results and outstanding report/evidence limitations.
- `docs/assignment_report_draft.md`: subsection-ordered report draft populated from saved measurements, with real-evidence placeholders.
- `sql/clean.sql`: conflict-aware deterministic duplicate removal.
- `sql/aggregates.sql`: three materialized-only aggregate definitions and historical refreshes.
- `analyze_forecast.py`: leakage-aware previous-day baseline and two trained regression configurations with chronological validation/test outputs.
- `analyze_anomalies.py`: meter/hour/weekday median rule and event-label evaluation outputs.
- `analyze_utility.py`: daily/weekly network consumption, demand peaks, group comparisons, completeness and reporting-delay outputs with charts.
- `benchmark.py`: sequential warm-cache query timing and correctness comparison for each requested hypertable configuration.
- `compression_experiment.py`: chunk-by-chunk loading, compression timing, and paused 48-hour policies for both compression layouts.
- `explain_plans.py`: actual Q5 plans with buffer statistics for each requested table.
- `refresh_aggregates.py`: initial full-range refresh timings/sizes followed by 6.1 policy creation.
- `freshness_test.py`: isolated two-day delayed-arrival and continuous-aggregate freshness stages.
- `dashboard.py`: interactive five-panel Raw and Aggregate dashboards with date and meter filters.
- `dashboard_compare.py`: matching-key, count and value validation for the two dashboard modes.
- `smart_meter_simulator.py`: unchanged supplied generator.

## Evidence and report

Follow the PDF subsection order and embed screenshots with the executed command/action, result, taskbar and CAT clock. Record the host identifier and actual execution times. Keep final ZIP/repository copies consistent and include report, code, SQL, query timings, environment details, dashboard queries/configuration and contribution details. This project intentionally does not include fabricated measurements or screenshots.
