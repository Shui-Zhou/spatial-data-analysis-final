# Spatial Data Analysis Coursework (7CUSMSDA)

Final submission for the MSc Urban Informatics Spatial Data Analysis coursework, King's College London.

Shui Zhou (K25120780), 2025-26.

## Layout

- `Analysis/step1_eda_official_tfl.py` — EDA and external-variable integration (distance to centre, nearest TfL rapid-transit station)
- `Analysis/step2_ols_baseline.py` — global OLS baseline regression on the Airbnb listing-count field
- `Analysis/step3_spatial_autocorrelation.py` — Queen contiguity weights, global Moran's I, LISA on OLS residuals
- `Analysis/step4_gwr_models.py` — GWR with adaptive bisquare kernel; raw-count and log-transformed specifications
- `Analysis/step5_spatial_regression_robustness.py` — Spatial Lag and Spatial Error models as robustness checks
- `Analysis/create_supporting_tables.py` — regenerates summary tables consumed by the report
- `Analysis/outputs/` — per-step figures, tables, JSON summaries, and the OFFICIAL_SOURCE_EVALUATION / SUPPORTING_TABLES summaries
- `report/CW2_Draft.md` — main report markdown source
- `report/CW2_Appendix.md` — code appendix markdown source
- `report/K25120780_7CUSMSDA_Coursework.pdf` — main report submission PDF (Turnitin portal 1)
- `report/K25120780_7CUSMSDA_Appendix.pdf` — appendix submission PDF (Turnitin portal 2)
- `report/CW2_Final_Report_with_Appendix.pdf` — merged local-reference copy (not submitted)
- `report/assets/` — figures and tables embedded in the report
- `report/export_report.sh` — rebuilds the PDFs via pandoc + headless Chrome + pypdf

## Reproducing

### Scripts

Run from the project root, in order. Steps 2-5 read the enriched LSOA layer saved by Step 1.

```bash
python3 Analysis/step1_eda_official_tfl.py
python3 Analysis/step2_ols_baseline.py
python3 Analysis/step3_spatial_autocorrelation.py
python3 Analysis/step4_gwr_models.py
python3 Analysis/step5_spatial_regression_robustness.py
python3 Analysis/create_supporting_tables.py
```

All outputs land under `Analysis/outputs/step*_official/`. The large intermediate `.gpkg` files are gitignored and regenerated on each run.

### Report

```bash
bash report/export_report.sh
```

Requires pandoc, Google Chrome, and pypdf. Produces the main report, appendix, and merged PDFs plus DOCX/HTML intermediates.

## Data

The primary LSOA shapefile (`lsoa_IMD_airbnb_housing.shp`, 4,486 Greater London LSOAs in EPSG:27700) and the course reference notebooks are distributed through the module's Weekly Resources and are not redistributed here. Step 1 also pulls TfL rapid-transit StopPoint data from the Transport for London Unified API (Tube, DLR, Overground, Elizabeth line; 385 station complexes after hub-level deduplication); an internet connection is required on first run.

Place the LSOA shapefile at `data/lsoa_IMD_airbnb_housing.shp` (path referenced in `step1_eda_official_tfl.py`) before running the scripts.

## Dependencies

Python 3.10+. See `requirements.txt`. The `mgwr` and `spreg` stack is most easily installed in a conda environment (`mscui2026`).
