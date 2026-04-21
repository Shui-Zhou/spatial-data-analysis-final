# Step 2 Official Summary

Run completed on 2026-04-03 for the official-data rerun of the baseline OLS.

## Model Specification

- Dependent variable: `Prop_Count`
- Predictors: unchanged from the accepted baseline
- Accessibility term:
  `tube_station_distance_km`, now populated from the official TfL rapid-transit
  station-complex layer

## Main Results

- Observations used: `4,486`
- `R^2 = 0.3886`
- `Adjusted R^2 = 0.3873`
- Maximum predictor VIF: `7.675`

## Significant Predictors (p < 0.05)

- Positive:
  - `Value`
  - `Health Dep`
  - `Crime Scor`
  - `Barriers t`
  - `Living Env`
- Negative:
  - `Income Sco`
  - `Employment`
  - `distance_to_centre_km`

## Not Statistically Significant In This Specification

- `Education,`
- `tube_station_distance_km` (`coef = -0.1861`, `p = 0.3920`)

## Interpretation

Replacing OSM with the official TfL source does **not** materially change the
baseline global OLS story. The main global results remain stable, which is a
good sign for robustness, while the data-source credibility is stronger.
