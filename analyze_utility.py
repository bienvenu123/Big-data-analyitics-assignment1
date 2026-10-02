"""Run the Section 5 utility-data summaries and create report charts."""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import psycopg

OUT=Path("results");OUT.mkdir(exist_ok=True)


def main():
    with psycopg.connect(os.getenv("DATABASE_URL","")) as conn:
        conn.execute("SET TIME ZONE 'Africa/Kigali'")
        daily=pd.read_sql("""SELECT event_time::date AS cat_day,SUM(energy_kwh) AS energy_kwh
           FROM energy_readings GROUP BY 1 ORDER BY 1""",conn)
        weekly=pd.read_sql("""SELECT date_bin(INTERVAL '7 days',event_time,TIMESTAMPTZ '2026-09-01 00:00:00+02') AS period_start,
           SUM(energy_kwh) AS energy_kwh FROM energy_readings GROUP BY 1 ORDER BY 1""",conn)
        peaks=pd.read_sql("""SELECT event_time,SUM(power_kw) AS network_kw FROM energy_readings
           GROUP BY event_time ORDER BY network_kw DESC,event_time ASC LIMIT 3""",conn)
        groups=pd.read_sql("""SELECT 'region' AS group_type,m.region AS group_name,COUNT(DISTINCT m.meter_id) AS meter_count,
           SUM(r.energy_kwh) AS total_kwh,SUM(r.energy_kwh)/COUNT(DISTINCT m.meter_id) AS kwh_per_meter
           FROM energy_readings r JOIN meters m USING(meter_id) GROUP BY m.region
           UNION ALL
           SELECT 'customer_type',m.customer_type,COUNT(DISTINCT m.meter_id),SUM(r.energy_kwh),
           SUM(r.energy_kwh)/COUNT(DISTINCT m.meter_id)
           FROM energy_readings r JOIN meters m USING(meter_id) GROUP BY m.customer_type
           ORDER BY 1,2""",conn)
        completeness=pd.read_sql("""WITH reg AS (
             SELECT region,COUNT(*) AS registered FROM meters GROUP BY region),
           obs AS (SELECT m.region,COUNT(DISTINCT (r.meter_id,r.event_time)) AS observed
             FROM meters m LEFT JOIN energy_readings r USING(meter_id) GROUP BY m.region)
           SELECT r.region,r.registered,COALESCE(o.observed,0) AS observed,r.registered*28*96 AS planned,
           100.0*COALESCE(o.observed,0)/(r.registered*28*96) AS completeness_pct
           FROM reg r JOIN obs o USING(region) ORDER BY r.region""",conn)
        daily_cutoff=pd.read_sql("""SELECT
           SUM(energy_kwh) FILTER(WHERE received_time<=TIMESTAMPTZ '2026-09-22 00:00:00+02') AS available_by_midnight,
           SUM(energy_kwh) AS final_total,
           SUM(energy_kwh) FILTER(WHERE received_time>TIMESTAMPTZ '2026-09-22 00:00:00+02') AS delayed_after_midnight
           FROM energy_readings WHERE event_time>=TIMESTAMPTZ '2026-09-21 00:00:00+02'
           AND event_time<TIMESTAMPTZ '2026-09-22 00:00:00+02'""",conn)
        overall=pd.read_sql("""SELECT (SELECT COUNT(*) FROM meters) AS registered,
           COUNT(DISTINCT (meter_id,event_time)) AS observed,
           (SELECT COUNT(*) FROM meters)*28*96 AS planned,
           100.0*COUNT(DISTINCT (meter_id,event_time))/((SELECT COUNT(*) FROM meters)*28*96) AS completeness_pct
           FROM energy_readings""",conn)
    weekly["period_start"]=pd.to_datetime(weekly.period_start,utc=True).dt.tz_convert("Africa/Johannesburg")
    peaks["event_time"]=pd.to_datetime(peaks.event_time,utc=True).dt.tz_convert("Africa/Johannesburg")
    daily_cutoff["difference_kwh"]=daily_cutoff.final_total-daily_cutoff.available_by_midnight
    daily_cutoff["difference_pct_of_final"]=100*daily_cutoff.difference_kwh/daily_cutoff.final_total
    daily.to_csv(OUT/"network_daily_energy.csv",index=False)
    weekly.to_csv(OUT/"network_weekly_energy.csv",index=False)
    peaks.to_csv(OUT/"network_peak_intervals.csv",index=False)
    groups.to_csv(OUT/"group_energy.csv",index=False)
    completeness.to_csv(OUT/"regional_completeness.csv",index=False)
    daily_cutoff.to_csv(OUT/"sep21_arrival_comparison.csv",index=False)
    overall.to_csv(OUT/"network_completeness.csv",index=False)
    fig,ax=plt.subplots(figsize=(12,4.5));ax.bar(pd.to_datetime(daily.cat_day),daily.energy_kwh,color="#1976d2")
    ax.set(title="Daily network energy",ylabel="Energy (kWh)",xlabel="CAT date");fig.tight_layout()
    fig.savefig(OUT/"network_daily_energy.png",dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5));ax.bar(pd.to_datetime(weekly.period_start),weekly.energy_kwh,width=4.5,color="#00897b")
    ax.set(title="Seven-day network energy",ylabel="Energy (kWh)",xlabel="CAT period starting");fig.tight_layout()
    fig.savefig(OUT/"network_weekly_energy.png",dpi=160);plt.close(fig)
    print("Daily energy:");print(daily.to_string(index=False))
    print("Weekly totals:");print(weekly.to_string(index=False))
    print("Peak demand intervals:");print(peaks.to_string(index=False))
    print("Group totals and per-meter energy:");print(groups.to_string(index=False))
    print("Completeness:");print(overall.to_string(index=False));print(completeness.to_string(index=False))
    print("21 September arrival cutoff:");print(daily_cutoff.to_string(index=False))


if __name__=="__main__":main()
