# Assignment I: Smart Energy Grid Analytics

**Group:** [Add group name and member names]
**Student IDs and contributions:** [Add each member, ID, and contribution]
**Database:** PostgreSQL 17.11 with TimescaleDB 2.30.1 in Docker
**Analysis time zone:** CAT (Africa/Kigali, UTC+02:00)
**Status:** Draft prepared from the project’s saved measurements. Bracketed evidence notes and group details must be completed before submission. No screenshots or timings have been fabricated.

## 1. Build the ingestion pipeline

### 1.1 Environment

The host record identifies an HP ENVY x360 2-in-1, 12th Gen Intel Core i7-1250U (10 cores, 12 logical processors), 16,077 MB RAM, Windows 11 Pro build 26200, and Python 3.14.4. PostgreSQL 17.11 and TimescaleDB 2.30.1 ran in Docker Desktop; the TimescaleDB container had no explicit CPU or memory limit. Recorded PostgreSQL settings are shared_buffers 1,947 MB, work_mem 5,192 kB, max_parallel_workers_per_gather 6, and jit off. Docker reported 12 CPUs and about 8.17 GB memory. The database session uses Africa/Kigali. The physical storage medium remains to be confirmed. The Windows clock was reported unsynchronized during the recorded work; synchronize it and re-record CAT evidence before submission.

The assignment specifies EMQX. The saved environment record says the pilot used Mosquitto 2.1.2 instead. This is a requirement deviation; repeat the pilot on EMQX if available, otherwise state the deviation accurately.

**Evidence to insert:** running broker and version; connected assignment database; enabled TimescaleDB extension; session time zone; host/system details and clock.

### 1.2 Database structures

The schema defines energy_live, energy_readings, and meters. energy_readings is a one-day Timescale hypertable with time and meter/time indexes. The metadata loader reads the simulator’s 4,000 meter records. The data dictionary documents columns, types, meanings, and units in docs/data_dictionary.md.

**Evidence to insert:** table definitions and types, one-day chunk interval, and query result showing 4,000 meters.

### 1.3 Pilot stream

The earlier saved pilot run reports 2,000 generated, acknowledged, received, and stored at QoS 1 with retain disabled. A fresh retry on 15 Oct 2026 reached the broker, but the subscriber was rejected with Not authorized. The retry did not produce new MQTT counts; its 2,000 simulator rows were restored to energy_live from the deterministic generator. Configure broker credentials before presenting the earlier pilot counts as a fresh run.

**Evidence to insert:** publisher completion, subscriber completion, and stored row/sample query.

## 2. Capture and prepare the historical dataset

### 2.1 Full capture

The saved direct PostgreSQL batch capture consumed and stored 10,696,848 rows, matching the simulator’s emitted count. Recorded elapsed time was 117.47 seconds, with 117.257 seconds from first write through final count. The original capture did not record exact CAT start/end times. The cleaned dataset contains 10,643,735 rows. The pilot remains separate in energy_live.

**Evidence to insert:** capture progress and completion, expected-versus-consumed-versus-stored counts, date range, distinct meters, and table/index/total storage sizes. Repeat the capture timing only if exact CAT timestamps are required; do not truncate/reload solely to recreate screenshots unless there is a backup and a planned run.

### 2.2 Data quality

Before cleaning, the source contained 10,696,848 emitted rows, 10,643,735 unique meter/time pairs, 53,113 extra copies, 213,090 delayed unique readings, 108,265 missing planned pairs, and no conflicting duplicate groups. Missing rate was 1.006929%, duplicate rate 0.499007%, delayed rate 2.002023%, and completeness 98.993071%. The five highest missing-meter counts are saved in results/top_five_missing_meters.csv.

**Evidence to insert:** diagnostic query output and top-five missing meters.

### 2.3 Cleaning

The cleanup retained one row per meter/time pair after confirming duplicate payloads did not conflict. Rows fell from 10,696,848 to 10,643,735; summed energy changed from 3,872,863.893 kWh to 3,853,704.347 kWh because repeated copies were removed. Gaps were preserved rather than filled with zero, since a missing measurement is unknown consumption, not evidence of no consumption.

**Evidence to insert:** cleanup execution, before/after counts and energy totals, and zero-duplicate check.

## 3. Compare chunk intervals

### 3.1 Configurations and data checks

The project defines one-day energy_readings, three-hour energy_readings_3h, and one-week energy_readings_week hypertables, with matching event-time and meter/event-time indexes. The saved benchmark workflow includes correctness checks and Q5 plans for all three configurations.

**Evidence to insert:** chunk interval/count, index definitions, date range and matching row/meter/sum checks for all three tables.

### 3.2 Workload timings

The fresh run used psycopg 3 / Python on DESKTOP-CK0HHMD. Each query/table had a warm-up plus five measured runs; the session lasted 33.04 seconds. Times below are medians in milliseconds. Full min/max and timestamps are in results/chunk_interval_benchmark_summary.csv and results/chunk_interval_benchmark_runs.csv.

| Query | 1 day | 3 hours | 1 week | Fastest |
|---|---:|---:|---:|---|
| Q1 | 30.90 | 43.58 | 49.49 | 1 day |
| Q2 | 107.75 | 154.27 | 197.64 | 1 day |
| Q3 | 568.21 | 1,325.01 | 669.51 | 1 day |
| Q4 | 4.05 | 4.50 | 3.54 | 1 week |
| Q5 | 488.19 | 436.10 | 491.23 | 3 hours |

**Evidence to insert:** timing comparison and one actual timing/buffer plan per table. Report the saved session duration and label all results warm-cache.

### 3.3 Interpretation

One-day chunks were fastest for Q1-Q3, the one-week layout was fastest for the selective-meter Q4, and three-hour chunks were fastest for Q5. In this fresh session, three-hour and one-week chunks were slower on the two time-filtered queries Q1 and Q2; these measurements vary from the earlier saved run. Smaller chunks can reduce time-range scanning, while extra chunks add planning and aggregation work to broad queries. These are interpretations of this machine's measured results, not universal guarantees.

## 4. Compare compression strategies

### 4.1 Layout and loading

Two one-day compressed hypertables were built from the cleaned data: event-time order without segmentation, and event-time order segmented by meter_id. Saved logs show both layouts have the same 29 time ranges compressed and contain 10,643,735 rows. Policies were paused for the measurements.

**Evidence to insert:** compression settings, policy configuration and paused state, chunk ranges, and data equivalence checks.

### 4.2 Storage and compression cost

| Layout | Total size | Ratio vs. 1-day baseline | Saved | Compressed rows/chunks | Compression time |
|---|---:|---:|---:|---:|---:|
| Uncompressed baseline | 1,503.85 MB | 1.00x | — | — | — |
| Time-only | 460.28 MB | 3.27x | 69.39% | 100%; 29/29 | 12.84 s |
| Meter-segmented | 526.26 MB | 2.86x | 65.01% | 100%; 29/29 | 43.61 s |

The baseline and compressed data/index sizes are recorded in results/compression_storage_summary.csv.

**Evidence to insert:** storage statistics and chunk compression timing summary.

### 4.3 Query comparison

Medians in milliseconds, against the same one-day uncompressed baseline:

| Query | Baseline | Time-only | Meter-segmented |
|---|---:|---:|---:|
| Q1 | 29.95 | 28.82 | 240.33 |
| Q2 | 103.77 | 99.07 | 75.57 |
| Q3 | 415.05 | 237.18 | 173.79 |
| Q4 | 2.50 | 53.44 | 2.65 |
| Q5 | 303.73 | 235.47 | 247.05 |

In this fresh run, time-only compression improved Q1, Q2, Q3, and Q5 by 3.8%, 4.5%, 42.9%, and 22.5%; selected-meter Q4 rose from 2.50 ms to 53.44 ms. Meter segmentation improved Q2, Q3, and Q5 by 27.2%, 58.1%, and 18.7%; Q4 was 2.65 ms versus 2.50 ms on the baseline, while Q1 rose to 240.33 ms. Full timings and actual Q5 plans are saved under results/.

**Evidence to insert:** comparison results, plans for both compressed tables, and policy enabled status after measurements.

### 4.4 Recommendation

For historical reporting, choose one-day time-only compression: it achieved a 3.27x total-size reduction and faster medians for four of five workloads, with 12.84 seconds measured compression cost. Keep an uncompressed one-day table for frequent selected-meter reads. Meter segmentation kept Q4 close to the raw baseline but used more storage, took longer to compress, and made Q1 much slower.

## 5. Investigate utility data

### 5.1 Demand patterns

Weekly network energy increased over the four periods: 934,199.061 kWh (1 Sep), 953,714.972 kWh (8 Sep), 973,230.026 kWh (15 Sep), and 992,560.288 kWh (22 Sep). The top network demand interval was 28 Sep 2026 at 13:00 CAT, 7,993.691 kW; the next were 12:45 at 7,943.947 kW and 13:15 at 7,943.636 kW. kW describes interval-average demand; kWh sums consumed energy. The day and week charts are in results/.

**Evidence to insert:** executed analysis, daily/weekly charts, and top-three intervals.

### 5.2 Regions and customer types

Each region has 400 registered meters. Region 8 was highest at 1,258.690 kWh per meter and Region 4 lowest at 811.011 kWh per meter. Customer-type totals were: industrial 2,220,672.036 kWh across 406 meters (5,469.636 kWh/meter); commercial 825,475.153 kWh across 1,010 meters (817.302 kWh/meter); residential 807,557.158 kWh across 2,584 meters (312.522 kWh/meter). Differences persist after normalization, so the group totals are not explained solely by group size.

**Evidence to insert:** group totals/counts and comparison query output.

### 5.3 Reporting quality

Overall completeness was 98.993071%. Regional completeness ranged from 98.969308% (Region 6) to 99.012928% (Region 8). For 21 Sep, 149,400.545 kWh had arrived by midnight on 22 Sep, versus a finalized 149,552.723 kWh. The fresh run measured a late-arrival difference of 152.178 kWh, or 0.101756% of the final total. Missing and late readings can make early reports incomplete.

**Evidence to insert:** network and regional completeness and arrival cutoff/final comparison.

### 5.4 Anomalies

The rule compares each reading with the same meter’s median for the same CAT hour and weekday. It flags a ratio at least 2.3 or at most 0.10. Event labels were used only after detection for evaluation. The saved findings report 40/40 injected intervals detected, 0 false flags among 10,643,261 readings outside event intervals, and 0 of 4,000 meters affected by false flags.

**Evidence to insert:** detector run, flagged rows, and event-level evaluation.

### 5.5 Management recommendation

Use the one-day time-only compressed layout for historical reports and retain an uncompressed one-day table for selective recent reads. The time-only layout reduced total size by 69.39% and improved four of five query medians, with the selected-meter query as the tradeoff. For next-day planning, use the selected RF_300 model as decision support. On the fresh test metrics, its MAE/RMSE were 5.133/7.147 kWh versus 42.708/79.403 kWh for the previous-day baseline. Display freshness and missing-data limitations because finalized historical totals can exceed early live totals. Use regional and customer-type demand patterns to focus operational load management and capacity review. Reassess with additional seasons and live-arrival replay before operational deployment.

## 6. Continuous aggregates

### 6.1 Definitions and refresh

Three materialized-only aggregates are defined: 15-minute region, CAT hour region, and CAT day meter. Saved initial full-refresh times and materialization sizes are:

| View | Refresh | Rows | Materialized total |
|---|---:|---:|---:|
| energy_15m_region | 0.045 s | 26,880 | 4,382,720 bytes |
| energy_hour_region | 0.012 s | 6,720 | 1,318,912 bytes |
| energy_day_meter | 0.012 s | 112,000 | 13,197,312 bytes |

Refresh timings were recorded before policies were installed. The SQL scripts define the policy schedule and lookback/end offsets.

**Evidence to insert:** view definitions, populated examples, sizes, policy settings and background-job status.

### 6.2 Freshness and delayed arrivals

At 12:10 CAT on 15 Oct, H was 11:00 and the older test hour was 11:00 on 13 Oct. The first older-hour insert aggregated to 1 kWh/one row. After adding 0.5 kWh to that older bucket and 2 kWh to H, with real-time aggregation off, the older bucket remained at 1 kWh/one row and H had no aggregate row. With real-time aggregation on, H showed 2 kWh/one row while the older bucket remained stale. After manually refreshing both hours, the older bucket showed 1.5 kWh/two rows and H showed 2 kWh/one row.

**Evidence to insert:** definitions, inserts, real-time mode, and raw/aggregate query output for each stage.

## 7. Dashboards

### 7.1 Raw and 7.2 Aggregate dashboards

The Dash app provides Raw and Aggregate modes with date/meter filters and five panels: hourly regional energy, daily network energy, weekly network energy, selected-meter daily energy, and regional completeness. Raw mode queries the base readings; Aggregate mode uses the continuous aggregates. The app source and panel queries are in dashboard.py.

**Evidence to insert:** both running dashboard modes and their panel query definitions.

### 7.3 Numerical agreement

For 22–29 Sep, the saved comparison found matching keys and counts across all five panels. It compared 1,680 hourly-region rows, 7 daily rows, 1 weekly row, 7 selected-meter daily rows, and 10 regional-completeness rows. Maximum energy differences were below 0.000001 kWh and there were no reading-count mismatches; completeness difference was zero.

**Evidence to insert:** paired filtered dashboards and numerical comparison output.

### 7.4 Performance tradeoff — outstanding

The project record says browser refresh performance was not measured. Assignment evidence requires one warm-up and ten measured refreshes per mode, individual panel query durations, full-dashboard render duration, and median/min/max. Do not substitute SQL benchmark timings for browser-render timings. Capture these on the same machine/browser with result caching disabled and assignment jobs paused. Then compare the timing cost with aggregate storage and refresh costs above.

## 8. Forecast the next day

### 8.1 Data, splits, and features

The script creates hourly regional targets from cleaned readings, preserving absent target hours as missing. It splits targets chronologically: 1–14 Sep train, 15–21 Sep validation, and 22–28 Sep test. The script reports 1,680 retained training rows after excluding 1,680 of 3,360 pre-lookback training rows; validation and test each contain 1,680 rows. Features are region, hour, weekday, day of year, 24-hour lag, 168-hour lag, and a prior-week same-hour mean. Imputation is fitted inside each training pipeline. Lag-source checks verify every lag is before that day’s 00:00 forecast origin.

**Evidence to insert:** split dates/counts, feature catalog/examples, and lag-origin check.

### 8.2 Baseline and 8.3 Model

The previous-day matching-hour baseline generated 1,680 test predictions. Two configurations were trained on the same 1,680 rows: RF_300 and HGB_depth3. RF_300 had the lower validation MAE (4.679 kWh; RMSE 6.109 kWh) and was selected. The selected fitted pipeline is saved at results/selected_forecast_model.joblib.

**Evidence to insert:** baseline run and sample predictions; model settings and validation comparison.

### 8.4 Test usefulness

Fresh test metrics across 1,680 region-hours, produced on 15 Oct 2026:

| Method | MAE | RMSE |
|---|---:|---:|
| Previous-day baseline | 42.708 kWh | 79.403 kWh |
| RF_300 | 5.133 kWh | 7.147 kWh |

Region-level metrics, peak-hour errors, predictions, and plot are saved under results/. These results indicate a substantial improvement on the fixed historical test split. Peak-hour error and missing-reading limitations still matter for operational planning; this is an offline forecast of finalized historical consumption.

**Evidence to insert:** metric outputs, regional peak errors, and forecast plot.

## 9. Submission and reproducibility

The repository contains the unchanged simulator, source scripts, SQL, README, environment notes, and saved measurements. Before submission, add the final group names, IDs, and contribution statement; capture every subsection’s required screenshot with synchronized CAT clock and taskbar; complete dashboard timings; resolve the fresh MQTT authorization failure and verify the EMQX requirement or document the Mosquitto deviation; record physical storage type; and create/check the final report PDF, GitHub repository URL, and ZIP against the same final file set. Keep credentials out of both packages.

**Evidence to insert:** final package inventory, repository URL, and contribution table.

---

## Evidence checklist

Each bracketed evidence note above must be replaced with the required real screenshot(s) beside its subsection. The existing charts and CSVs are analysis outputs, not substitutes for screenshots of executed commands, database checks, or dashboard sessions. Confirm host clock synchronization before recording new timings.
