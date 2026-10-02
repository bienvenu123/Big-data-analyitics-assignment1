"""Run the assignment's warm-cache Q1–Q5 timing protocol on loaded tables."""
from __future__ import annotations

import argparse
import csv
import os
import platform
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

CAT = ZoneInfo("Africa/Johannesburg")
TABLES = ["energy_readings", "energy_readings_3h", "energy_readings_week",
          "energy_time_compressed", "energy_meter_compressed"]
QUERIES = {
 "Q1": """SELECT time_bucket(INTERVAL '1 hour',event_time) AS hour,AVG(power_kw) AS avg_kw
 FROM {table} WHERE event_time>=TIMESTAMPTZ '2026-09-21 00:00:00+02'
 AND event_time<TIMESTAMPTZ '2026-09-22 00:00:00+02' GROUP BY 1 ORDER BY 1""",
 "Q2": """SELECT event_time,SUM(power_kw) AS total_kw FROM {table}
 WHERE event_time>=TIMESTAMPTZ '2026-09-22 00:00:00+02' AND event_time<TIMESTAMPTZ '2026-09-29 00:00:00+02'
 GROUP BY event_time ORDER BY total_kw DESC,event_time ASC LIMIT 10""",
 "Q3": "SELECT meter_id,SUM(energy_kwh) AS total_kwh FROM {table} GROUP BY meter_id ORDER BY meter_id",
 "Q4": """SELECT SUM(energy_kwh),AVG(power_kw),MAX(power_kw) FROM {table}
 WHERE meter_id=1000000000 AND event_time>=TIMESTAMPTZ '2026-09-22 00:00:00+02'
 AND event_time<TIMESTAMPTZ '2026-09-29 00:00:00+02'""",
 "Q5": "SELECT COUNT(*),SUM(energy_kwh),AVG(power_kw),MIN(power_kw),MAX(power_kw) FROM {table}",
}


def cat_now():
    return datetime.now(CAT).isoformat(timespec="milliseconds")


def results_match(a_rows, b_rows):
    if len(a_rows) != len(b_rows): return False
    for a_row,b_row in zip(a_rows,b_rows):
        if len(a_row) != len(b_row): return False
        for a,b in zip(a_row,b_row):
            if isinstance(a,(int,float)) and isinstance(b,(int,float)):
                if abs(a-b)>0.001: return False
            elif a != b: return False
    return True


def run(tables):
    Path("results").mkdir(exist_ok=True)
    machine = platform.node()
    conn = psycopg.connect(os.getenv("DATABASE_URL", ""), application_name="Assignment-I-benchmark")
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    runs=[]
    baselines={}
    session_start=None; session_tick=None
    with conn:
      with conn.cursor() as cur:
       for table in tables:
        if table not in TABLES: raise ValueError(f"invalid table: {table}")
        for qid,template in QUERIES.items():
         sql=template.format(table=table)
         if session_start is None:
          session_start=cat_now();session_tick=time.perf_counter()
         cur.execute(sql); current=cur.fetchall(); baseline=baselines.setdefault(qid,current)
         if not results_match(current,baseline): raise RuntimeError(f"result mismatch {qid} on {table}")
         for n in range(1,6):
          start=cat_now(); tick=time.perf_counter_ns()
          cur.execute(sql); rows=cur.fetchall()
          ms=(time.perf_counter_ns()-tick)/1e6; end=cat_now()
          if not results_match(rows,baseline): raise RuntimeError(f"result mismatch {qid} on {table}")
          runs.append({"table":table,"query":qid,"run":n,"start_CAT":start,"end_CAT":end,
                       "duration_ms":ms,"machine":machine,"rows":len(rows)})
         print(f"{table} {qid}: warm-up plus five runs complete",flush=True)
    conn.close()
    with open("results/benchmark_runs.csv","w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(runs[0])); writer.writeheader(); writer.writerows(runs)
    summaries=[]
    for table in tables:
        for qid in QUERIES:
            vals=[r["duration_ms"] for r in runs if r["table"]==table and r["query"]==qid]
            ordered=sorted(vals); n=len(vals)
            median=(ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2)
            summaries.append({"table":table,"query":qid,"median_ms":median,"min_ms":ordered[0],"max_ms":ordered[-1]})
    with open("results/benchmark_summary.csv","w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(summaries[0])); writer.writeheader(); writer.writerows(summaries)
    session_end=cat_now()
    with open("results/benchmark_session.csv","w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["machine","client","session_start_CAT","session_end_CAT","session_seconds"])
        writer.writeheader();writer.writerow({"machine":machine,"client":"psycopg 3 / Python",
          "session_start_CAT":session_start,"session_end_CAT":session_end,
          "session_seconds":time.perf_counter()-session_tick})
    for row in summaries: print(row)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--tables",nargs="+",default=TABLES[:3])
    run(parser.parse_args().tables)
