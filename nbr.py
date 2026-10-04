import rasterio
import numpy as np
import geopandas as gpd
from rasterio.mask import mask
from shapely.geometry import shape


def calculate_fire_nbr(nir_path, swir_path, fmask_path, fire_geojson):
    """
    Calculate NBR inside the selected fire perimeter.

    NBR = (NIR - SWIR) / (NIR + SWIR)
    """

    fire_shape = shape(fire_geojson)


    with rasterio.open(nir_path) as nir_src:
        nir = nir_src.read(1).astype(float)
        raster_crs = nir_src.crs

    with rasterio.open(swir_path) as swir_src:
        swir = swir_src.read(1).astype(float)

    with rasterio.open(fmask_path) as fmask_src:
        fmask = fmask_src.read(1)

    # ----------------------------------------
    # Fmask filtering
    # ----------------------------------------

    # HLS V2.0 Fmask bits:
    # Bit 1 = Cloud
    # Bit 2 = Adjacent to cloud/shadow
    # Bit 3 = Cloud shadow
    # Bit 4 = Snow/ice
    # Bit 5 = Water
    #
    # Water is intentionally not excluded.

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


    # HLS reflectance scale factor
    nir = nir * 0.0001
    swir = swir * 0.0001

    denominator = nir + swir

    nbr = np.full(nir.shape, np.nan)

    valid = (
        clear_pixels &
        (denominator != 0) &
        np.isfinite(nir) &
        np.isfinite(swir)
    )

    nbr[valid] = (
        (nir[valid] - swir[valid])
        / denominator[valid]
    )

    # Remove impossible values
    nbr[(nbr < -1) | (nbr > 1)] = np.nan


    # Convert fire geometry into satellite CRS.
    fire_gdf = gpd.GeoDataFrame(
        geometry=[fire_shape],
        crs="EPSG:4326"
    )

    fire_gdf = fire_gdf.to_crs(raster_crs)

    geometry = [fire_gdf.geometry.iloc[0]]

    with rasterio.open(nir_path) as src:

        fire_mask, _ = mask(
            src,
            geometry,
            crop=False,
            filled=False
        )

    inside_fire = ~fire_mask.mask[0]

    nbr_fire = nbr[inside_fire]

    nbr_fire = nbr_fire[np.isfinite(nbr_fire)]

    if len(nbr_fire) == 0:
        raise ValueError(
            "No valid NBR pixels found inside fire perimeter "
            "after Fmask filtering."
        )

    return {
        "valid_pixels": len(nbr_fire),
        "minimum": float(np.min(nbr_fire)),
        "maximum": float(np.max(nbr_fire)),
        "mean": float(np.mean(nbr_fire)),
        "median": float(np.median(nbr_fire))
    }