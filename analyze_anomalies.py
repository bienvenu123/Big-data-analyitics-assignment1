"""Rule-based anomaly flags and evaluation against simulator labels."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg


def main():
    import smart_meter_simulator as simulator
    with psycopg.connect(os.getenv("DATABASE_URL", "")) as conn:
        readings = pd.read_sql("""SELECT meter_id,event_time,power_kw FROM energy_readings
             ORDER BY meter_id,event_time""", conn)
    readings["event_time"] = pd.to_datetime(readings.event_time, utc=True).dt.tz_convert("Africa/Johannesburg")
    readings["hour"] = readings.event_time.dt.hour
    readings["weekday"] = readings.event_time.dt.dayofweek
    # Compare each reading with the meter's median at the same local hour and
    # weekday. Flags require a large multiplicative departure from that baseline.
    baseline = readings.groupby(["meter_id","weekday","hour"]).power_kw.transform("median")
    readings["expected_kw"] = baseline
    readings["ratio"] = readings.power_kw / baseline
    readings["flag"] = (readings.ratio >= 2.3) | (readings.ratio <= 0.10)
    labels = pd.DataFrame(simulator.anomaly_events())
    for col in ("start_time","end_time"):
        labels[col] = pd.to_datetime(labels[col],utc=True).dt.tz_convert("Africa/Johannesburg")
    by_meter = {m: g for m,g in readings.groupby("meter_id")}
    detected = 0
    for event in labels.itertuples(index=False):
        rows = by_meter[event.meter_id]
        detected += int(((rows.event_time >= event.start_time) & (rows.event_time < event.end_time) & rows.flag).any())
    # Mark all readings inside any known event interval only for score calculation.
    in_event = pd.Series(False,index=readings.index)
    for event in labels.itertuples(index=False):
        mask=(readings.meter_id.eq(event.meter_id)&readings.event_time.ge(event.start_time)&readings.event_time.lt(event.end_time))
        in_event |= mask
    false = readings.flag & ~in_event
    outside_count=(~in_event).sum()
    false_meters=readings.loc[false,"meter_id"].nunique()
    Path("results").mkdir(exist_ok=True)
    readings.loc[readings.flag].to_csv("results/anomaly_flags.csv",index=False)
    print(f"detected_events={detected}/{len(labels)}; missed={len(labels)-detected}")
    print(f"false_flags={int(false.sum())}; outside_readings={int(outside_count)}; false_pct={100*false.sum()/outside_count:.6f}")
    print(f"meters_with_false_flags={false_meters}/4000; affected_meter_pct={100*false_meters/4000:.4f}")
    print("Rule: hour-and-weekday meter median ratio >=2.3 or <=0.10; labels were used only for evaluation.")


if __name__ == "__main__":
    main()
