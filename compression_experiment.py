"""Build the two one-day compression layouts and measure per-chunk work.

The experiment deliberately uses the 1-day uncompressed baseline. Run after the
cleaned source is ready and the compression result is empty.
"""
from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

CAT=ZoneInfo("Africa/Johannesburg")
CONFIGS={
 "energy_time_compressed":None,
 "energy_meter_compressed":"meter_id",
}


def now_cat(): return datetime.now(CAT)


def main():
    Path("results").mkdir(exist_ok=True)
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-compression")
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    with conn:
      with conn.cursor() as cur:
        start=now_cat(); cutoff=start.replace(tzinfo=None)-__import__('datetime').timedelta(hours=48)
        chunks=cur.execute("""SELECT chunk_schema,chunk_name,range_start,range_end
            FROM timescaledb_information.chunks WHERE hypertable_name='energy_readings'
            ORDER BY range_start""").fetchall()
        if not chunks: raise RuntimeError("source has no chunks")
        for table,segment in CONFIGS.items():
            cur.execute("SELECT to_regclass(%s)",(table,))
            exists=cur.fetchone()[0]
            if not exists:
                cur.execute(f"CREATE TABLE {table} (LIKE energy_readings INCLUDING DEFAULTS)")
                cur.execute("SELECT create_hypertable(%s,'event_time',chunk_time_interval=>INTERVAL '1 day')",(table,))
                cur.execute(f"CREATE INDEX {table}_event_idx ON {table}(event_time)")
                cur.execute(f"CREATE INDEX {table}_meter_event_idx ON {table}(meter_id,event_time)")
            else:
                cur.execute(f"SELECT count(*) FROM {table}")
                if cur.fetchone()[0]: raise RuntimeError(f"{table} is not empty; refusing to duplicate rows")
            options="timescaledb.compress=true,timescaledb.compress_orderby='event_time DESC'"
            if segment: options+=f",timescaledb.compress_segmentby='{segment}'"
            cur.execute(f"ALTER TABLE {table} SET ({options})")
            cur.execute("SELECT add_compression_policy(%s,INTERVAL '48 hours',if_not_exists=>true)",(table,))
            job=cur.fetchone()[0]
            cur.execute("SELECT alter_job(%s,scheduled=>false)",(job,))

        rows=[]
        for table in CONFIGS:
            for schema,name,lo,hi in chunks:
                cur.execute(f"INSERT INTO {table} SELECT * FROM energy_readings WHERE event_time >= %s AND event_time < %s",(lo,hi))
                load_count=cur.rowcount
                compress_s=0.0
                if hi.astimezone(CAT).replace(tzinfo=None) < cutoff:
                    cur.execute("""SELECT chunk_schema,chunk_name FROM timescaledb_information.chunks
                        WHERE hypertable_name=%s AND range_start=%s""",(table,lo))
                    destination=cur.fetchone()
                    if not destination: raise RuntimeError(f"destination chunk not found for {table} {lo}")
                    t=time.perf_counter()
                    cur.execute("SELECT compress_chunk(%s::regclass)",(f"{destination[0]}.{destination[1]}",))
                    cur.fetchone()
                    compress_s=time.perf_counter()-t
                rows.append({"table":table,"chunk_schema":schema,"source_chunk":name,
                             "range_start_CAT":lo.astimezone(CAT).isoformat(),
                             "range_end_CAT":hi.astimezone(CAT).isoformat(),
                             "rows_loaded":load_count,"cutoff_CAT":cutoff.isoformat(),
                             "compression_seconds":compress_s})
                print(f"{table}: {name} loaded={load_count} compressed={compress_s:.3f}s",flush=True)
        conn.commit()
    with open("results/compression_chunks.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(f"experiment_start_CAT={start.isoformat(timespec='seconds')} cutoff_CAT={cutoff.isoformat()} rows={sum(r['rows_loaded'] for r in rows)}")
    conn.close()


if __name__=="__main__": main()
