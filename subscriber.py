"""Standalone QoS 1 pilot subscriber writing JSON readings to energy_live."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

import psycopg
import paho.mqtt.client as mqtt

COLS=("meter_id","event_time","received_time","power_kw","voltage_v","current_a","frequency_hz","energy_kwh")


def main(limit,truncate):
    host=os.getenv("MQTT_HOST","localhost");port=int(os.getenv("MQTT_PORT","1883"))
    username=os.getenv("MQTT_USERNAME");password=os.getenv("MQTT_PASSWORD")
    pg=psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-subscriber")
    pg.execute("SET TIME ZONE 'Africa/Kigali'")
    with pg.cursor() as cur:
        if truncate:cur.execute("TRUNCATE energy_live")
    pg.commit();cur=pg.cursor();started=time.perf_counter();received=0;ready=threading.Event();done=threading.Event()
    sub=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="assignment-subscriber")
    if username:sub.username_pw_set(username,password)
    def on_connect(client,userdata,flags,reason,properties):
        if reason==0:client.subscribe("energy/meters/#",qos=1);ready.set()
        else:print(f"connect failed: {reason}",flush=True)
    def on_message(client,userdata,message):
        nonlocal received
        try:
            row=json.loads(message.payload)
            cur.execute("INSERT INTO energy_live ("+",".join(COLS)+") VALUES ("+",".join(["%s"]*8)+")",tuple(row[c] for c in COLS))
            received+=1
            if received%100==0 or received>=limit:pg.commit()
            if received>=limit:done.set()
        except Exception as exc:
            pg.rollback();print(f"parse/insert error: {exc}",flush=True)
    sub.on_connect=on_connect;sub.on_message=on_message;sub.connect(host,port,60);sub.loop_start()
    try:
        if not ready.wait(15):raise TimeoutError("subscriber did not connect")
        if not done.wait(120):raise TimeoutError(f"received only {received}/{limit}")
        with psycopg.connect(os.getenv("DATABASE_URL","")) as check:
            stored=check.execute("SELECT count(*) FROM energy_live").fetchone()[0]
        summary={"received":received,"stored":stored,"expected":limit,"elapsed_seconds":round(time.perf_counter()-started,3)}
        Path("results").mkdir(exist_ok=True);Path("results/subscriber_counts.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print(json.dumps(summary))
        if received!=limit or stored!=limit:raise SystemExit("subscriber count mismatch")
    finally:
        sub.disconnect();sub.loop_stop();cur.close();pg.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--limit",type=int,default=2000);p.add_argument("--truncate",action="store_true")
    a=p.parse_args();main(a.limit,a.truncate)
