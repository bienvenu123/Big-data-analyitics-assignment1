-- Run only after the full load and diagnostic review. All six payload values
-- must match within each duplicate group. If conflicts exist, stop and inspect.
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM energy_readings
    GROUP BY meter_id,event_time
    HAVING COUNT(DISTINCT (received_time,power_kw,voltage_v,current_a,frequency_hz,energy_kwh)) > 1
  ) THEN
    RAISE EXCEPTION 'Conflicting duplicates found; investigate before cleanup';
  END IF;
END $$;

WITH ranked AS (
  -- ctid repeats in different Timescale chunks; pair it with tableoid.
  SELECT tableoid,ctid,ROW_NUMBER() OVER (PARTITION BY meter_id,event_time ORDER BY tableoid,ctid) AS rn
  FROM energy_readings
)
DELETE FROM energy_readings e USING ranked r
WHERE e.tableoid=r.tableoid AND e.ctid=r.ctid AND r.rn>1;

ANALYZE energy_readings;
SELECT COUNT(*) AS rows_after_cleaning,
       COUNT(DISTINCT (meter_id,event_time)) AS unique_pairs,
       SUM(energy_kwh) AS total_energy_kwh
FROM energy_readings;
