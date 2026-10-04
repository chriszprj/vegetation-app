import numpy as np

from ndvi import calculate_fire_ndvi
from nbr import calculate_fire_nbr


def safe_ndvi_for_year(tile_files, geometry):
    pixels = []

    for tile, tile_data in tile_files.items():

        try:
            result = calculate_fire_ndvi(
                tile_data["files"]["red"],
                tile_data["files"]["nir"],
                tile_data["files"]["fmask"],
                geometry,
            )

            if len(result["pixels"]):
                pixels.append(result["pixels"])

        except ValueError as exc:

            if "No valid NDVI pixels" not in str(exc):
                raise

    if not pixels:
        return None

    all_pixels = np.concatenate(pixels)

    return {
        "valid_pixels": len(all_pixels),
        "mean": float(np.mean(all_pixels)),
        "median": float(np.median(all_pixels)),
        "minimum": float(np.min(all_pixels)),
        "maximum": float(np.max(all_pixels)),
    }


def safe_nbr_for_year(tile_files, geometry, fire_date):
    results = []

    for tile, tile_data in tile_files.items():

        try:
            result = calculate_fire_nbr(
                tile_data["files"]["nir"],
                tile_data["files"]["swir"],
                tile_data["files"]["fmask"],
                geometry,
            )

            if result["valid_pixels"] > 0:
                results.append(result)

        except ValueError as exc:

            if "No valid NBR" not in str(exc):
                raise

    if not results:
        return None

    total_pixels = sum(
        result["valid_pixels"]
        for result in results
    )

    mean = (
        sum(
            result["mean"] * result["valid_pixels"]
            for result in results
        )
        / total_pixels
    )

    observation_date = next(
        iter(tile_files.values())
    )["scene_date"]

    if fire_date is None:
        relationship = "UNKNOWN"

    elif observation_date < fire_date:
        relationship = "PRE-FIRE"

    else:
        relationship = "POST-DISCOVERY"

    return {
        "observation_date": observation_date,
        "fire_relationship": relationship,
        "valid_pixels": total_pixels,
        "mean": mean,
        "median": None,
        "minimum": min(
            result["minimum"]
            for result in results
        ),
        "maximum": max(
            result["maximum"]
            for result in results
        ),
    }