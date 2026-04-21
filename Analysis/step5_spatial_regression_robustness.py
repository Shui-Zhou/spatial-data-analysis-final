from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import geopandas as gpd
import libpysal as lps
import numpy as np
import pandas as pd
from libpysal.weights import Queen
from spreg import ML_Error, ML_Lag, OLS


BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
DATA_PATH = Path(
    os.environ.get(
        "STEP1_DATA_PATH",
        str(BASE_DIR / "Analysis/outputs/step1_official/data/lsoa_step1_enriched_official.gpkg"),
    )
)
STEP2_METRICS_PATH = Path(
    os.environ.get(
        "STEP2_METRICS_PATH",
        str(BASE_DIR / "Analysis/outputs/step2_official/data/ols_summary_metrics.json"),
    )
)
OUTPUT_DIR = Path(
    os.environ.get("STEP5_OUTPUT_DIR", str(BASE_DIR / "Analysis/outputs/step5_official"))
)
DATA_DIR = OUTPUT_DIR / "data"

DV_COLUMN = "Prop_Count"
PREDICTORS = [
    "Value",
    "Income Sco",
    "Employment",
    "Education,",
    "Health Dep",
    "Crime Scor",
    "Barriers t",
    "Living Env",
    "distance_to_centre_km",
    "tube_station_distance_km",
]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_data() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PATH)
    keep = ["LSOA21CD", "LSOA name", "geometry", DV_COLUMN, *PREDICTORS]
    gdf = gdf[keep].copy()
    for col in [DV_COLUMN, *PREDICTORS]:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce")
    return gdf.dropna().reset_index(drop=True)


def build_design(gdf: gpd.GeoDataFrame):
    y = gdf[DV_COLUMN].to_numpy(dtype=float).reshape((-1, 1))
    X = gdf[PREDICTORS].to_numpy(dtype=float)
    w = Queen.from_dataframe(gdf, use_index=False)
    w.transform = "r"
    return y, X, w


def fit_models(y, X, w):
    ols = OLS(y, X, name_y=DV_COLUMN, name_x=PREDICTORS, name_w="queen_w", name_ds="step5")
    lag = ML_Lag(y, X, w, name_y=DV_COLUMN, name_x=PREDICTORS, name_w="queen_w", name_ds="step5")
    err = ML_Error(y, X, w, name_y=DV_COLUMN, name_x=PREDICTORS, name_w="queen_w", name_ds="step5")
    return ols, lag, err


def save_summary_text(model, filename: str) -> None:
    (DATA_DIR / filename).write_text(str(model.summary), encoding="utf-8")


def get_metric(model, attr: str):
    value = getattr(model, attr, None)
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return float(value.ravel()[0])
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    return value


def coefficient_table(model, model_name: str) -> pd.DataFrame:
    names = ["Intercept", *PREDICTORS]
    if model_name == "spatial_lag":
        names = [*names, "rho"]
    elif model_name == "spatial_error":
        names = [*names, "lambda"]

    betas = np.array(model.betas).reshape(-1)
    z_stat = getattr(model, "z_stat", [])
    rows = []
    for i, beta in enumerate(betas):
        p_val = None
        z_val = None
        if i < len(z_stat):
            z_val = float(z_stat[i][0])
            p_val = float(z_stat[i][1])
        rows.append(
            {
                "variable": names[i] if i < len(names) else f"beta_{i}",
                "coefficient": float(beta),
                "z_or_t_stat": z_val,
                "p_value": p_val,
            }
        )
    return pd.DataFrame(rows)


def build_metrics(ols, lag, err) -> dict:
    step2_metrics = json.loads(STEP2_METRICS_PATH.read_text())

    def metrics_for(model, label: str):
        return {
            "model": label,
            "n_obs": int(model.n),
            "pseudo_r2_or_r2": round(float(get_metric(model, "pr2") or get_metric(model, "r2")), 4),
            "aic": round(float(get_metric(model, "aic")), 4) if get_metric(model, "aic") is not None else None,
            "bic_or_schwarz": round(float(get_metric(model, "schwarz")), 4)
            if get_metric(model, "schwarz") is not None
            else None,
            "log_likelihood": round(float(get_metric(model, "logll")), 4)
            if get_metric(model, "logll") is not None
            else None,
        }

    summary = {
        "ols_baseline": {
            "r2": step2_metrics["r_squared"],
            "adj_r2": step2_metrics["adj_r_squared"],
            "aic": step2_metrics["aic"],
            "bic": step2_metrics["bic"],
        },
        "spatial_lag": metrics_for(lag, "spatial_lag"),
        "spatial_error": metrics_for(err, "spatial_error"),
        "lag_parameter_rho": round(float(np.array(lag.rho).ravel()[0]), 4),
        "error_parameter_lambda": round(float(np.array(err.lam).ravel()[0]), 4),
        "note": (
            "Spatial Lag and Spatial Error are treated as robustness checks for the "
            "global specification, not replacements for the project's main GWR analysis."
        ),
    }
    return summary


def main() -> None:
    ensure_dirs()
    gdf = load_data()
    y, X, w = build_design(gdf)
    ols, lag, err = fit_models(y, X, w)

    save_summary_text(ols, "ols_spreg_summary.txt")
    save_summary_text(lag, "spatial_lag_summary.txt")
    save_summary_text(err, "spatial_error_summary.txt")

    coefficient_table(lag, "spatial_lag").to_csv(DATA_DIR / "spatial_lag_coefficients.csv", index=False)
    coefficient_table(err, "spatial_error").to_csv(DATA_DIR / "spatial_error_coefficients.csv", index=False)

    metrics = build_metrics(ols, lag, err)
    with open(DATA_DIR / "step5_summary.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Saved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
