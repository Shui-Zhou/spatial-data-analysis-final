from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import esda
import geopandas as gpd
import libpysal as lps
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm


BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
DATA_PATH = Path(
    os.environ.get(
        "STEP1_DATA_PATH",
        str(BASE_DIR / "Analysis/outputs/step1_official/data/lsoa_step1_enriched_official.gpkg"),
    )
)
OUTPUT_DIR = Path(
    os.environ.get("STEP3_OUTPUT_DIR", str(BASE_DIR / "Analysis/outputs/step3_official"))
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

CLUSTER_LABELS = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
CLUSTER_COLORS = {
    "Not Significant": "#D9D9D9",
    "HH": "#B2182B",
    "LH": "#2166AC",
    "LL": "#67A9CF",
    "HL": "#EF8A62",
}
RANDOM_SEED = 12345


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_model_frame() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    gdf = gpd.read_file(DATA_PATH)
    model_df = gdf[[DV_COLUMN, *PREDICTORS]].copy()
    for col in model_df.columns:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")
    valid = model_df.notna().all(axis=1)
    return gdf.loc[valid].copy().reset_index(drop=True), model_df.loc[valid].reset_index(drop=True)


def fit_baseline_ols(model_df: pd.DataFrame):
    X = sm.add_constant(model_df[PREDICTORS])
    y = model_df[DV_COLUMN]
    return sm.OLS(y, X).fit()


def make_weights(gdf: gpd.GeoDataFrame):
    w = lps.weights.Queen.from_dataframe(gdf, use_index=False)
    w.transform = "r"
    return w


def add_residual_outputs(gdf: gpd.GeoDataFrame, model, w) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["ols_fitted"] = model.fittedvalues.values
    gdf["ols_residual"] = model.resid.values
    gdf["ols_residual_std"] = (
        (gdf["ols_residual"] - gdf["ols_residual"].mean()) / gdf["ols_residual"].std()
    )
    gdf["residual_spatial_lag"] = lps.weights.lag_spatial(w, gdf["ols_residual_std"])
    return gdf


def compute_global_moran(gdf: gpd.GeoDataFrame, w):
    np.random.seed(RANDOM_SEED)
    return esda.Moran(gdf["ols_residual"].values, w, permutations=999)


def compute_lisa(gdf: gpd.GeoDataFrame, w):
    np.random.seed(RANDOM_SEED)
    lisa = esda.Moran_Local(gdf["ols_residual"].values, w, permutations=999)
    sig = lisa.p_sim < 0.05
    labels = []
    for is_sig, quad in zip(sig, lisa.q):
        if not is_sig:
            labels.append("Not Significant")
        else:
            labels.append(CLUSTER_LABELS.get(int(quad), "Not Significant"))
    gdf = gdf.copy()
    gdf["lisa_local_i"] = lisa.Is
    gdf["lisa_pvalue"] = lisa.p_sim
    gdf["lisa_quadrant"] = lisa.q
    gdf["lisa_cluster"] = labels
    return lisa, gdf


def plot_residual_choropleth(gdf: gpd.GeoDataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 10))
    gdf.plot(
        column="ols_residual",
        scheme="Quantiles",
        k=5,
        cmap="RdBu_r",
        linewidth=0.05,
        edgecolor="white",
        legend=True,
        ax=ax,
    )
    ax.set_title("OLS residuals by LSOA (quantiles)")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ols_residual_choropleth_quantiles.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_moran_scatter(gdf: gpd.GeoDataFrame, moran) -> None:
    x = gdf["ols_residual_std"]
    y = gdf["residual_spatial_lag"]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(x, y, s=14, alpha=0.35, color="#176087")
    slope = moran.I
    intercept = y.mean() - slope * x.mean()
    line_x = np.linspace(x.min(), x.max(), 100)
    ax.plot(line_x, intercept + slope * line_x, color="#B2182B")
    ax.axhline(y.mean(), linestyle="--", color="grey")
    ax.axvline(x.mean(), linestyle="--", color="grey")
    ax.text(x.quantile(0.8), y.quantile(0.85), f"I = {moran.I:.3f}", fontsize=12)
    ax.set_title("Moran scatterplot for OLS residuals")
    ax.set_xlabel("Standardized residual")
    ax.set_ylabel("Spatial lag of standardized residual")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "moran_scatter_ols_residuals.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_lisa_clusters(gdf: gpd.GeoDataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 10))
    for label, color in CLUSTER_COLORS.items():
        subset = gdf[gdf["lisa_cluster"] == label]
        if subset.empty:
            continue
        subset.plot(color=color, linewidth=0.05, edgecolor="white", ax=ax, label=label)
    ax.set_title("LISA cluster map of OLS residuals")
    ax.set_axis_off()
    handles = [
        Patch(facecolor=color, edgecolor="none", label=label)
        for label, color in CLUSTER_COLORS.items()
        if (gdf["lisa_cluster"] == label).any()
    ]
    ax.legend(handles=handles, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "lisa_cluster_map_ols_residuals.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_local_i_distribution(gdf: gpd.GeoDataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(gdf["lisa_local_i"], bins=40, kde=True, ax=ax, color="#2A6F97")
    ax.set_title("Distribution of local Moran's I values")
    ax.set_xlabel("Local Moran's I")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "local_moran_i_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_outputs(gdf: gpd.GeoDataFrame, moran, lisa, w) -> dict:
    cluster_counts = gdf["lisa_cluster"].value_counts().to_dict()
    significant_count = int((gdf["lisa_pvalue"] < 0.05).sum())

    gdf[
        [
            "LSOA21CD",
            "LSOA name",
            DV_COLUMN,
            "ols_fitted",
            "ols_residual",
            "ols_residual_std",
            "residual_spatial_lag",
            "lisa_local_i",
            "lisa_pvalue",
            "lisa_quadrant",
            "lisa_cluster",
            "geometry",
        ]
    ].to_file(DATA_DIR / "lsoa_step3_residual_diagnostics.gpkg", driver="GPKG")

    pd.DataFrame(
        {
            "metric": ["moran_i", "expected_i", "z_score", "p_sim", "permutations", "n_obs"],
            "value": [
                moran.I,
                moran.EI,
                moran.z_sim,
                moran.p_sim,
                lisa.permutations,
                len(gdf),
            ],
        }
    ).to_csv(DATA_DIR / "global_moran_summary.csv", index=False)

    gdf[["LSOA21CD", "LSOA name", "lisa_cluster", "lisa_pvalue", "lisa_local_i"]].to_csv(
        DATA_DIR / "lisa_results.csv", index=False
    )

    summary = {
        "n_obs": int(len(gdf)),
        "queen_weights_n": int(w.n),
        "queen_weights_islands": int(len(w.islands)),
        "global_moran_i": round(float(moran.I), 4),
        "expected_i": round(float(moran.EI), 4),
        "z_score": round(float(moran.z_sim), 4),
        "p_value_sim": round(float(moran.p_sim), 6),
        "significant_lisa_count": significant_count,
        "significant_lisa_share": round(significant_count / len(gdf), 4),
        "cluster_counts": {k: int(v) for k, v in cluster_counts.items()},
        "interpretation_note": (
            "Positive and significant Moran's I on OLS residuals indicates that the "
            "baseline global model leaves spatial structure unexplained."
        ),
    }
    with open(DATA_DIR / "step3_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main() -> None:
    ensure_dirs()
    sns.set_theme(style="whitegrid")

    gdf, model_df = load_model_frame()
    model = fit_baseline_ols(model_df)
    w = make_weights(gdf)
    gdf = add_residual_outputs(gdf, model, w)
    moran = compute_global_moran(gdf, w)
    lisa, gdf = compute_lisa(gdf, w)

    plot_residual_choropleth(gdf)
    plot_moran_scatter(gdf, moran)
    plot_lisa_clusters(gdf)
    plot_local_i_distribution(gdf)
    summary = save_outputs(gdf, moran, lisa, w)

    print(json.dumps(summary, indent=2))
    print(f"Saved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
