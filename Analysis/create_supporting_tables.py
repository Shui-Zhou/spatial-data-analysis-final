from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t


BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
LEGACY_STEP1_GPKG = Path(
    os.environ.get(
        "LEGACY_STEP1_GPKG",
        str(BASE_DIR / "Analysis/outputs/step1/data/lsoa_step1_enriched.gpkg"),
    )
)
LEGACY_STEP2_DIR = Path(
    os.environ.get(
        "LEGACY_STEP2_DIR",
        str(BASE_DIR / "Analysis/outputs/step2/data"),
    )
)
PRIMARY_STEP2_DIR = Path(
    os.environ.get(
        "PRIMARY_STEP2_DIR",
        str(BASE_DIR / "Analysis/outputs/step2_official/data"),
    )
)
PRIMARY_STEP4_DIR = Path(
    os.environ.get(
        "PRIMARY_STEP4_DIR",
        str(BASE_DIR / "Analysis/outputs/step4_official/data"),
    )
)
PRIMARY_STEP5_DIR = Path(
    os.environ.get(
        "PRIMARY_STEP5_DIR",
        str(BASE_DIR / "Analysis/outputs/step5_official/data"),
    )
)
OUTPUT_DIR = Path(
    os.environ.get(
        "SUPPORTING_OUTPUT_DIR",
        str(BASE_DIR / "Analysis/outputs"),
    )
)
PRIMARY_TABLE_FILENAME = os.environ.get(
    "PRIMARY_MODEL_TABLE_FILENAME",
    "model_comparison_table.csv",
)

DV = "Prop_Count"
BASE_PREDICTORS = [
    "Value",
    "Income Sco",
    "Employment",
    "Education,",
    "Health Dep",
    "Crime Scor",
    "Barriers t",
    "Living Env",
    "distance_to_centre_km",
]
TUBE_PREDICTOR = "tube_station_distance_km"
ALL_STATION_PREDICTOR = "station_distance_km"
KEY_VARS = ["Value", "Income Sco", "Crime Scor", "distance_to_centre_km", "tube_station_distance_km"]

GWR_PARAMETER_COUNT = len(BASE_PREDICTORS) + 2


def load_legacy_enriched_data() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(LEGACY_STEP1_GPKG)
    return gdf


def run_all_station_robustness(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    predictors = [*BASE_PREDICTORS, ALL_STATION_PREDICTOR]
    cols = [DV, *predictors]
    model_df = gdf[cols].copy()
    for col in cols:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")
    model_df = model_df.dropna().reset_index(drop=True)

    X = sm.add_constant(model_df[predictors])
    y = model_df[DV]
    model = sm.OLS(y, X).fit()

    coef_df = pd.DataFrame(
        {
            "variable": model.params.index,
            "coef": model.params.values,
            "p_value": model.pvalues.values,
        }
    )
    coef_df.to_csv(LEGACY_STEP2_DIR / "ols_all_stations_robustness.csv", index=False)
    return coef_df


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def sig_flag_from_p(df: pd.DataFrame, variable: str) -> str:
    row = df.loc[df["variable"] == variable]
    if row.empty:
        return "NA"
    return "global sig." if float(row["p_value"].iloc[0]) < 0.05 else "n.s."


def gwr_critical_t(metrics: dict) -> float:
    adjusted_alpha_95 = (0.05 * GWR_PARAMETER_COUNT) / float(metrics["enp"])
    return float(t.ppf(1 - (adjusted_alpha_95 / 2.0), int(metrics["n_obs"]) - 1))


def local_sig_share(gpkg_path: Path, dv_name: str, variable: str, critical_t: float) -> str:
    gdf = gpd.read_file(gpkg_path)
    safe = (
        variable.lower()
        .replace(" ", "_")
        .replace(",", "")
        .replace("-", "_")
    )
    t_col = f"{dv_name}_t_{safe}"
    share = float((gdf[t_col].abs() > critical_t).mean())
    return f"{share:.1%} sig."


def build_comparison_table() -> pd.DataFrame:
    step2_metrics = load_json(PRIMARY_STEP2_DIR / "ols_summary_metrics.json")
    step2_coefs = load_csv(PRIMARY_STEP2_DIR / "ols_coefficients.csv")
    step4_raw = load_json(PRIMARY_STEP4_DIR / "gwr_Prop_Count_metrics.json")
    step4_log = load_json(PRIMARY_STEP4_DIR / "gwr_log_prop_count_metrics.json")
    step5_metrics = load_json(PRIMARY_STEP5_DIR / "step5_summary.json")
    step5_lag = load_csv(PRIMARY_STEP5_DIR / "spatial_lag_coefficients.csv")

    raw_critical_t = gwr_critical_t(step4_raw)
    log_critical_t = gwr_critical_t(step4_log)

    rows = [
        {
            "model": "OLS baseline",
            "r2": step2_metrics["r_squared"],
            "adj_r2": step2_metrics["adj_r_squared"],
            "aicc": "",
            "aic": step2_metrics["aic"],
            "Value_sig": sig_flag_from_p(step2_coefs, "Value"),
            "Income_Sco_sig": sig_flag_from_p(step2_coefs, "Income Sco"),
            "Crime_Scor_sig": sig_flag_from_p(step2_coefs, "Crime Scor"),
            "distance_to_centre_sig": sig_flag_from_p(step2_coefs, "distance_to_centre_km"),
            "tube_station_distance_sig": sig_flag_from_p(step2_coefs, "tube_station_distance_km"),
        },
        {
            "model": "GWR raw",
            "r2": step4_raw["r2"],
            "adj_r2": step4_raw["adj_r2"],
            "aicc": step4_raw["aicc"],
            "aic": step4_raw["aic"],
            "Value_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_Prop_Count_results.gpkg",
                "Prop_Count",
                "Value",
                raw_critical_t,
            ),
            "Income_Sco_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_Prop_Count_results.gpkg",
                "Prop_Count",
                "Income Sco",
                raw_critical_t,
            ),
            "Crime_Scor_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_Prop_Count_results.gpkg",
                "Prop_Count",
                "Crime Scor",
                raw_critical_t,
            ),
            "distance_to_centre_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_Prop_Count_results.gpkg",
                "Prop_Count",
                "distance_to_centre_km",
                raw_critical_t,
            ),
            "tube_station_distance_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_Prop_Count_results.gpkg",
                "Prop_Count",
                "tube_station_distance_km",
                raw_critical_t,
            ),
        },
        {
            "model": "GWR log",
            "r2": step4_log["r2"],
            "adj_r2": step4_log["adj_r2"],
            "aicc": step4_log["aicc"],
            "aic": step4_log["aic"],
            "Value_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_log_prop_count_results.gpkg",
                "log_prop_count",
                "Value",
                log_critical_t,
            ),
            "Income_Sco_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_log_prop_count_results.gpkg",
                "log_prop_count",
                "Income Sco",
                log_critical_t,
            ),
            "Crime_Scor_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_log_prop_count_results.gpkg",
                "log_prop_count",
                "Crime Scor",
                log_critical_t,
            ),
            "distance_to_centre_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_log_prop_count_results.gpkg",
                "log_prop_count",
                "distance_to_centre_km",
                log_critical_t,
            ),
            "tube_station_distance_sig": local_sig_share(
                PRIMARY_STEP4_DIR / "gwr_log_prop_count_results.gpkg",
                "log_prop_count",
                "tube_station_distance_km",
                log_critical_t,
            ),
        },
        {
            "model": "Spatial Lag",
            "r2": step5_metrics["spatial_lag"]["pseudo_r2_or_r2"],
            "adj_r2": "",
            "aicc": "",
            "aic": step5_metrics["spatial_lag"]["aic"],
            "Value_sig": sig_flag_from_p(step5_lag, "Value"),
            "Income_Sco_sig": sig_flag_from_p(step5_lag, "Income Sco"),
            "Crime_Scor_sig": sig_flag_from_p(step5_lag, "Crime Scor"),
            "distance_to_centre_sig": sig_flag_from_p(step5_lag, "distance_to_centre_km"),
            "tube_station_distance_sig": sig_flag_from_p(step5_lag, "tube_station_distance_km"),
        },
    ]

    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT_DIR / PRIMARY_TABLE_FILENAME, index=False)
    return table


def write_summary(robustness_df: pd.DataFrame, comparison_df: pd.DataFrame) -> None:
    station_row = robustness_df.loc[robustness_df["variable"] == ALL_STATION_PREDICTOR]
    coef = float(station_row["coef"].iloc[0]) if not station_row.empty else None
    p_val = float(station_row["p_value"].iloc[0]) if not station_row.empty else None

    lines = [
        "# Supporting Tables Summary",
        "",
        "Generated for report support after the switch to the official TfL analysis chain.",
        "",
        "## Task A",
        "",
        "- Purpose: legacy OSM robustness check retained for audit trail only.",
        "- Output: `Analysis/outputs/step2/data/ols_all_stations_robustness.csv`",
        f"- `station_distance_km` coefficient: {coef:.6f}" if coef is not None else "- `station_distance_km` coefficient: NA",
        f"- `station_distance_km` p-value: {p_val:.6f}" if p_val is not None else "- `station_distance_km` p-value: NA",
        "",
        "## Task B",
        "",
        "- Purpose: primary report comparison table based on the official TfL rerun.",
        f"- Output: `Analysis/outputs/{PRIMARY_TABLE_FILENAME}`",
        "- GWR significance entries are reported as local significance shares using adjusted critical t values.",
        "- OLS and Spatial Lag significance entries are reported as global p-value flags (`sig` / `ns`).",
    ]
    (OUTPUT_DIR / "SUPPORTING_TABLES_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    gdf = load_legacy_enriched_data()
    robustness_df = run_all_station_robustness(gdf)
    comparison_df = build_comparison_table()
    write_summary(robustness_df, comparison_df)

    print(robustness_df.to_string(index=False))
    print()
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
