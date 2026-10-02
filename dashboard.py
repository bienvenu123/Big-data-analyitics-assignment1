"""Raw and aggregate dashboard for assignment Sections 7.1–7.3.

Start with `python dashboard.py`; no query-result cache is enabled.
"""
from __future__ import annotations

import os
from datetime import date,datetime,time,timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import psycopg
from dash import Dash,Input,Output,dcc,html

CAT=ZoneInfo("Africa/Johannesburg")
START_DEFAULT="2026-09-22"
END_DEFAULT="2026-09-28"
METER_DEFAULT=1000000000


def bounds(start,end):
    start_date=date.fromisoformat(start);end_date=date.fromisoformat(end)
    begin=datetime.combine(start_date,time.min,CAT)
    finish=datetime.combine(end_date+timedelta(days=1),time.min,CAT)
    return begin,finish,(finish-begin).days


def query(sql,params):
    with psycopg.connect(os.getenv("DATABASE_URL",""),application_name="Assignment-I-dashboard") as conn:
        conn.execute("SET TIME ZONE 'Africa/Kigali'")
        with conn.cursor() as cur:
            cur.execute(sql,params); rows=cur.fetchall(); cols=[c.name for c in cur.description]
    return pd.DataFrame(rows,columns=cols)


def figures(mode,start,end,meter):
    begin,finish,days=bounds(start,end)
    if mode=="raw":
        hourly=query("""SELECT time_bucket(INTERVAL '1 hour',r.event_time) AS bucket,m.region,SUM(r.energy_kwh) AS energy_kwh
          FROM energy_readings r JOIN meters m USING(meter_id) WHERE r.event_time >= %s AND r.event_time < %s
          GROUP BY 1,2 ORDER BY 1,2""",(begin,finish))
        daily=query("""SELECT event_time::date AS bucket,SUM(energy_kwh) AS energy_kwh FROM energy_readings
          WHERE event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(begin,finish))
        weekly=query("""SELECT date_bin(INTERVAL '7 days',event_time,TIMESTAMPTZ '2026-09-01 00:00:00+02') AS bucket,
          SUM(energy_kwh) AS energy_kwh FROM energy_readings WHERE event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(begin,finish))
        meter_daily=query("""SELECT event_time::date AS bucket,SUM(energy_kwh) AS energy_kwh FROM energy_readings
          WHERE meter_id=%s AND event_time >= %s AND event_time < %s GROUP BY 1 ORDER BY 1""",(meter,begin,finish))
        comp=query("""WITH reg AS(SELECT region,COUNT(*) AS registered FROM meters GROUP BY region),
          obs AS(SELECT m.region,COUNT(DISTINCT(r.meter_id,r.event_time)) FILTER(WHERE r.meter_id IS NOT NULL) AS observed FROM meters m
          LEFT JOIN energy_readings r ON r.meter_id=m.meter_id AND r.event_time >= %s AND r.event_time < %s GROUP BY m.region)
          SELECT reg.region,100.0*COALESCE(obs.observed,0)/(reg.registered*%s*96) AS completeness_pct
          FROM reg JOIN obs USING(region) ORDER BY reg.region""",(begin,finish,days))
    else:
        hourly=query("""SELECT bucket,region,energy_kwh FROM energy_hour_region
          WHERE bucket >= %s AND bucket < %s ORDER BY bucket,region""",(begin,finish))
        daily=query("""SELECT bucket::date AS bucket,SUM(energy_kwh) AS energy_kwh FROM energy_15m_region
          WHERE bucket >= %s AND bucket < %s GROUP BY 1 ORDER BY 1""",(begin,finish))
        weekly=query("""SELECT date_bin(INTERVAL '7 days',bucket,TIMESTAMPTZ '2026-09-01 00:00:00+02') AS bucket,
          SUM(energy_kwh) AS energy_kwh FROM energy_15m_region WHERE bucket >= %s AND bucket < %s GROUP BY 1 ORDER BY 1""",(begin,finish))
        meter_daily=query("""SELECT bucket,energy_kwh FROM energy_day_meter
          WHERE meter_id=%s AND bucket >= %s AND bucket < %s ORDER BY bucket""",(meter,begin,finish))
        comp=query("""WITH reg AS(SELECT region,COUNT(*) AS registered FROM meters GROUP BY region),
          obs AS(SELECT region,SUM(reading_count) AS observed FROM energy_15m_region
          WHERE bucket >= %s AND bucket < %s GROUP BY region)
          SELECT reg.region,100.0*COALESCE(obs.observed,0)/(reg.registered*%s*96) AS completeness_pct
          FROM reg LEFT JOIN obs USING(region) ORDER BY reg.region""",(begin,finish,days))
    figs=[
      px.line(hourly,x="bucket",y="energy_kwh",color="region",title="Hourly regional energy",labels={"bucket":"CAT hour","energy_kwh":"Energy (kWh)"}),
      px.bar(daily,x="bucket",y="energy_kwh",title="Daily network energy",labels={"bucket":"CAT day","energy_kwh":"Energy (kWh)"}),
      px.bar(weekly,x="bucket",y="energy_kwh",title="Seven-day network energy",labels={"bucket":"CAT period start","energy_kwh":"Energy (kWh)"}),
      px.line(meter_daily,x="bucket",y="energy_kwh",title=f"Daily meter {meter}",labels={"bucket":"CAT day","energy_kwh":"Energy (kWh)"}),
      px.bar(comp,x="region",y="completeness_pct",title="Regional completeness",labels={"region":"Region","completeness_pct":"Completeness (%)"}),
    ]
    return figs


def dashboard(mode):
    p=mode
    return html.Div([
      html.H2("Raw" if mode=="raw" else "Aggregate"),
      html.Div([html.Label("Whole CAT days"),dcc.DatePickerRange(id=f"{p}-dates",start_date=START_DEFAULT,end_date=END_DEFAULT,
        min_date_allowed="2026-09-01",max_date_allowed="2026-09-28",display_format="YYYY-MM-DD"),
        html.Label("Meter"),dcc.Input(id=f"{p}-meter",type="number",value=METER_DEFAULT,min=1000000000,max=1000003999,step=1)],
        style={"display":"flex","gap":"18px","alignItems":"center","padding":"14px"}),
      html.Div([dcc.Graph(id=f"{p}-panel-{i}",config={"displaylogo":False}) for i in range(1,6)],
        style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"12px"})
    ])


app=Dash(__name__,suppress_callback_exceptions=True,title="Smart Energy Grid Analytics")
app.layout=html.Div([
 html.H1("Smart Energy Grid Analytics",style={"margin":"16px"}),
 dcc.Tabs(id="dashboard-tabs",value="raw",children=[
   dcc.Tab(label="Raw",value="raw",children=[dashboard("raw")]),
   dcc.Tab(label="Aggregate",value="aggregate",children=[dashboard("aggregate")])
 ])
],style={"fontFamily":"Arial,sans-serif","maxWidth":"1500px","margin":"auto"})


def register(mode):
    @app.callback([Output(f"{mode}-panel-{i}","figure") for i in range(1,6)],
       Input(f"{mode}-dates","start_date"),Input(f"{mode}-dates","end_date"),Input(f"{mode}-meter","value"))
    def update(start,end,meter):
        if not start or not end:return [{}]*5
        return figures(mode,start,end,int(meter or METER_DEFAULT))

register("raw");register("aggregate")

if __name__=="__main__":
    app.run(host=os.getenv("DASH_HOST","127.0.0.1"),port=int(os.getenv("DASH_PORT","8050")),debug=False)
