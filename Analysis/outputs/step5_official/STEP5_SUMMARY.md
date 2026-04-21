# Step 5 Official Summary

Run completed on 2026-04-03 for the official-data rerun of the Spatial Lag and
Spatial Error robustness checks.

## Main Results

### OLS baseline reference

- `R^2 = 0.3886`
- `AIC = 40591.166`
- `BIC = 40661.662`

### Spatial Lag model

- Pseudo `R^2 = 0.7015`
- `AIC = 38025.5387`
- `Schwarz = 38102.4433`
- `rho = 0.7147` (`p < 0.001`)

### Spatial Error model

- Pseudo `R^2 = 0.3658`
- `AIC = 38032.3542`
- `Schwarz = 38102.8501`
- `lambda = 0.7331` (`p < 0.001`)

## Variable Pattern Note

- `distance_to_centre_km` remains clearly negative and significant.
- `tube_station_distance_km` remains non-significant in both global spatial
  models:
  - Spatial Lag: `p = 0.8332`
  - Spatial Error: `p = 0.3751`

## Interpretation

The official-data rerun leaves the Step 5 conclusion unchanged. Global spatial
dependence is strong, but the accessibility variable still looks much more like
a locally varying relationship than a strong global average effect.
