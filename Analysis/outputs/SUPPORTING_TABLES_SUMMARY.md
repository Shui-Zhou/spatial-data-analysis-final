# Supporting Tables Summary

Generated for report support after the switch to the official TfL analysis chain.

## Task A

- Purpose: legacy OSM robustness check retained for audit trail only.
- Output: `Analysis/outputs/step2/data/ols_all_stations_robustness.csv`
- `station_distance_km` coefficient: -2.064987
- `station_distance_km` p-value: 0.003924

## Task B

- Purpose: primary report comparison table based on the official TfL rerun.
- Output: `Analysis/outputs/model_comparison_table.csv`
- GWR significance entries are reported as local significance shares using adjusted critical t values.
- OLS and Spatial Lag significance entries are reported as global p-value flags (`sig` / `ns`).