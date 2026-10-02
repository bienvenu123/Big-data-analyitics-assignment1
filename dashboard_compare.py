"""Numerical raw-versus-aggregate check for the 7.3 dashboard filters."""
from __future__ import annotations

import csv
import os
from datetime import date,datetime,time,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

CAT=ZoneInfo("Africa/Johannesburg")
START=datetime(2026,9,22,tzinfo=CAT);END=datetime(2026,9,29,tzinfo=CAT)
METER=1000000000;DAYS=7


def fetch(cur,sql,args):cur.execute(sql,args);return cur.fetchall()


def compare(name,raw,agg,energy=True):
    rd={r[0]:r[1:] for r in raw};ad={r[0]:r[1:] for r in agg}
    if rd.keys()!=ad.keys():raise RuntimeError(f"{name}: key mismatch ({len(rd)} vs {len(ad)})")
    max_energy=max((abs(rd[k][0]-ad[k][0]) for k in rd),default=0) if energy else 0
    count_diffs=[(k,rd[k][1],ad[k][1]) for k in rd if rd[k][1]!=ad[k][1]]
    if count_diffs:raise RuntimeError(f"{name}: reading count mismatch, sample={count_diffs[:3]}")
    if max_energy>0.001:raise RuntimeError(f"{name}: energy difference {max_energy} > 0.001 kWh")
    return {"panel":name,"compared_rows":len(rd),"max_abs_energy_diff_kwh":max_energy,"reading_count_mismatches":len(count_diffs)}


def main():
    Path("results").mkdir(exist_ok=True);out=[]
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-dashboard-check")
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    with conn:
      with conn.cursor() as cur:
       raw=fetch(cur,"""SELECT time_bucket(INTERVAL '1 hour',event_time),region,SUM(energy_kwh),COUNT(*)
          FROM energy_readings r JOIN meters m USING(meter_id) WHERE event_time >= %s AND event_time < %s
          GROUP BY 1,2 ORDER BY 1,2""",(START,END))
       agg=fetch(cur,"""SELECT bucket,region,SUM(energy_kwh),SUM(reading_count) FROM energy_hour_region
          WHERE bucket >= %s AND bucket < %s GROUP BY 1,2 ORDER BY 1,2""",(START,END))
       out.append(compare("hourly_regional_energy",[( (r[0],r[1]),r[2],r[3]) for r in raw],
                          [((r[0],r[1]),r[2],r[3]) for r in agg]))
       raw=fetch(cur,"""SELECT event_time::date,SUM(energy_kwh),COUNT(*) FROM energy_readings
          WHERE event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(START,END))
       agg=fetch(cur,"""SELECT bucket::date,SUM(energy_kwh),SUM(reading_count) FROM energy_15m_region
          WHERE bucket >= %s AND bucket < %s GROUP BY 1 ORDER BY 1""",(START,END))
       out.append(compare("daily_network_energy",raw,agg))
       origin=datetime(2026,9,1,tzinfo=CAT)
       raw=fetch(cur,"""SELECT date_bin(INTERVAL '7 days',event_time,%s),SUM(energy_kwh),COUNT(*) FROM energy_readings
          WHERE event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(origin,START,END))
       agg=fetch(cur,"""SELECT date_bin(INTERVAL '7 days',bucket,%s),SUM(energy_kwh),SUM(reading_count) FROM energy_15m_region
          WHERE bucket >= %s AND bucket < %s GROUP BY 1 ORDER BY 1""",(origin,START,END))
       out.append(compare("seven_day_network_energy",raw,agg))
       raw=fetch(cur,"""SELECT event_time::date,SUM(energy_kwh),COUNT(*) FROM energy_readings
          WHERE meter_id=%s AND event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(METER,START,END))
       agg=fetch(cur,"""SELECT bucket::date,SUM(energy_kwh),SUM(reading_count) FROM energy_day_meter
          WHERE meter_id=%s AND bucket >= %s AND bucket < %s GROUP BY 1 ORDER BY 1""",(METER,START,END))
       out.append(compare("selected_meter_daily_energy",raw,agg))
       raw=fetch(cur,"""WITH reg AS(SELECT region,COUNT(*) AS registered FROM meters GROUP BY region),
          obs AS(SELECT m.region,COUNT(DISTINCT(r.meter_id,r.event_time)) FILTER(WHERE r.meter_id IS NOT NULL) AS observed
          FROM meters m LEFT JOIN energy_readings r ON r.meter_id=m.meter_id AND r.event_time >= %s AND r.event_time < %s GROUP BY m.region)
          SELECT reg.region,100.0*COALESCE(obs.observed,0)/(reg.registered*%s*96),COALESCE(obs.observed,0)
          FROM reg JOIN obs USING(region) ORDER BY reg.region""",(START,END,DAYS))
       agg=fetch(cur,"""WITH reg AS(SELECT region,COUNT(*) AS registered FROM meters GROUP BY region),
          obs AS(SELECT region,SUM(reading_count) AS observed FROM energy_15m_region WHERE bucket >= %s AND bucket < %s GROUP BY region)
          SELECT reg.region,100.0*COALESCE(obs.observed,0)/(reg.registered*%s*96),COALESCE(obs.observed,0)
          FROM reg LEFT JOIN obs USING(region) ORDER BY reg.region""",(START,END,DAYS))
       result=compare("regional_completeness",raw,agg,energy=False)
       result["max_abs_completeness_diff_percentage_points"]=max((abs(a[1]-b[1]) for a,b in zip(raw,agg)),default=0)
       out.append(result)
    conn.close()
    with open("results/dashboard_comparison.csv","w",newline="",encoding="utf-8") as f:
        fields=list(dict.fromkeys(k for row in out for k in row))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    for row in out:print(row)


if __name__=="__main__":main()
