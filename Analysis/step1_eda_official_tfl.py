from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
from shapely.geometry import Point


BASE_DIR = Path("/Users/joe/Documents/kcl/spatial data analysis")
DATA_PATH = (
    BASE_DIR
    / "Weekly_Resources/Week_07_Regression_Autocorrelation/lsoa_IMD_airbnb_housing.shp"
)
OUTPUT_DIR = BASE_DIR / "Analysis/outputs/step1_official"
FIG_DIR = OUTPUT_DIR / "figures"
DATA_DIR = OUTPUT_DIR / "data"

CHARING_CROSS_EPSG27700 = Point(530028.7469491746, 180380.09425125577)
TFL_API_URL = "https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,overground,elizabeth-line"
TARGET_MODES = ["tube", "dlr", "overground", "elizabeth-line"]

DV_COLUMN = "Prop_Count"


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_lsoa_data() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PATH)
    if gdf.crs is None:
        raise ValueError("Main shapefile has no CRS.")
    if gdf.crs.to_epsg() != 27700:
        gdf = gdf.to_crs(27700)
    return gdf


def add_geometry_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    centroids = gdf.geometry.centroid
    gdf["centroid_x"] = centroids.x
    gdf["centroid_y"] = centroids.y
    gdf["lsoa_area_km2"] = gdf.geometry.area / 1_000_000
    gdf["distance_to_centre_m"] = centroids.distance(CHARING_CROSS_EPSG27700)
    gdf["distance_to_centre_km"] = gdf["distance_to_centre_m"] / 1000
    denom_is_invalid = "Number of" in gdf.columns and gdf["Number of"].equals(gdf[DV_COLUMN])
    gdf["prop_per_1000_homes"] = np.nan
    gdf["standardization_denominator_available"] = not denom_is_invalid
    return gdf


def london_boundary_wgs84(gdf: gpd.GeoDataFrame):
    gdf_wgs84 = gdf.to_crs(4326)
    if hasattr(gdf_wgs84, "union_all"):
        return gdf_wgs84.union_all()
    return gdf_wgs84.unary_union


def clean_name(series: pd.Series) -> str:
    names = sorted({str(value).strip() for value in series.dropna() if str(value).strip()})
    if not names:
        return "Unnamed station"
    names.sort(key=lambda value: (len(value), value))
    return names[0]


def fetch_official_station_features(boundary_wgs84) -> tuple[gpd.GeoDataFrame, dict]:
    response = requests.get(TFL_API_URL, timeout=60)
    response.raise_for_status()
    payload = response.json()
    stop_points = payload["stopPoints"]

    rows = []
    for stop in stop_points:
        lat = stop.get("lat")
        lon = stop.get("lon")
        if lat is None or lon is None:
            continue
        modes = stop.get("modes") or []
        target_modes = [mode for mode in TARGET_MODES if mode in set(modes)]
        if not target_modes:
            continue
        rows.append(
            {
                "id": stop.get("id"),
                "naptan_id": stop.get("naptanId"),
                "station_naptan": stop.get("stationNaptan"),
                "hub_naptan": stop.get("hubNaptanCode"),
                "name": stop.get("commonName"),
                "stop_type": stop.get("stopType"),
                "lat": lat,
                "lon": lon,
                "target_modes": tuple(target_modes),
            }
        )

    raw_df = pd.DataFrame(rows)
    raw_gdf = gpd.GeoDataFrame(
        raw_df,
        geometry=gpd.points_from_xy(raw_df["lon"], raw_df["lat"]),
        crs=4326,
    )
    raw_gdf = raw_gdf.loc[raw_gdf.geometry.intersects(boundary_wgs84)].copy()
    raw_gdf["station_key"] = (
        raw_gdf["hub_naptan"]
        .fillna(raw_gdf["station_naptan"])
        .fillna(raw_gdf["naptan_id"])
        .fillna(raw_gdf["id"])
    )

    station_records = []
    for station_key, group in raw_gdf.groupby("station_key", sort=True):
        geometry = (group.geometry.union_all() if hasattr(group.geometry, "union_all") else group.geometry.unary_union).centroid
        mode_set = sorted({mode for values in group["target_modes"] for mode in values})
        station_records.append(
            {
                "station_key": station_key,
                "name": clean_name(group["name"]),
                "railway": "tfl_rapid_transit",
                "station": "+".join(mode_set),
                "mode_count": len(mode_set),
                "stop_point_count": int(len(group)),
                "hub_naptan": group["hub_naptan"].dropna().iloc[0]
                if group["hub_naptan"].notna().any()
                else None,
                "geometry": geometry,
            }
        )

    stations = gpd.GeoDataFrame(station_records, geometry="geometry", crs=4326).to_crs(27700)

    metadata = {
        "tfl_api_url": TFL_API_URL,
        "tfl_stop_points_total": int(len(stop_points)),
        "london_stop_points_after_filter": int(len(raw_gdf)),
        "station_complex_count": int(len(stations)),
        "mode_combo_counts": (
            stations["station"].value_counts().sort_index().astype(int).to_dict()
        ),
    }
    return stations.reset_index(drop=True), metadata


def add_nearest_distance(
    gdf: gpd.GeoDataFrame,
    stations: gpd.GeoDataFrame,
    *,
    distance_col: str,
    name_col: str,
    type_col: str,
) -> gpd.GeoDataFrame:
    centroids = gdf.geometry.centroid.to_frame("geometry")
    centroids = gpd.GeoDataFrame(centroids, geometry="geometry", crs=gdf.crs)
    nearest = gpd.sjoin_nearest(
        centroids,
        stations[["name", "railway", "station", "geometry"]],
        how="left",
        distance_col=distance_col,
    )
    gdf = gdf.copy()
    gdf[name_col] = nearest["name"].values
    gdf[type_col] = nearest["station"].fillna(nearest["railway"]).values
    gdf[distance_col] = nearest[distance_col].values
    gdf[distance_col.replace("_m", "_km")] = gdf[distance_col] / 1000
    return gdf


def add_compatibility_aliases(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["station_distance_m"] = gdf["official_station_distance_m"]
    gdf["station_distance_km"] = gdf["official_station_distance_km"]
    gdf["nearest_station_name"] = gdf["nearest_official_station_name"]
    gdf["nearest_station_type"] = gdf["nearest_official_station_type"]
    gdf["tube_station_distance_m"] = gdf["official_station_distance_m"]
    gdf["tube_station_distance_km"] = gdf["official_station_distance_km"]
    gdf["nearest_tube_station_name"] = gdf["nearest_official_station_name"]
    gdf["nearest_tube_station_type"] = gdf["nearest_official_station_type"]
    return gdf


def build_summary(gdf: gpd.GeoDataFrame, metadata: dict) -> dict:
    numeric_cols = [
        DV_COLUMN,
        "lsoa_area_km2",
        "distance_to_centre_km",
        "official_station_distance_km",
        "tube_station_distance_km",
        "prop_per_1000_homes",
        "Number of",
        "Mean Price",
    ]
    summary_stats = (
        gdf[numeric_cols]
        .apply(pd.to_numeric, errors="coerce")
        .describe(percentiles=[0.25, 0.5, 0.75])
        .round(3)
        .to_dict()
    )

    corr_targets = [
        "lsoa_area_km2",
        "Number of",
        "distance_to_centre_km",
        "official_station_distance_km",
        "tube_station_distance_km",
    ]
    corr_values = {}
    for col in corr_targets:
        series = pd.to_numeric(gdf[col], errors="coerce")
        corr_values[col] = round(pd.to_numeric(gdf[DV_COLUMN], errors="coerce").corr(series), 3)

    missingness = (
        gdf[
            [
                "prop_per_1000_homes",
                "official_station_distance_km",
                "tube_station_distance_km",
                "nearest_official_station_name",
                "nearest_tube_station_name",
            ]
        ]
        .isna()
        .sum()
        .to_dict()
    )

    return {
        "shape": list(gdf.shape),
        "crs": str(gdf.crs),
        "official_source": "TfL Unified API StopPoint endpoint",
        "official_definition": "Nearest TfL rapid-transit station complex (Tube, DLR, Overground, Elizabeth line)",
        "compatibility_note": (
            "`tube_station_distance_km` is retained as a backwards-compatible alias "
            "for the official rapid-transit distance used in Steps 2-5."
        ),
        "source_metadata": metadata,
        "columns": gdf.columns.tolist(),
        "summary_stats": summary_stats,
        "prop_count_correlations": corr_values,
        "missingness": missingness,
        "standardization_note": (
            "`Number of` is identical to `Prop_Count`, so the current dataset does not "
            "contain a valid housing-stock denominator for standardization."
        ),
    }


def plot_distribution(
    gdf: gpd.GeoDataFrame, column: str, title: str, filename: str, bins: int = 40
) -> None:
    values = pd.to_numeric(gdf[column], errors="coerce").dropna()
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(values, bins=bins, kde=True, ax=ax, color="#2A6F97")
    ax.set_title(title)
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_choropleth(
    gdf: gpd.GeoDataFrame, column: str, title: str, filename: str, cmap: str = "viridis"
) -> None:
    fig, ax = plt.subplots(figsize=(8, 10))
    gdf.plot(
        column=column,
        scheme="Quantiles",
        k=5,
        cmap=cmap,
        linewidth=0.05,
        edgecolor="white",
        legend=True,
        ax=ax,
        missing_kwds={"color": "lightgrey", "label": "Missing"},
    )
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_outputs(gdf: gpd.GeoDataFrame, stations: gpd.GeoDataFrame, summary: dict) -> None:
    export_columns = [
        "LSOA21CD",
        "LSOA name",
        DV_COLUMN,
        "Value",
        "IMDRank",
        "IMDDecil",
        "Number of",
        "Mean Price",
        "Small Host",
        "Multiple L",
        "Income Sco",
        "Employment",
        "Education,",
        "Health Dep",
        "Crime Scor",
        "Barriers t",
        "Living Env",
        "distance_to_centre_km",
        "official_station_distance_km",
        "nearest_official_station_name",
        "nearest_official_station_type",
        "station_distance_km",
        "nearest_station_name",
        "nearest_station_type",
        "tube_station_distance_km",
        "nearest_tube_station_name",
        "nearest_tube_station_type",
        "prop_per_1000_homes",
        "lsoa_area_km2",
        "geometry",
    ]
    available = [col for col in export_columns if col in gdf.columns]
    gdf[available].to_file(DATA_DIR / "lsoa_step1_enriched_official.gpkg", driver="GPKG")
    stations[
        [
            "station_key",
            "name",
            "railway",
            "station",
            "mode_count",
            "stop_point_count",
            "hub_naptan",
            "geometry",
        ]
    ].to_file(DATA_DIR / "tfl_rapid_transit_station_points.gpkg", driver="GPKG")
    pd.DataFrame(
        {
            "variable": list(summary["prop_count_correlations"].keys()),
            "correlation_with_prop_count": list(summary["prop_count_correlations"].values()),
        }
    ).to_csv(DATA_DIR / "prop_count_correlations_official.csv", index=False)
    with open(DATA_DIR / "step1_official_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main() -> None:
    ensure_dirs()
    sns.set_theme(style="whitegrid")

    gdf = load_lsoa_data()
    gdf = add_geometry_features(gdf)
    stations, metadata = fetch_official_station_features(london_boundary_wgs84(gdf))
    gdf = add_nearest_distance(
        gdf,
        stations,
        distance_col="official_station_distance_m",
        name_col="nearest_official_station_name",
        type_col="nearest_official_station_type",
    )
    gdf = add_compatibility_aliases(gdf)

    summary = build_summary(gdf, metadata)
    save_outputs(gdf, stations, summary)

    plot_distribution(
        gdf,
        DV_COLUMN,
        "Distribution of Airbnb property counts across London LSOAs",
        "prop_count_distribution.png",
    )
    plot_distribution(
        gdf,
        "distance_to_centre_km",
        "Distribution of centroid distance to Charing Cross",
        "distance_to_centre_distribution.png",
    )
    plot_distribution(
        gdf,
        "official_station_distance_km",
        "Distribution of nearest official rapid-transit station distance",
        "official_station_distance_distribution.png",
    )
    plot_choropleth(
        gdf,
        DV_COLUMN,
        "Airbnb property counts by LSOA (quantiles)",
        "prop_count_choropleth_quantiles.png",
        cmap="magma",
    )
    plot_choropleth(
        gdf,
        "distance_to_centre_km",
        "Distance to Charing Cross by LSOA centroid (km, quantiles)",
        "distance_to_centre_choropleth_quantiles.png",
        cmap="plasma",
    )
    plot_choropleth(
        gdf,
        "official_station_distance_km",
        "Nearest official rapid-transit station distance by LSOA (km, quantiles)",
        "official_station_distance_choropleth_quantiles.png",
        cmap="cividis",
    )

    print(json.dumps(summary, indent=2))
    print(f"Saved outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
