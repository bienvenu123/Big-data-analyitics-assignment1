"""Standalone QoS 1 pilot publisher for the first 2,000 generator readings."""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from pathlib import Path

import paho.mqtt.client as mqtt

import smart_meter_simulator as sim


def main(limit):
    host=os.getenv("MQTT_HOST","localhost");port=int(os.getenv("MQTT_PORT","1883"))
    username=os.getenv("MQTT_USERNAME");password=os.getenv("MQTT_PASSWORD")
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="assignment-publisher")
    if username:client.username_pw_set(username,password)
    client.connect(host,port,60);client.loop_start();started=time.perf_counter();generated=acknowledged=0
    try:
        for row in itertools.islice(sim.iter_readings(),limit):
            msg=client.publish(f"energy/meters/{row['meter_id']}",json.dumps(row,separators=(",",":")),qos=1,retain=False)
            msg.wait_for_publish()
            if msg.rc!=mqtt.MQTT_ERR_SUCCESS:raise RuntimeError(f"publish failed with code {msg.rc}")
            generated+=1;acknowledged+=1
        summary={"generated":generated,"acknowledged":acknowledged,"expected":limit,"elapsed_seconds":round(time.perf_counter()-started,3),"qos":1,"retain":False}
        Path("results").mkdir(exist_ok=True);Path("results/publisher_counts.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print(json.dumps(summary))
        if generated!=limit or acknowledged!=limit:raise SystemExit("publisher count mismatch")
    finally:client.disconnect();client.loop_stop()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--limit",type=int,default=2000)
    main(p.parse_args().limit)
