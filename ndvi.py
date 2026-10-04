import rasterio
import numpy as np

from rasterio.mask import mask
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer


def calculate_fire_ndvi(red_path, nir_path, fmask_path, fire_geometry):

    # ----------------------------------------
    # Convert fire geometry to Shapely
    # ----------------------------------------

    fire_shape = shape(fire_geometry)

    # ----------------------------------------
    # Load satellite data
    # ----------------------------------------

    with rasterio.open(red_path) as red_src:
        red = red_src.read(1).astype(float)
        raster_crs = red_src.crs

    with rasterio.open(nir_path) as nir_src:
        nir = nir_src.read(1).astype(float)

    with rasterio.open(fmask_path) as fmask_src:
        fmask = fmask_src.read(1)

    # ----------------------------------------
    # Reproject fire perimeter
    # ----------------------------------------

    fire_crs = "EPSG:4326"

    if raster_crs != fire_crs:

        transformer = Transformer.from_crs(
            fire_crs,
            raster_crs,
            always_xy=True
        )

        fire_shape = transform(
            transformer.transform,
            fire_shape
        )

    # ----------------------------------------
    # HLS Fmask filtering
    # ----------------------------------------

    cloud = (fmask & (1 << 1)) != 0
    adjacent = (fmask & (1 << 2)) != 0
    cloud_shadow = (fmask & (1 << 3)) != 0
    snow_ice = (fmask & (1 << 4)) != 0

    clear_pixels = ~(
        cloud |
        adjacent |
        cloud_shadow |
        snow_ice
    )

    # ----------------------------------------
    # Convert HLS reflectance
    # ----------------------------------------

    red = red * 0.0001
    nir = nir * 0.0001

    # ----------------------------------------
    # Calculate NDVI
    # ----------------------------------------

    denominator = nir + red

    ndvi = np.full(red.shape, np.nan)

    valid = (
        clear_pixels &
        (denominator != 0) &
        np.isfinite(red) &
        np.isfinite(nir)
    )

    ndvi[valid] = (
        (nir[valid] - red[valid])
        / denominator[valid]
    )

    # Remove impossible values
    ndvi[(ndvi < -1) | (ndvi > 1)] = np.nan

    # ----------------------------------------
    # Apply fire perimeter
    # ----------------------------------------

    with rasterio.open(red_path) as src:

        fire_mask, _ = mask(
            src,
            [fire_shape],
            crop=False,
            filled=False
        )

    inside_fire = ~fire_mask.mask[0]

    # Keep only valid NDVI pixels inside fire
    ndvi_fire = ndvi[inside_fire]

    ndvi_fire = ndvi_fire[np.isfinite(ndvi_fire)]

    if len(ndvi_fire) == 0:
        raise ValueError(
            "No valid NDVI pixels found inside fire perimeter "
            "after Fmask filtering."
        )

    # ----------------------------------------
    # Return pixel data + statistics
    # ----------------------------------------

    return {
        "pixels": ndvi_fire,

        "valid_pixels": len(ndvi_fire),

        "minimum": float(np.min(ndvi_fire)),

        "maximum": float(np.max(ndvi_fire)),

        "mean": float(np.mean(ndvi_fire)),

        "median": float(np.median(ndvi_fire))
    }