from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import esda
import geopandas as gpd
import libpysal as lps
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW


BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
DATA_PATH = Path(
    os.environ.get(
        "STEP1_DATA_PATH",
        str(BASE_DIR / "Analysis/outputs/step1_official/data/lsoa_step1_enriched_official.gpkg"),
    )
)
OUTPUT_DIR = Path(
    os.environ.get("STEP4_OUTPUT_DIR", str(BASE_DIR / "Analysis/outputs/step4_official"))
)
FIG_DIR = OUTPUT_DIR / "figures"
DATA_DIR = OUTPUT_DIR / "data"

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
DV_MAIN = "Prop_Count"
DV_LOG = "log_prop_count"
MAP_VARIABLES = [
    "Value",
    "Income Sco",
    "Crime Scor",
    "distance_to_centre_km",
    "tube_station_distance_km",
]
RANDOM_SEED = 12345


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_data() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PATH)
    keep = ["LSOA21CD", "LSOA name", "geometry", DV_MAIN, *PREDICTORS]
    gdf = gdf[keep].copy()
    for col in [DV_MAIN, *PREDICTORS]:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce")
    gdf = gdf.dropna().reset_index(drop=True)
    gdf[DV_LOG] = np.log1p(gdf[DV_MAIN])
    return gdf


def prepare_design(gdf: gpd.GeoDataFrame, dv_name: str):
    centroids = gdf.geometry.centroid
    coords = np.column_stack([centroids.x.values, centroids.y.values])
    X = gdf[PREDICTORS].to_numpy(dtype=float)
    y = gdf[dv_name].to_numpy(dtype=float).reshape((-1, 1))

    X_s = (X - X.mean(axis=0)) / X.std(axis=0)
    y_s = (y - y.mean(axis=0)) / y.std(axis=0)
    return coords, X_s, y_s


def fit_gwr(gdf: gpd.GeoDataFrame, dv_name: str):
    coords, X_s, y_s = prepare_design(gdf, dv_name)
    np.random.seed(RANDOM_SEED)
    selector = Sel_BW(coords, y_s, X_s, fixed=False, spherical=False)
    bw = selector.search(bw_min=2)
    model = GWR(coords, y_s, X_s, bw, fixed=False, spherical=False)
    results = model.fit()
    return bw, results


def build_results_gdf(gdf: gpd.GeoDataFrame, results, dv_name: str) -> gpd.GeoDataFrame:
    out = gdf[["LSOA21CD", "LSOA name", "geometry"]].copy()
    out[f"{dv_name}_local_r2"] = results.localR2
    out[f"{dv_name}_predy"] = results.predy.flatten()
    out[f"{dv_name}_resid"] = results.resid_response.flatten()

    param_names = ["Intercept", *PREDICTORS]
    for idx, name in enumerate(param_names):
        safe = sanitize_name(name)
        out[f"{dv_name}_coef_{safe}"] = results.params[:, idx]
        out[f"{dv_name}_t_{safe}"] = results.tvalues[:, idx]
    return out


def sanitize_name(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace(",", "")
        .replace("-", "_")
    )


def make_weights(gdf: gpd.GeoDataFrame):
    w = lps.weights.Queen.from_dataframe(gdf, use_index=False)
    w.transform = "r"
    return w


def compute_residual_moran(gdf_out: gpd.GeoDataFrame, dv_name: str, w) -> dict:
    np.random.seed(RANDOM_SEED)
    moran = esda.Moran(gdf_out[f"{dv_name}_resid"].values, w, permutations=999)
    return {
        "dependent_variable": dv_name,
        "moran_i": round(float(moran.I), 4),
        "expected_i": round(float(moran.EI), 4),
        "z_score": round(float(moran.z_sim), 4),
        "p_value_sim": round(float(moran.p_sim), 6),
        "permutations": int(moran.permutations),
    }


def save_model_outputs(gdf_out: gpd.GeoDataFrame, results, dv_name: str, bw: int) -> dict:
    gpkg_path = DATA_DIR / f"gwr_{dv_name}_results.gpkg"
    gdf_out.to_file(gpkg_path, driver="GPKG")

    coef_cols = [col for col in gdf_out.columns if col.startswith(f"{dv_name}_coef_")]
    coef_summary = gdf_out[coef_cols].describe().round(4)
    coef_summary.to_csv(DATA_DIR / f"gwr_{dv_name}_coefficient_summary.csv")

    metrics = {
        "dependent_variable": dv_name,
        "bandwidth": int(bw),
        "n_obs": int(results.n),
        "sigma2": round(float(results.sigma2), 6),
        "aicc": round(float(results.aicc), 4),
        "aic": round(float(results.aic), 4),
        "bic": round(float(results.bic), 4),
        "r2": round(float(results.R2), 4),
        "adj_r2": round(float(results.adj_R2), 4),
        "enp": round(float(results.ENP), 4),
    }
    with open(DATA_DIR / f"gwr_{dv_name}_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    summary_text = str(results.summary())
    (DATA_DIR / f"gwr_{dv_name}_summary.txt").write_text(summary_text, encoding="utf-8")
    return metrics


def plot_local_r2(gdf_out: gpd.GeoDataFrame, dv_name: str) -> None:
    col = f"{dv_name}_local_r2"
    fig, ax = plt.subplots(figsize=(8, 10))
    gdf_out.plot(
        column=col,
        scheme="Quantiles",
        k=5,
        cmap="YlGnBu",
        linewidth=0.05,
        edgecolor="white",
        legend=True,
        ax=ax,
    )
    ax.set_title(f"Local R² for GWR ({dv_name})")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"gwr_{dv_name}_local_r2.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_coefficient_maps(gdf_out: gpd.GeoDataFrame, dv_name: str) -> None:
    for variable in MAP_VARIABLES:
        safe = sanitize_name(variable)
        col = f"{dv_name}_coef_{safe}"
        fig, ax = plt.subplots(figsize=(8, 10))
        gdf_out.plot(
            column=col,
            scheme="Quantiles",
            k=5,
            cmap="RdBu_r",
            linewidth=0.05,
            edgecolor="white",
            legend=True,
            ax=ax,
        )
        ax.set_title(f"GWR local coefficient: {variable} ({dv_name})")
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(
            FIG_DIR / f"gwr_{dv_name}_coef_{safe}.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)


def plot_bandwidth_comparison(metrics_main: dict, metrics_log: dict) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = [metrics_main["dependent_variable"], metrics_log["dependent_variable"]]
    values = [metrics_main["bandwidth"], metrics_log["bandwidth"]]
    ax.bar(labels, values, color=["#176087", "#B56576"])
    ax.set_title("Selected adaptive bandwidths")
    ax.set_ylabel("Bandwidth (nearest neighbours)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "gwr_bandwidth_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_overall_summary(
    metrics_main: dict,
    metrics_log: dict,
    moran_main: dict,
    moran_log: dict,
) -> None:
    overall = {
        "main_model": metrics_main,
        "log_sensitivity_model": metrics_log,
        "gwr_residual_moran": {
            "main_model": moran_main,
            "log_sensitivity_model": moran_log,
        },
        "note": (
            "Both GWR models use standardized X and y, adaptive bandwidth, and "
            "projected centroid coordinates in EPSG:27700."
        ),
    }
    with open(DATA_DIR / "step4_summary.json", "w", encoding="utf-8") as f:
        json.dump(overall, f, indent=2)
    pd.DataFrame([moran_main, moran_log]).to_csv(
        DATA_DIR / "gwr_residual_moran_summary.csv", index=False
    )


def main() -> None:
    ensure_dirs()
    sns.set_theme(style="whitegrid")

    gdf = load_data()
    w = make_weights(gdf)

    bw_main, results_main = fit_gwr(gdf, DV_MAIN)
    gdf_main = build_results_gdf(gdf, results_main, DV_MAIN)
    metrics_main = save_model_outputs(gdf_main, results_main, DV_MAIN, bw_main)
    moran_main = compute_residual_moran(gdf_main, DV_MAIN, w)
    plot_local_r2(gdf_main, DV_MAIN)
    plot_coefficient_maps(gdf_main, DV_MAIN)

    bw_log, results_log = fit_gwr(gdf, DV_LOG)
    gdf_log = build_results_gdf(gdf, results_log, DV_LOG)
    metrics_log = save_model_outputs(gdf_log, results_log, DV_LOG, bw_log)
    moran_log = compute_residual_moran(gdf_log, DV_LOG, w)
    plot_local_r2(gdf_log, DV_LOG)
    plot_coefficient_maps(gdf_log, DV_LOG)

    plot_bandwidth_comparison(metrics_main, metrics_log)
    write_overall_summary(metrics_main, metrics_log, moran_main, moran_log)

    print(
        json.dumps(
            {
                "main_model": metrics_main,
                "log_model": metrics_log,
                "gwr_residual_moran": {
                    "main_model": moran_main,
                    "log_model": moran_log,
                },
            },
            indent=2,
        )
    )
    print(f"Saved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
