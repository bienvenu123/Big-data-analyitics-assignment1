"""Save actual EXPLAIN plans with buffer statistics for Q5 per table."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from benchmark import QUERIES, TABLES


def main(tables):
    out=Path("results/plans");out.mkdir(parents=True,exist_ok=True)
    conn=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-explain")
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    with conn:
      with conn.cursor() as cur:
       for table in tables:
        if table not in TABLES: raise ValueError(table)
        cur.execute("EXPLAIN (ANALYZE,BUFFERS,VERBOSE,FORMAT TEXT) "+QUERIES["Q5"].format(table=table))
        plan="\n".join(row[0] for row in cur.fetchall())
        (out/f"{table}_Q5.txt").write_text(plan+"\n",encoding="utf-8")
        print(f"saved {out/f'{table}_Q5.txt'}")
    conn.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--tables",nargs="+",default=TABLES[:3])
    main(parser.parse_args().tables)
