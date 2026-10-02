"""Time full initial refreshes, size materializations, then add 6.1 policies."""
from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql

CAT=ZoneInfo("Africa/Johannesburg")
VIEWS=["energy_15m_region","energy_hour_region","energy_day_meter"]
START="2026-09-01 00:00:00+02"
END="2026-09-29 00:00:00+02"


def main():
    Path("results").mkdir(exist_ok=True)
    records=[]
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-aggregate-refresh")
    conn.autocommit=True
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    with conn:
      with conn.cursor() as cur:
       for view in VIEWS:
        begin=datetime.now(CAT);tick=time.perf_counter()
        cur.execute("CALL refresh_continuous_aggregate(%s::regclass,%s::timestamptz,%s::timestamptz)",(view,START,END))
        elapsed=time.perf_counter()-tick;finish=datetime.now(CAT)
        cur.execute("""SELECT materialization_hypertable_schema,materialization_hypertable_name FROM timescaledb_information.continuous_aggregates
                       WHERE view_name=%s""",(view,))
        mat_schema,mat=cur.fetchone();mat_ref=f"{mat_schema}.{mat}"
        cur.execute("SELECT table_bytes,index_bytes,toast_bytes,total_bytes FROM hypertable_detailed_size(%s::regclass)",(mat_ref,))
        table_b,index_b,toast_b,total_b=cur.fetchone()
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(sql.Identifier(mat_schema),sql.Identifier(mat)))
        n=cur.fetchone()[0]
        records.append({"view":view,"materialization_hypertable":mat_ref,"refresh_start_CAT":begin.isoformat(),
          "refresh_end_CAT":finish.isoformat(),"refresh_seconds":elapsed,"materialized_rows":n,
          "data_bytes":table_b+toast_b,"index_bytes":index_b,"total_bytes":total_b})
        print(f"{view}: {elapsed:.3f}s; rows={n}; size={total_b/1e6:.3f} MB",flush=True)
       # Add policies only after the manual full-range refresh measurements.
       for view in VIEWS:
        cur.execute("""SELECT add_continuous_aggregate_policy(%s::regclass,
            start_offset=>INTERVAL '3 days',end_offset=>INTERVAL '1 hour',
            schedule_interval=>INTERVAL '15 minutes',if_not_exists=>true)""",(view,))
        cur.fetchone()
    with open("results/aggregate_refreshes.csv","w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    conn.close()


if __name__=="__main__":main()
