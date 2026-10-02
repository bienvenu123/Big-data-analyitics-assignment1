-- Recreate empty materialized-only views for the initial-refresh experiment.
-- Run only after the clean source data is loaded; refresh_aggregates.py then
-- measures full historical refreshes before it installs the policies.
DROP MATERIALIZED VIEW IF EXISTS energy_day_meter;
DROP MATERIALIZED VIEW IF EXISTS energy_hour_region;
DROP MATERIALIZED VIEW IF EXISTS energy_15m_region;

CREATE MATERIALIZED VIEW energy_15m_region
WITH (timescaledb.continuous, timescaledb.materialized_only=true) AS
SELECT time_bucket(INTERVAL '15 minutes',r.event_time) AS bucket,m.region,
       SUM(r.energy_kwh) AS energy_kwh,SUM(r.power_kw) AS power_kw,COUNT(*) AS reading_count
FROM energy_readings r JOIN meters m USING(meter_id)
GROUP BY bucket,m.region WITH NO DATA;

CREATE MATERIALIZED VIEW energy_hour_region
WITH (timescaledb.continuous, timescaledb.materialized_only=true) AS
SELECT time_bucket(INTERVAL '1 hour',r.event_time) AS bucket,m.region,
       SUM(r.energy_kwh) AS energy_kwh,SUM(r.power_kw) AS power_kw,COUNT(*) AS reading_count
FROM energy_readings r JOIN meters m USING(meter_id)
GROUP BY bucket,m.region WITH NO DATA;

CREATE MATERIALIZED VIEW energy_day_meter
WITH (timescaledb.continuous, timescaledb.materialized_only=true) AS
SELECT time_bucket(INTERVAL '1 day',event_time,'Africa/Kigali') AS bucket,meter_id,
       SUM(energy_kwh) AS energy_kwh,SUM(power_kw) AS power_kw,COUNT(*) AS reading_count
FROM energy_readings GROUP BY bucket,meter_id WITH NO DATA;
