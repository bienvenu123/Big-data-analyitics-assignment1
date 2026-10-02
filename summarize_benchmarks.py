"""Compare saved interval timings and compression improvements."""
from __future__ import annotations

import csv
from pathlib import Path


def read(path):return list(csv.DictReader(open(path,encoding="utf-8",newline="")))
def write(path,rows):
    if not rows:return
    with open(path,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    Path("results").mkdir(exist_ok=True)
    interval=read("results/chunk_interval_benchmark_summary.csv")
    by={(r["table"],r["query"]):float(r["median_ms"]) for r in interval}
    base="energy_readings";out=[]
    for q in sorted({r["query"] for r in interval}):
        med={t:by[(t,q)] for t in ("energy_readings","energy_readings_3h","energy_readings_week")}
        fastest=min(med,key=med.get)
        out.append({"query":q,"fastest_table":fastest,"fastest_median_ms":med[fastest],
          "one_day_median_ms":med[base],"three_hour_median_ms":med["energy_readings_3h"],
          "one_week_median_ms":med["energy_readings_week"],
          "three_hour_improvement_vs_day_pct":100*(med[base]-med["energy_readings_3h"])/med[base],
          "week_improvement_vs_day_pct":100*(med[base]-med["energy_readings_week"])/med[base]})
    write("results/chunk_interval_comparison.csv",out)
    rows=read("results/compression_benchmark_summary.csv")
    by={(r["table"],r["query"]):float(r["median_ms"]) for r in rows}
    base="energy_readings";out=[]
    for q in sorted({r["query"] for r in rows}):
        b=by[(base,q)]
        for table,strategy in (("energy_time_compressed","time"),("energy_meter_compressed","meter")):
            comp=by[(table,q)]
            out.append({"query":q,"strategy":strategy,"baseline_table":base,"baseline_median_ms":b,
              "compressed_table":table,"compressed_median_ms":comp,
              "improvement_pct":100*(b-comp)/b})
    write("results/compression_query_improvements.csv",out)
    print("Chunk interval comparison:")
    for r in read("results/chunk_interval_comparison.csv"):print(r)
    print("Compression query improvements:")
    for r in read("results/compression_query_improvements.csv"):print(r)


if __name__=="__main__":main()
