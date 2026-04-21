# Step 1 Official Summary

Run completed on 2026-04-03 for the official-data replacement of CW2 Step 1.

## What Was Produced

- Enriched LSOA dataset:
  `Analysis/outputs/step1_official/data/lsoa_step1_enriched_official.gpkg`
- Official TfL station-complex points:
  `Analysis/outputs/step1_official/data/tfl_rapid_transit_station_points.gpkg`
- Summary JSON:
  `Analysis/outputs/step1_official/data/step1_official_summary.json`
- Correlation table:
  `Analysis/outputs/step1_official/data/prop_count_correlations_official.csv`

## Key Results

- Main dataset loaded successfully: `4,486` LSOAs in `EPSG:27700`.
- Official station source: TfL Unified API StopPoint endpoint.
- Source counts:
  - Raw TfL stop points returned: `2,639`
  - Stop points inside the London study boundary: `2,342`
  - Station complexes after hub-first deduplication: `385`
- The official accessibility measure is the nearest TfL rapid-transit station
  complex covering Tube, DLR, Overground, and Elizabeth line.
- For downstream compatibility, `tube_station_distance_km` is retained as an
  alias of this official rapid-transit distance.
- `Prop_Count` correlation with the new official accessibility variable:
  `-0.281`

## Important Method Note

The column `Number of` is still identical to `Prop_Count`, so the dependent
variable remains unstandardized in the official-data rerun as well.

## Recommended Next Step

Proceed with the official-data rerun of Steps 2-5 using
`lsoa_step1_enriched_official.gpkg` as the primary input while keeping the old
OSM outputs untouched.
