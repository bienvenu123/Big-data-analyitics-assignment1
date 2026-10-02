SET TIME ZONE 'Africa/Kigali';
-- Run before cleaning.
WITH observed AS (
  SELECT meter_id,event_time,COUNT(*) AS copies,
         MIN(received_time-event_time) AS min_delay, MAX(received_time-event_time) AS max_delay
  FROM energy_readings GROUP BY meter_id,event_time
), totals AS (
  SELECT COUNT(*) AS unique_readings,
         SUM(copies-1) AS duplicate_readings,
         COUNT(*) FILTER (WHERE max_delay > INTERVAL '15 minutes') AS delayed_unique_readings
  FROM observed
)
SELECT *, 10752000-unique_readings AS missing_readings,
       100.0*(10752000-unique_readings)/10752000 AS missing_pct,
       100.0*duplicate_readings/unique_readings AS duplicate_pct,
       100.0*delayed_unique_readings/unique_readings AS delayed_pct,
       100.0*unique_readings/10752000 AS completeness_pct
FROM totals;

SELECT m.meter_id, 28*96-COUNT(DISTINCT (r.meter_id,r.event_time)) AS missing_count
FROM meters m LEFT JOIN energy_readings r USING(meter_id)
GROUP BY m.meter_id ORDER BY missing_count DESC,meter_id LIMIT 5;

-- Exact query set Q1-Q5. Replace only the table name when benchmarking.
-- Q1
SELECT time_bucket(INTERVAL '1 hour',event_time) AS hour,AVG(power_kw) AS avg_kw
FROM energy_readings WHERE event_time >= TIMESTAMPTZ '2026-09-21 00:00:00+02'
 AND event_time < TIMESTAMPTZ '2026-09-22 00:00:00+02' GROUP BY hour ORDER BY hour;
-- Q2
SELECT event_time,SUM(power_kw) AS total_kw FROM energy_readings
WHERE event_time >= TIMESTAMPTZ '2026-09-22 00:00:00+02' AND event_time < TIMESTAMPTZ '2026-09-29 00:00:00+02'
GROUP BY event_time ORDER BY total_kw DESC,event_time ASC LIMIT 10;
-- Q3
SELECT meter_id,SUM(energy_kwh) AS total_kwh FROM energy_readings GROUP BY meter_id ORDER BY meter_id;
-- Q4
SELECT SUM(energy_kwh) AS total_kwh,AVG(power_kw) AS avg_kw,MAX(power_kw) AS peak_kw
FROM energy_readings WHERE meter_id=1000000000 AND event_time >= TIMESTAMPTZ '2026-09-22 00:00:00+02'
AND event_time < TIMESTAMPTZ '2026-09-29 00:00:00+02';
-- Q5
SELECT COUNT(*) AS row_count,SUM(energy_kwh) AS total_kwh,AVG(power_kw) AS avg_kw,
MIN(power_kw) AS min_kw,MAX(power_kw) AS max_kw FROM energy_readings;

-- Full history totals used by the report.
SELECT event_time::date AS cat_day,SUM(energy_kwh) AS energy_kwh FROM energy_readings GROUP BY 1 ORDER BY 1;
SELECT date_trunc('week',event_time) AS week_start,SUM(energy_kwh) AS energy_kwh FROM energy_readings GROUP BY 1 ORDER BY 1;
SELECT event_time,SUM(power_kw) AS network_kw FROM energy_readings GROUP BY event_time ORDER BY network_kw DESC,event_time LIMIT 3;
SELECT m.region,m.customer_type,COUNT(DISTINCT m.meter_id) AS meters,SUM(r.energy_kwh) AS total_kwh,
       SUM(r.energy_kwh)/COUNT(DISTINCT m.meter_id) AS kwh_per_meter
FROM energy_readings r JOIN meters m USING(meter_id) GROUP BY GROUPING SETS ((m.region),(m.customer_type)) ORDER BY 1,2;

-- For comparison table copies after loading and ANALYZE:
-- INSERT INTO energy_readings_3h SELECT * FROM energy_readings;
-- INSERT INTO energy_readings_week SELECT * FROM energy_readings;
