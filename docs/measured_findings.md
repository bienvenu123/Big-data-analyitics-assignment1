# Measured findings for the report

## Data quality and cleaning

- Pre-clean: 10,696,848 emitted rows; 10,643,735 unique meter/time pairs; 53,113 exact extra copies; 213,090 delayed unique rows; 108,265 missing pairs; no conflicting duplicate payload groups.
- Missing rate 1.006929%; duplicate rate 0.499007%; delayed rate 2.002023%; completeness 98.993071%.
- The conflict-checked cleanup removed 53,113 rows and left 10,643,735 unique pairs. The before/after energy sums are in `results/cleaning_summary.csv`.
- The five highest missing-meter counts are in `results/top_five_missing_meters.csv`.

## Demand and reporting

- Weekly network energy rose across the four periods: 934,199.061 kWh, 953,714.972 kWh, 973,230.026 kWh, and 992,560.288 kWh, beginning 1, 8, 15 and 22 September CAT.
- The top 15-minute network demand interval was 28 September 2026 at 13:00 CAT, 7,993.691 kW. The next two were 12:45 and 13:15 CAT at 7,943.947 and 7,943.636 kW.
- Industrial customers used 5,469.636 kWh per registered meter, versus 817.302 for commercial and 312.522 for residential meters. Each region has 400 registered meters; Region 8 was highest at 1,258.690 kWh per meter and Region 4 lowest at 811.011 kWh per meter.
- Whole-network completeness was 98.993071%. Region completeness ranged from 98.969308% (Region 6) to 99.012928% (Region 8).
- For 21 September, 149,400.545 kWh had arrived by 00:00 on 22 September; the finalized total was 149,552.723 kWh. The 152.178 kWh difference was 0.101756% of the final daily total.
- The weekly decline on weekends and rise across the period reflect the generator's customer load shapes and daily trend; power is demand in kW, while energy in kWh accumulates consumption over time.

## Anomalies

The rule compares each reading with that meter's median at the same CAT hour and weekday. It flags ratios at least 2.3 or at most 0.10. The ordinary generated multiplier is 0.85–1.15, while injected events multiply load by 2.8 or 0.03, so these thresholds leave margin around normal variation while covering both injected extremes. It detected 40/40 labeled intervals. There were 0 false flags among 10,643,261 observed readings outside injected intervals and 0/4,000 meters affected by a false flag. Labels were used only after flagging for evaluation.

## Forecast

The random forest (`n_estimators=300`, `min_samples_leaf=3`, `max_features=0.9`, seed 42) had the lowest validation MAE (4.679 kWh; validation RMSE 6.109 kWh) in the 15 October run. Training used 1,680 rows after excluding 1,680 of 3,360 training rows lacking the selected 168-hour lookback. Validation and test each contained 1,680 rows. The latest saved test MAE/RMSE are 5.133/7.147 kWh, versus 42.708/79.403 kWh for the previous-day baseline. Missing hourly predictors were imputed from training-only medians; absent target hours remain absent. See `results/regional_peak_errors.csv` for each region's peak-hour errors.

## Limitations

The recorded full-load elapsed duration is 117.47 seconds, with 117.257 seconds from first write through final count, but the successful regeneration did not retain exact CAT start/end timestamps. `pipeline.py` now records those timestamps for future runs. Windows also reported an unsynchronized clock; resynchronization was denied in this session, so CAT timestamps need to be re-recorded after an administrator sync. The dashboard backend and its numerical data were verified, but the available in-app browser list was empty, so browser-render timing and required screenshots were not captured. The report still needs group names/student IDs/contributions and evidence images. The host physical storage media type also needs manual confirmation.
