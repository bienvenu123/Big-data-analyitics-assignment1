"""Chronological offline forecast experiment; reads the cleaned DB table."""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import psycopg
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from joblib import dump

OUT = Path("results")
OUT.mkdir(exist_ok=True)


def main():
    with psycopg.connect(os.getenv("DATABASE_URL", "")) as conn:
        df = pd.read_sql("""SELECT date_trunc('hour',r.event_time) AS target_time,
                   m.region,SUM(r.energy_kwh) AS actual_kwh,COUNT(*) AS reading_count
                   FROM energy_readings r JOIN meters m USING(meter_id)
                   GROUP BY 1,2 ORDER BY 1,2""", conn)
    df["target_time"] = pd.to_datetime(df.target_time, utc=True).dt.tz_convert("Africa/Johannesburg")
    df = df.set_index(["target_time", "region"]).sort_index()
    # Complete region-hour grid: absent targets remain NaN; absent predictor values
    # are imputed from training data only by each sklearn pipeline.
    times = pd.date_range("2026-09-01", "2026-09-29", freq="h", inclusive="left", tz="Africa/Johannesburg")
    regions = sorted(df.index.get_level_values("region").unique())
    full = pd.MultiIndex.from_product([times, regions], names=["target_time", "region"])
    df = df.reindex(full).reset_index()
    observed = df.dropna(subset=["actual_kwh"]).copy()
    observed["origin"] = observed.target_time.dt.normalize()
    observed["hour"] = observed.target_time.dt.hour
    observed["dow"] = observed.target_time.dt.dayofweek
    observed["day_of_year"] = observed.target_time.dt.dayofyear
    observed["lag_24_source_time"] = observed.target_time - pd.Timedelta(hours=24)
    observed["lag_168_source_time"] = observed.target_time - pd.Timedelta(hours=168)
    if not ((observed.lag_24_source_time < observed.origin).all() and
            (observed.lag_168_source_time < observed.origin).all()):
        raise RuntimeError("a lag source is not before its daily forecast origin")
    lookup = df.set_index(["target_time", "region"])["actual_kwh"]
    observed["lag_24h"] = [lookup.get((t-pd.Timedelta(hours=24),r), float("nan")) for t,r in zip(observed.target_time,observed.region)]
    observed["lag_168h"] = [lookup.get((t-pd.Timedelta(hours=168),r), float("nan")) for t,r in zip(observed.target_time,observed.region)]
    # Mean of seven matching hours from prior weeks; every source precedes that day's origin.
    observed["prior_week_same_hour_mean"] = [
        pd.to_numeric(pd.Series([lookup.get((t-pd.Timedelta(hours=24+168*k),r),float("nan")) for k in range(7)]),errors="coerce").mean()
        for t,r in zip(observed.target_time,observed.region)]
    observed["split"] = "excluded"
    observed.loc[observed.target_time.dt.date.between(pd.Timestamp("2026-09-01").date(),pd.Timestamp("2026-09-14").date()),"split"]="train"
    observed.loc[observed.target_time.dt.date.between(pd.Timestamp("2026-09-15").date(),pd.Timestamp("2026-09-21").date()),"split"]="validation"
    observed.loc[observed.target_time.dt.date.between(pd.Timestamp("2026-09-22").date(),pd.Timestamp("2026-09-28").date()),"split"]="test"
    features=["region","hour","dow","day_of_year","lag_24h","lag_168h","prior_week_same_hour_mean"]
    # Use one shared complete-case training set across both configurations.
    train_all=observed[observed.split=="train"].copy()
    train=train_all[train_all.lag_168h.notna()].copy()
    valid=observed[observed.split=="validation"].copy()
    test=observed[observed.split=="test"].copy()
    categorical=["region"]
    numeric=[f for f in features if f not in categorical]
    prep=ColumnTransformer([("region",OneHotEncoder(handle_unknown="ignore"),categorical),
                            ("numeric",SimpleImputer(strategy="median",add_indicator=True),numeric)])
    candidates={
      "HGB_depth3":HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=7,l2_regularization=1.0,random_state=42),
      "RF_300":RandomForestRegressor(n_estimators=300,min_samples_leaf=3,max_features=0.9,n_jobs=-1,random_state=42),
    }
    scores=[]; fitted={}
    for name,est in candidates.items():
        model=make_pipeline(prep,est)
        model.fit(train[features],train.actual_kwh)
        pred=model.predict(valid[features])
        scores.append({"configuration":name,"train_rows":len(train),"validation_rows":len(valid),
                       "validation_MAE_kWh":mean_absolute_error(valid.actual_kwh,pred),
                       "validation_RMSE_kWh":mean_squared_error(valid.actual_kwh,pred)**0.5})
        fitted[name]=model
    scores=pd.DataFrame(scores).sort_values("validation_MAE_kWh")
    scores.to_csv(OUT/"validation_scores.csv",index=False)
    best=scores.iloc[0].configuration
    chosen=fitted[best]
    dump(chosen,OUT/"selected_forecast_model.joblib")
    (OUT/"selected_forecast_model.txt").write_text(
      f"configuration={best}\nfeatures={features}\ntraining_rows={len(train)}\nvalidation_rows={len(valid)}\n",
      encoding="utf-8")
    pred=chosen.predict(test[features])
    test["model_prediction_kwh"]=pred
    test["baseline_prediction_kwh"]=test.lag_24h
    # Baseline defined as prior-day matching hour. A missing prior-day target is left
    # missing and counted, never silently replaced with zero.
    test["baseline_error"]=test.baseline_prediction_kwh-test.actual_kwh
    test["model_error"]=test.model_prediction_kwh-test.actual_kwh
    test.to_csv(OUT/"test_predictions.csv",index=False)
    example_cols=["target_time","region","origin","lag_24_source_time","lag_24h",
                  "lag_168_source_time","lag_168h","prior_week_same_hour_mean"]
    observed[example_cols].head(30).to_csv(OUT/"forecast_feature_examples.csv",index=False)
    pd.DataFrame([
      {"feature":"region","lag_hours":"none","earliest_data_target":"2026-09-01"},
      {"feature":"hour","lag_hours":"none","earliest_data_target":"2026-09-01"},
      {"feature":"dow","lag_hours":"none","earliest_data_target":"2026-09-01"},
      {"feature":"day_of_year","lag_hours":"none","earliest_data_target":"2026-09-01"},
      {"feature":"lag_24h","lag_hours":24,"earliest_data_target":"2026-09-02"},
      {"feature":"lag_168h","lag_hours":168,"earliest_data_target":"2026-09-08"},
      {"feature":"prior_week_same_hour_mean","lag_hours":"24, 192, 360, 528, 696, 864, 1032","earliest_data_target":"2026-09-02"},
    ]).to_csv(OUT/"forecast_feature_catalog.csv",index=False)
    peak_rows=[]
    for region,group in test.groupby("region"):
        peak=group.sort_values("target_time").loc[group.actual_kwh.idxmax()]
        peak_rows.append({"region":region,"peak_time_CAT":peak.target_time.isoformat(),
          "actual_kwh":peak.actual_kwh,"baseline_prediction_kwh":peak.baseline_prediction_kwh,
          "baseline_abs_error_kwh":abs(peak.baseline_error),
          "model_prediction_kwh":peak.model_prediction_kwh,
          "model_abs_error_kwh":abs(peak.model_error)})
    pd.DataFrame(peak_rows).sort_values("region").to_csv(OUT/"regional_peak_errors.csv",index=False)
    plot_data=test[test.region==regions[0]].sort_values("target_time")
    fig,ax=plt.subplots(figsize=(12,5))
    ax.plot(plot_data.target_time,plot_data.actual_kwh,label="Actual",linewidth=1.8)
    ax.plot(plot_data.target_time,plot_data.baseline_prediction_kwh,label="Previous-day baseline",alpha=.8)
    ax.plot(plot_data.target_time,plot_data.model_prediction_kwh,label=best,alpha=.8)
    ax.set(title=f"{regions[0]}: seven test days",ylabel="Energy (kWh)",xlabel="CAT hour")
    ax.legend();fig.tight_layout();fig.savefig(OUT/"forecast_test_plot.png",dpi=160);plt.close(fig)
    def metrics(g):
        return pd.Series({"n":g.actual_kwh.notna().sum(),
          "baseline_MAE_kWh":mean_absolute_error(g.actual_kwh,g.baseline_prediction_kwh),
          "baseline_RMSE_kWh":mean_squared_error(g.actual_kwh,g.baseline_prediction_kwh)**0.5,
          "model_MAE_kWh":mean_absolute_error(g.actual_kwh,g.model_prediction_kwh),
          "model_RMSE_kWh":mean_squared_error(g.actual_kwh,g.model_prediction_kwh)**0.5})
    metrics(test).to_frame("all_regions").T.to_csv(OUT/"test_metrics.csv",index=False)
    test.groupby("region").apply(metrics,include_groups=False).to_csv(OUT/"region_metrics.csv")
    print(f"selected={best}; train={len(train)} validation={len(valid)} test={len(test)}")
    print(f"train_before_lookback={len(train_all)} excluded={len(train_all)-len(train)} retained={len(train)}; earliest_feature_usable=2026-09-08 00:00 CAT")
    print(f"prediction_count={len(test)}; baseline_nonnull={test.baseline_prediction_kwh.notna().sum()}")
    print("lag_source_check=passed; every 24h and 168h lag source precedes the CAT daily forecast origin")
    print(scores.to_string(index=False))
    print("Predictions and metrics saved under results/.")


if __name__ == "__main__":
    main()
