-- Run with psql against the assignment database.
CREATE EXTENSION IF NOT EXISTS timescaledb;
SET TIME ZONE 'Africa/Kigali';

CREATE TABLE IF NOT EXISTS meters (
  meter_id BIGINT PRIMARY KEY,
  region TEXT NOT NULL,
  customer_type TEXT NOT NULL,
  base_power_kw DOUBLE PRECISION NOT NULL,
  power_factor DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS energy_live (
  meter_id BIGINT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  received_time TIMESTAMPTZ NOT NULL,
  power_kw DOUBLE PRECISION NOT NULL,
  voltage_v DOUBLE PRECISION NOT NULL,
  current_a DOUBLE PRECISION NOT NULL,
  frequency_hz DOUBLE PRECISION NOT NULL,
  energy_kwh DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS energy_readings (
  meter_id BIGINT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  received_time TIMESTAMPTZ NOT NULL,
  power_kw DOUBLE PRECISION NOT NULL,
  voltage_v DOUBLE PRECISION NOT NULL,
  current_a DOUBLE PRECISION NOT NULL,
  frequency_hz DOUBLE PRECISION NOT NULL,
  energy_kwh DOUBLE PRECISION NOT NULL
);
SELECT create_hypertable('energy_readings','event_time',chunk_time_interval => INTERVAL '1 day',if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS energy_readings_event_time_idx ON energy_readings (event_time);
CREATE INDEX IF NOT EXISTS energy_readings_meter_event_idx ON energy_readings (meter_id,event_time);

-- Chunk-interval comparison copies. Populate only after cleaning.
CREATE TABLE IF NOT EXISTS energy_readings_3h (LIKE energy_readings INCLUDING DEFAULTS);
SELECT create_hypertable('energy_readings_3h','event_time',chunk_time_interval => INTERVAL '3 hours',if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS energy_readings_3h_event_idx ON energy_readings_3h (event_time);
CREATE INDEX IF NOT EXISTS energy_readings_3h_meter_event_idx ON energy_readings_3h (meter_id,event_time);

CREATE TABLE IF NOT EXISTS energy_readings_week (LIKE energy_readings INCLUDING DEFAULTS);
SELECT create_hypertable('energy_readings_week','event_time',chunk_time_interval => INTERVAL '1 week',if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS energy_readings_week_event_idx ON energy_readings_week (event_time);
CREATE INDEX IF NOT EXISTS energy_readings_week_meter_event_idx ON energy_readings_week (meter_id,event_time);

-- Initial 15-minute regional continuous aggregate; create additional rollups in
-- sql/aggregates.sql once the base data and policy timing requirements are met.
CREATE MATERIALIZED VIEW IF NOT EXISTS energy_15m_region
WITH (timescaledb.continuous, timescaledb.materialized_only=true) AS
SELECT time_bucket(INTERVAL '15 minutes',r.event_time) AS bucket, m.region,
       SUM(r.energy_kwh) AS energy_kwh, SUM(r.power_kw) AS power_kw,
       COUNT(*) AS reading_count
FROM energy_readings r JOIN meters m USING (meter_id)
GROUP BY bucket,m.region WITH NO DATA;
