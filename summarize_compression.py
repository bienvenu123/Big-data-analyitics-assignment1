"""Create the Section 4 storage ratio/cost/coverage summary from DB and logs."""
from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg


def main():
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-compression-summary")
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    with conn:
      with conn.cursor() as cur:
       cur.execute("SELECT COUNT(*) FROM energy_readings");baseline_rows=cur.fetchone()[0]
       data={}
       for table in ["energy_readings","energy_time_compressed","energy_meter_compressed"]:
        cur.execute("SELECT table_bytes,index_bytes,toast_bytes,total_bytes FROM hypertable_detailed_size(%s::regclass)",(table,))
        tb,ib,tob,total=cur.fetchone()
        cur.execute("SELECT COUNT(*),COUNT(DISTINCT meter_id),MIN(event_time),MAX(event_time),SUM(power_kw),SUM(energy_kwh) FROM "+table)
        n,meters,first,last,sum_kw,sum_kwh=cur.fetchone()
        cur.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE is_compressed) FROM timescaledb_information.chunks WHERE hypertable_name=%s",(table,))
        chunks,compressed=cur.fetchone()
        data[table]={"rows":n,"meters":meters,"chunks":chunks,"compressed_chunks":compressed,
                     "data_bytes":tb+tob,"index_bytes":ib,"total_bytes":total,
                     "first_event":first,"last_event":last,"sum_kw":sum_kw,"sum_kwh":sum_kwh}
       baseline=data["energy_readings"]
       range_sets={}
       for table in ("energy_time_compressed","energy_meter_compressed"):
        cur.execute("SELECT range_start,range_end,is_compressed FROM timescaledb_information.chunks WHERE hypertable_name=%s ORDER BY range_start",(table,))
        range_sets[table]=cur.fetchall()
       if [(r[0],r[1],r[2]) for r in range_sets["energy_time_compressed"]] != [(r[0],r[1],r[2]) for r in range_sets["energy_meter_compressed"]]:
        raise RuntimeError("compressed chunk ranges/status differ between layouts")
       if any(not r[2] for r in range_sets["energy_time_compressed"]): raise RuntimeError("time-only layout has uncompressed chunks")
    logs=list(csv.DictReader(open("results/compression_chunks.csv",encoding="utf-8",newline="")))
    result=[]
    base=data["energy_readings"]
    for table,strategy in (("energy_time_compressed","time"),("energy_meter_compressed","meter")):
        entries=[r for r in logs if r["table"]==table]
        cost=sum(float(r["compression_seconds"]) for r in entries)
        compressed_rows=sum(int(r["rows_loaded"]) for r in entries if float(r["compression_seconds"])>0)
        cur_data=data[table]
        if (cur_data["rows"]!=baseline_rows or cur_data["meters"]!=base["meters"] or
            cur_data["first_event"]!=base["first_event"] or cur_data["last_event"]!=base["last_event"] or
            abs(cur_data["sum_kw"]-base["sum_kw"])>0.001 or abs(cur_data["sum_kwh"]-base["sum_kwh"])>0.001):
            raise RuntimeError(f"data mismatch in {table}")
        result.append({"strategy":strategy,"table":table,"baseline_data_bytes":base["data_bytes"],
          "baseline_index_bytes":base["index_bytes"],"baseline_total_bytes":base["total_bytes"],
          "data_bytes":cur_data["data_bytes"],"index_bytes":cur_data["index_bytes"],"total_bytes":cur_data["total_bytes"],
          "compression_ratio":base["total_bytes"]/cur_data["total_bytes"],
          "saved_pct":100*(base["total_bytes"]-cur_data["total_bytes"])/base["total_bytes"],
          "compression_seconds":cost,"compressed_chunks":cur_data["compressed_chunks"],"total_chunks":cur_data["chunks"],
          "compressed_rows":compressed_rows,"total_rows":baseline_rows,"row_pct":100*compressed_rows/baseline_rows})
    with open("results/compression_storage_summary.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    with open("results/compressed_chunk_ranges.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["range_start","range_end","time_compressed","meter_compressed"]);w.writeheader()
        for t,m in zip(range_sets["energy_time_compressed"],range_sets["energy_meter_compressed"]):
            w.writerow({"range_start":t[0].isoformat(),"range_end":t[1].isoformat(),"time_compressed":t[2],"meter_compressed":m[2]})
    for r in result:print(r)
    conn.close()


if __name__=="__main__":main()
