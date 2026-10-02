"""Run the assignment's delayed-arrival/materialized-only freshness test."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

CAT=ZoneInfo("Africa/Johannesburg")


def main():
    Path("results").mkdir(exist_ok=True)
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-freshness-test")
    conn.autocommit=True
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    now=datetime.now(CAT);hour_start=now.replace(minute=0,second=0,microsecond=0);H=hour_start-timedelta(hours=1)
    old=H-timedelta(hours=48);old1=old+timedelta(minutes=10);old2=old+timedelta(minutes=25);new1=H+timedelta(minutes=10)
    with conn.cursor() as cur:
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS energy_freshness_hourly")
        cur.execute("DROP TABLE IF EXISTS energy_freshness_test CASCADE")
        cur.execute("CREATE TABLE energy_freshness_test(event_time TIMESTAMPTZ NOT NULL,energy_kwh DOUBLE PRECISION NOT NULL)")
        cur.execute("SELECT create_hypertable('energy_freshness_test','event_time',chunk_time_interval=>INTERVAL '1 day')")
        cur.execute("""CREATE MATERIALIZED VIEW energy_freshness_hourly
             WITH(timescaledb.continuous,timescaledb.materialized_only=true) AS
             SELECT time_bucket(INTERVAL '1 hour',event_time) AS bucket,SUM(energy_kwh) AS energy_kwh,COUNT(*) AS reading_count
             FROM energy_freshness_test GROUP BY bucket WITH NO DATA""")
        cur.execute("INSERT INTO energy_freshness_test VALUES(%s,1.0)",(old1,))
        cur.execute("CALL refresh_continuous_aggregate('energy_freshness_hourly',%s,%s)",(old,old+timedelta(hours=1)))
        records=[]
        def snapshot(stage):
            cur.execute("SELECT bucket,energy_kwh,reading_count FROM energy_freshness_hourly WHERE bucket IN (%s,%s) ORDER BY bucket",(old,H))
            agg={r[0]:r[1:] for r in cur.fetchall()}
            cur.execute("SELECT date_trunc('hour',event_time),SUM(energy_kwh),COUNT(*) FROM energy_freshness_test WHERE event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1",(old, H+timedelta(hours=1)))
            raw={r[0]:r[1:] for r in cur.fetchall()}
            for label,bucket in (("older",old),("H",H)):
                records.append({"stage":stage,"bucket":label,"bucket_start_CAT":bucket.isoformat(),
                   "raw_energy_kwh":raw.get(bucket,(None,None))[0],"raw_rows":raw.get(bucket,(None,None))[1],
                   "aggregate_energy_kwh":agg.get(bucket,(None,None))[0],"aggregate_rows":agg.get(bucket,(None,None))[1]})
        snapshot("after_initial_older_refresh_real_time_off")
        cur.execute("INSERT INTO energy_freshness_test VALUES(%s,0.5),(%s,2.0)",(old2,new1))
        snapshot("after_inserts_real_time_off")
        cur.execute("ALTER MATERIALIZED VIEW energy_freshness_hourly SET(timescaledb.materialized_only=false)")
        snapshot("real_time_on_before_refresh")
        cur.execute("CALL refresh_continuous_aggregate('energy_freshness_hourly',%s,%s)",(old,old+timedelta(hours=1)))
        cur.execute("CALL refresh_continuous_aggregate('energy_freshness_hourly',%s,%s)",(H,H+timedelta(hours=1)))
        snapshot("after_manual_refresh_both_hours")
        cur.execute("ALTER MATERIALIZED VIEW energy_freshness_hourly SET(timescaledb.materialized_only=true)")
    with open("results/freshness_test.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    metadata={"actual_test_time_CAT":now.isoformat(),"most_recent_completed_hour_H_CAT":H.isoformat(),
      "older_hour_H_minus_48h_CAT":old.isoformat(),"insert_times_CAT":[old1.isoformat(),old2.isoformat(),new1.isoformat()]}
    Path("results/freshness_test_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    for r in records: print(r)
    print(metadata)
    conn.close()


if __name__=="__main__":main()
