"""Reproducible ingestion utilities for Assignment I.

Requires psycopg (v3) and paho-mqtt. Credentials come from PG* and MQTT_* env vars.
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

import smart_meter_simulator as sim

CAT_TZ = ZoneInfo("Africa/Johannesburg")


def cat_now():
    return datetime.now(CAT_TZ).isoformat(timespec="milliseconds")

READING_COLUMNS = ("meter_id", "event_time", "received_time", "power_kw", "voltage_v",
                   "current_a", "frequency_hz", "energy_kwh")
INSERT_READINGS = "INSERT INTO {table} (" + ",".join(READING_COLUMNS) + ") VALUES (" + ",".join(["%s"] * 8) + ")"


def pg_connect():
    conn = psycopg.connect(os.getenv("DATABASE_URL", ""), row_factory=dict_row)
    conn.execute("SET TIME ZONE 'Africa/Kigali'")
    return conn


def load_meters():
    with pg_connect() as conn, conn.cursor() as cur:
        cur.executemany("""INSERT INTO meters(meter_id,region,customer_type,base_power_kw,power_factor)
          VALUES (%(meter_id)s,%(region)s,%(customer_type)s,%(base_power_kw)s,%(power_factor)s)
          ON CONFLICT(meter_id) DO UPDATE SET region=EXCLUDED.region,
          customer_type=EXCLUDED.customer_type,base_power_kw=EXCLUDED.base_power_kw,
          power_factor=EXCLUDED.power_factor""", sim.meter_metadata())
        cur.execute("SELECT count(*) AS n FROM meters")
        print(f"meters={cur.fetchone()['n']}")


def batches(iterable, size):
    it = iter(iterable)
    while batch := list(itertools.islice(it, size)):
        yield batch


def capture(table="energy_readings", batch_size=10000):
    if table not in {"energy_readings", "energy_live"}:
        raise ValueError("unsupported target table")
    expected = sim.dataset_info()["expected_counts"]["emitted_readings"]
    started = time.perf_counter()
    started_cat = cat_now()
    first_write = None
    count = 0
    with pg_connect() as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table}")
        for batch in batches(sim.iter_readings(), batch_size):
            if first_write is None:
                first_write = time.perf_counter()
            with cur.copy(f"COPY {table} ({','.join(READING_COLUMNS)}) FROM STDIN") as copy:
                for row in batch:
                    copy.write_row(tuple(row[c] for c in READING_COLUMNS))
            count += len(batch)
            conn.commit()
            elapsed = time.perf_counter() - started
            print(f"consumed={count:,}/{expected:,} elapsed={elapsed:.1f}s", flush=True)
        cur.execute(f"SELECT count(*) AS n FROM {table}")
        stored = cur.fetchone()["n"]
    finished = time.perf_counter()
    summary={"route":"direct PostgreSQL COPY","machine":__import__("platform").node(),
             "start_CAT":started_cat,"end_CAT":cat_now(),"consumed":count,"stored":stored,"expected":expected,
             "total_seconds":round(finished-started,3),
             "write_seconds":round(finished-(first_write or finished),3)}
    Path("results").mkdir(exist_ok=True)
    Path("results/capture_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))
    if count != expected or stored != expected:
        raise SystemExit("count mismatch: inspect database and rerun after correcting pipeline")


def pilot():
    import paho.mqtt.client as mqtt

    total = 2000
    started_cat = cat_now()
    started = time.perf_counter()
    received = 0
    acknowledged = 0
    ready = threading.Event()
    pub_done = threading.Event()
    lock = threading.Lock()
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")

    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="assignment-subscriber")
    if username:
        sub.username_pw_set(username, password)

    def on_connect(client, userdata, flags, reason, properties):
        if reason == 0:
            client.subscribe("energy/meters/#", qos=1)
            ready.set()
        else:
            print(f"subscriber connect error: {reason}", file=sys.stderr)

    # Empty pilot table before connecting the subscriber, then keep one DB
    # connection for the callback loop instead of opening one per publication.
    with pg_connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE energy_live")
    sub_conn = pg_connect()
    sub_cur = sub_conn.cursor()

    def on_message(client, userdata, message):
        nonlocal received
        try:
            row = json.loads(message.payload)
            sub_cur.execute(INSERT_READINGS.format(table="energy_live"), tuple(row[c] for c in READING_COLUMNS))
            with lock:
                received += 1
                if received % 100 == 0:
                    sub_conn.commit()
        except Exception as exc:
            sub_conn.rollback()
            print(f"subscriber insert/parse failure: {exc}", file=sys.stderr, flush=True)

    sub.on_connect, sub.on_message = on_connect, on_message
    sub.connect(host, port, 60)
    sub.loop_start()
    if not ready.wait(15):
        raise RuntimeError("subscriber did not connect")

    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="assignment-publisher")
    if username:
        pub.username_pw_set(username, password)
    pub.connect(host, port, 60)
    pub.loop_start()
    try:
        for row in itertools.islice(sim.iter_readings(), total):
            topic = f"energy/meters/{row['meter_id']}"
            info = pub.publish(topic, json.dumps(row, separators=(",", ":")), qos=1, retain=False)
            info.wait_for_publish()
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"publish failed: {info.rc}")
            acknowledged += 1
        pub_done.set()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and received < total:
            time.sleep(0.2)
        sub_conn.commit()
        with pg_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM energy_live")
            stored = cur.fetchone()["n"]
        summary={"start_CAT":started_cat,"end_CAT":cat_now(),"elapsed_seconds":round(time.perf_counter()-started,3),
                 "generated":total,"acknowledged":acknowledged,"received":received,"stored":stored,
                 "qos":1,"retain":False}
        Path("results").mkdir(exist_ok=True)
        Path("results/pilot_counts.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print(json.dumps(summary))
        if (acknowledged, received, stored) != (total, total, total):
            raise SystemExit("pilot count mismatch; inspect subscriber logs")
    finally:
        pub.disconnect(); pub.loop_stop()
        sub.disconnect(); sub.loop_stop()
        sub_cur.close(); sub_conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["meters", "capture", "pilot"])
    parser.add_argument("--table", default="energy_readings")
    parser.add_argument("--batch-size", type=int, default=10000)
    args = parser.parse_args()
    {"meters": load_meters, "capture": lambda: capture(args.table, args.batch_size), "pilot": pilot}[args.command]()
