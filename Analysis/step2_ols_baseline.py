from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
DATA_PATH = Path(
    os.environ.get(
        "STEP1_DATA_PATH",
        str(BASE_DIR / "Analysis/outputs/step1_official/data/lsoa_step1_enriched_official.gpkg"),
    )
)
OUTPUT_DIR = Path(
    os.environ.get("STEP2_OUTPUT_DIR", str(BASE_DIR / "Analysis/outputs/step2_official"))
)
FIG_DIR = OUTPUT_DIR / "figures"
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
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_data() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PATH)
    missing = [col for col in [DV_COLUMN, *PREDICTORS] if col not in gdf.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
    return gdf


def prepare_model_frame(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    model_df = gdf[[DV_COLUMN, *PREDICTORS]].copy()
    for col in model_df.columns:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")
    return model_df.dropna().reset_index(drop=True)


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    X_const = sm.add_constant(X)
    rows = []
    for i, col in enumerate(X_const.columns):
        rows.append(
            {
                "variable": col,
                "vif": variance_inflation_factor(X_const.values, i),
            }
        )
    return pd.DataFrame(rows)


def fit_model(model_df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    X = sm.add_constant(model_df[PREDICTORS])
    y = model_df[DV_COLUMN]
    return sm.OLS(y, X).fit()


def plot_observed_vs_fitted(model_df: pd.DataFrame, model) -> None:
    fitted = model.fittedvalues
    observed = model_df[DV_COLUMN]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(fitted, observed, alpha=0.35, color="#176087", s=18)
    min_val = min(fitted.min(), observed.min())
    max_val = max(fitted.max(), observed.max())
    ax.plot([min_val, max_val], [min_val, max_val], linestyle="--", color="#B22222")
    ax.set_title("Observed vs fitted Airbnb property counts")
    ax.set_xlabel("Fitted values")
    ax.set_ylabel("Observed values")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "observed_vs_fitted.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_residuals(model) -> None:
    residuals = model.resid
    fitted = model.fittedvalues

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.histplot(residuals, bins=40, kde=True, ax=ax, color="#2A6F97")
    ax.set_title("OLS residual distribution")
    ax.set_xlabel("Residual")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "residual_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(fitted, residuals, alpha=0.35, color="#176087", s=18)
    ax.axhline(0, linestyle="--", color="#B22222")
    ax.set_title("Residuals vs fitted values")
    ax.set_xlabel("Fitted values")
    ax.set_ylabel("Residual")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "residuals_vs_fitted.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_outputs(model_df: pd.DataFrame, model, vif_df: pd.DataFrame) -> dict:
    coef_df = pd.DataFrame(
        {
            "variable": model.params.index,
            "coefficient": model.params.values,
            "std_error": model.bse.values,
            "t_value": model.tvalues.values,
            "p_value": model.pvalues.values,
        }
    )
    coef_df.to_csv(DATA_DIR / "ols_coefficients.csv", index=False)
    vif_df.to_csv(DATA_DIR / "ols_vif.csv", index=False)
    model_df.corr(numeric_only=True).round(3).to_csv(DATA_DIR / "model_correlation_matrix.csv")

    (DATA_DIR / "ols_summary.txt").write_text(model.summary().as_text(), encoding="utf-8")

    summary = {
        "n_obs": int(model.nobs),
        "dependent_variable": DV_COLUMN,
        "predictors": PREDICTORS,
        "r_squared": round(float(model.rsquared), 4),
        "adj_r_squared": round(float(model.rsquared_adj), 4),
        "aic": round(float(model.aic), 3),
        "bic": round(float(model.bic), 3),
        "f_statistic": round(float(model.fvalue), 3),
        "f_pvalue": round(float(model.f_pvalue), 6),
        "max_vif_excluding_constant": round(
            float(vif_df.loc[vif_df["variable"] != "const", "vif"].max()), 3
        ),
        "significant_predictors_p_lt_0_05": coef_df.loc[
            (coef_df["variable"] != "const") & (coef_df["p_value"] < 0.05), "variable"
        ].tolist(),
        "excluded_variables_note": (
            "`Small Host` and `Multiple L` were excluded because they sum exactly "
            "to `Prop_Count`, which would create target leakage."
        ),
        "standardization_note": (
            "The dependent variable remains raw `Prop_Count` because no valid "
            "housing-stock denominator is available in the current dataset."
        ),
    }
    with open(DATA_DIR / "ols_summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main() -> None:
    ensure_dirs()
    sns.set_theme(style="whitegrid")

    gdf = load_data()
    model_df = prepare_model_frame(gdf)
    vif_df = compute_vif(model_df[PREDICTORS])
    model = fit_model(model_df)

    plot_observed_vs_fitted(model_df, model)
    plot_residuals(model)
    summary = save_outputs(model_df, model, vif_df)

    print(json.dumps(summary, indent=2))
    print(f"Saved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
