# Step 4 Official Summary

Run completed on 2026-04-03 for the official-data rerun of the GWR models.

## Main Performance Results

### Raw-count GWR

- Bandwidth: `156`
- `R^2 = 0.7970`
- `Adjusted R^2 = 0.7585`
- `AICc = 7281.8536`

### Log-DV GWR

- Bandwidth: `286`
- `R^2 = 0.8018`
- `Adjusted R^2 = 0.7822`
- `AICc = 6357.0665`

## Local Significance Highlights

Using the adjusted critical t values reported by GWR:

### Raw-count GWR

- `distance_to_centre_km`: locally significant in `20.89%` of LSOAs
- `Crime Scor`: locally significant in `19.73%`
- `tube_station_distance_km`: locally significant in `7.60%`

### Log-DV GWR

- `distance_to_centre_km`: locally significant in `69.82%` of LSOAs
- `Crime Scor`: locally significant in `63.69%`
- `tube_station_distance_km`: locally significant in `17.30%`

## Interpretation

- The official-data rerun still strongly favors GWR over the global OLS.
- The log-DV sensitivity model remains the stronger specification on fit and
  parsimony.
- The official accessibility variable remains weak in the global OLS but shows
  clearer local significance in GWR, especially in the log-DV model. That keeps
  the core interpretation intact: accessibility effects are spatially uneven
  rather than globally uniform.
- Post-GWR residual Moran's I shows that local modelling substantially reduces
  residual spatial dependence but does not remove it completely:
  - raw-count GWR residual Moran's I = `0.0668`
  - log-DV GWR residual Moran's I = `0.0777`
  - both are much smaller than the OLS residual Moran's I of `0.5562`
