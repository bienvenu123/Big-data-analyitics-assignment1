# Database data dictionary

All timestamps are stored as `TIMESTAMPTZ`. Analysis sessions use `Africa/Kigali` (CAT, UTC+02:00). Each measurement represents one 15-minute interval starting at `event_time`; `received_time` is the generator's simulated arrival time.

## Reading tables

`energy_live` is a regular pilot table. `energy_readings` is the one-day chunk baseline; `energy_readings_3h` and `energy_readings_week` are the interval comparison hypertables. `energy_time_compressed` and `energy_meter_compressed` use one-day chunks with their named compression layouts.

| Column | PostgreSQL type | Meaning | Unit |
|---|---|---|---|
| `meter_id` | BIGINT | Registered smart meter identifier | none |
| `event_time` | TIMESTAMPTZ | Start of the 15-minute measurement interval | CAT timestamp |
| `received_time` | TIMESTAMPTZ | Simulated arrival time of the reading | CAT timestamp |
| `power_kw` | DOUBLE PRECISION | Average active power over the interval | kW |
| `voltage_v` | DOUBLE PRECISION | Voltage | V |
| `current_a` | DOUBLE PRECISION | Current at power factor 0.95 | A |
| `frequency_hz` | DOUBLE PRECISION | Grid frequency | Hz |
| `energy_kwh` | DOUBLE PRECISION | Energy consumed in this interval (`power_kw × 0.25 h`, rounded) | kWh |

The reading tables intentionally have no uniqueness constraint, so the pilot can retain deliberate duplicate messages. The historical comparison tables are populated only after the clean baseline is ready.

## `meters`

| Column | PostgreSQL type | Meaning | Unit |
|---|---|---|---|
| `meter_id` | BIGINT PRIMARY KEY | Stable meter identifier | none |
| `region` | TEXT | Registered region label | none |
| `customer_type` | TEXT | Residential, commercial or industrial class | none |
| `base_power_kw` | DOUBLE PRECISION | Generated customer base load | kW |
| `power_factor` | DOUBLE PRECISION | Power factor used for current calculation | none |

## Continuous aggregate views

`energy_15m_region` and `energy_hour_region` group by `bucket` and `region`; `energy_day_meter` groups by `bucket` and `meter_id`. Each stores `bucket TIMESTAMPTZ`, its grouping key (`region TEXT` or `meter_id BIGINT`), `energy_kwh DOUBLE PRECISION` (kWh), `power_kw DOUBLE PRECISION` (summed interval-average kW) and `reading_count BIGINT` (readings). The views are materialized-only for the historical/dashboard measurements.

## Freshness test objects

`energy_freshness_test` contains `event_time TIMESTAMPTZ` (hourly bucket source) and `energy_kwh DOUBLE PRECISION` (kWh). `energy_freshness_hourly` stores `bucket TIMESTAMPTZ`, `energy_kwh DOUBLE PRECISION` (kWh) and `reading_count BIGINT` (rows in the hour).
