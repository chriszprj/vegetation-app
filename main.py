from fire_search import find_fires
from time_series_search import search_hls_scenes
from scene_selection import select_scenes
from hls_download import download_scene
from ndvi import calculate_fire_ndvi
from recovery_analysis import analyze_recovery
from nbr import calculate_fire_nbr
import tempfile
import numpy as np
import time

# ==================================================
# WILDFIRE VEGETATION RECOVERY ANALYZER
# ==================================================

print("=" * 50)
print("WILDFIRE VEGETATION RECOVERY ANALYZER")
print("=" * 50)


# ==================================================
# 1. GET FIRE FROM USER
# ==================================================

fire_name = input("\nEnter fire name: ").strip()
fire_year = int(input("Enter fire year: ").strip())

print("\nSearching for fire...")

fires = find_fires(fire_name, fire_year)

if not fires:
    print("No matching fires found.")
    exit()

print(f"\nFound {len(fires)} matching record(s).")

for i, fire in enumerate(fires, start=1):

    print("\n" + "-" * 40)
    print(f"Option {i}")
    print(f"Name: {fire['name']}")
    print(f"Year: {fire['year']}")
    print(f"GIS acres: {fire['acres']}")
    print(f"Total acres: {fire['total_acres']}")
    print(f"Agency: {fire['agency']}")
    print(f"Unique ID: {fire['unique_id']}")
    print(f"Geometry: {fire['geometry']['type']}")


choice = int(
    input(f"\nSelect a fire (1-{len(fires)}): ")
)

if choice < 1 or choice > len(fires):
    print("Invalid selection.")
    exit()

fire = fires[choice - 1]

print("\n" + "=" * 50)
print("SELECTED FIRE")
print("=" * 50)

print(f"Name: {fire['name']}")
print(f"Year: {fire['year']}")
print(f"Acres: {fire['acres']}")
print(f"Unique ID: {fire['unique_id']}")
print(f"Geometry: {fire['geometry']['type']}")

if fire["discovery_date"] is not None:
    print(
        f"Discovery date: "
        f"{fire['discovery_date'].date()}"
    )
else:
    print(
        "Discovery date: unavailable"
    )

# ==================================================
# 2. DETERMINE SATELLITE SEARCH AREA
# ==================================================

coordinates = []

geometry = fire["geometry"]

if geometry["type"] == "Polygon":

    for ring in geometry["coordinates"]:
        coordinates.extend(ring)

elif geometry["type"] == "MultiPolygon":

    for polygon in geometry["coordinates"]:

        for ring in polygon:
            coordinates.extend(ring)

else:
    print("Unsupported fire geometry.")
    exit()


longitudes = [
    point[0]
    for point in coordinates
]

latitudes = [
    point[1]
    for point in coordinates
]


bounding_box = (
    min(longitudes),
    min(latitudes),
    max(longitudes),
    max(latitudes)
)


# ==================================================
# 3. SEARCH SATELLITE IMAGERY
# ==================================================
print("\nSearching for satellite imagery...")

years = range(
    fire_year - 2,
    fire_year + 3
)

scenes = search_hls_scenes(
    bounding_box,
    years
)


# ==================================================
# 4. SELECT REPRESENTATIVE SCENES
# ==================================================

selected_scenes = select_scenes(
    scenes,
    fire["discovery_date"].date()
    if fire["discovery_date"] is not None
    else None
)


# ==================================================
# 5. DOWNLOAD TEMPORARY SATELLITE DATA
# ==================================================
print("\nDownloading satellite data...")
download_start = time.time()

downloaded_scenes = {}

with tempfile.TemporaryDirectory() as temp_dir:

    for year, tile_scenes in selected_scenes.items():

        downloaded_scenes[year] = {}

        for tile, scene in tile_scenes.items():

            files = download_scene(
                scene["result"],
                temp_dir
            )

            downloaded_scenes[year][tile] = {
                "files": files,
                "scene_date": scene["date"]
            }

    print(
        f"Satellite download time: "
        f"{time.time() - download_start:.1f} seconds"
    )

    # ==================================================
    # 6. CALCULATE NDVI
    # ==================================================
    ndvi_start = time.time()

    print("\nAnalyzing vegetation condition (NDVI)...")

    ndvi_results = {}

    for year, tile_files in downloaded_scenes.items():

        tile_results = []

        for tile, tile_data in tile_files.items():

            files = tile_data["files"]

            results = calculate_fire_ndvi(
                files["red"],
                files["nir"],
                files["fmask"],
                fire["geometry"]
            )

            tile_results.append(results)

        # ----------------------------------------
        # Combine actual valid pixels from all tiles
        # ----------------------------------------

        all_pixels = np.concatenate(
            [
                result["pixels"]
                for result in tile_results
            ]
        )

        if len(all_pixels) == 0:
            raise ValueError(
                f"No valid NDVI pixels found for {year}."
            )

        # Calculate statistics from the complete
        # fire-wide pixel population.
        # Use the first selected tile's observation date.
        # All selected scenes for a given year are normally
        # from approximately the same seasonal period.
        observation_date = next(
            iter(tile_files.values())
        )["scene_date"]

        ndvi_results[year] = {
            "observation_date": observation_date,

            "valid_pixels": len(all_pixels),

            "mean": float(np.mean(all_pixels)),

            "median": float(np.median(all_pixels)),

            "minimum": float(np.min(all_pixels)),

            "maximum": float(np.max(all_pixels))
        }

    print(
        f"NDVI processing time: "
        f"{time.time() - ndvi_start:.1f} seconds"
    )
    # ----------------------------------------
    # NDVI diagnostic table
    # ----------------------------------------

    print("\nNDVI YEARLY RESULTS")
    print("-" * 70)
    print("Year       Valid Pixels       Mean       Median       Min       Max")
    print("-" * 70)

    for year in sorted(ndvi_results):

        results = ndvi_results[year]

        print(
            f"{year:<10}"
            f"{results['valid_pixels']:<19}"
            f"{results['mean']:<11.4f}"
            f"{results['median']:<13.4f}"
            f"{results['minimum']:<10.4f}"
            f"{results['maximum']:<10.4f}"
        )
    # ==================================================
    # 7. RECOVERY ANALYSIS
    # ==================================================
    recovery = analyze_recovery(
        ndvi_results,
        fire_year,
        fire["discovery_date"].date()
        if fire["discovery_date"] is not None
        else None
    )

    # ==================================================
    # 8. CALCULATE NBR
    # ==================================================
    # ==================================================
    # 8. CALCULATE NBR
    # ==================================================

    nbr_start = time.time()

    print("\nAnalyzing burn severity (NBR)...")

    nbr_results = {}

    for year, tile_files in downloaded_scenes.items():

        tile_results = []

        for tile, scene_data in tile_files.items():

            results = calculate_fire_nbr(
                scene_data["files"]["nir"],
                scene_data["files"]["swir"],
                scene_data["files"]["fmask"],
                fire["geometry"]
            )

            tile_results.append(results)

        total_pixels = sum(
            result["valid_pixels"]
            for result in tile_results
        )

        if total_pixels == 0:
            raise ValueError(
                f"No valid NBR pixels found for {year}."
            )

        # Combine tile means using valid-pixel weighting.
        combined_mean = (
            sum(
                result["mean"] * result["valid_pixels"]
                for result in tile_results
            )
            / total_pixels
        )

        combined_minimum = min(
            result["minimum"]
            for result in tile_results
        )

        combined_maximum = max(
            result["maximum"]
            for result in tile_results
        )

        # Use the first selected tile's observation date.
        observation_date = next(
            iter(tile_files.values())
        )["scene_date"]

        # Determine whether this observation occurred
        # before or after the fire discovery date.
        if (
            fire["discovery_date"] is not None
            and observation_date < fire["discovery_date"].date()
        ):
            fire_relationship = "PRE-FIRE"

        elif (
            fire["discovery_date"] is not None
            and observation_date >= fire["discovery_date"].date()
        ):
            fire_relationship = "POST-DISCOVERY"

        else:
            fire_relationship = "UNKNOWN"

        nbr_results[year] = {
            "observation_date": observation_date,
            "fire_relationship": fire_relationship,
            "valid_pixels": total_pixels,
            "mean": combined_mean,
            "median": None,
            "minimum": combined_minimum,
            "maximum": combined_maximum
        }

    print(
        f"NBR processing time: "
        f"{time.time() - nbr_start:.1f} seconds"
    )

    # ----------------------------------------
    # NBR diagnostic table
    # ----------------------------------------

    print("\nNBR YEARLY RESULTS")
    print("-" * 80)

    print(
        "Year       Observation   Relationship      "
        "Valid Pixels       Mean       Min       Max"
    )

    print("-" * 80)

    for year in sorted(nbr_results):

        results = nbr_results[year]

        print(
            f"{year:<10}"
            f"{str(results['observation_date']):<15}"
            f"{results['fire_relationship']:<19}"
            f"{results['valid_pixels']:<19}"
            f"{results['mean']:<11.4f}"
            f"{results['minimum']:<10.4f}"
            f"{results['maximum']:<10.4f}"
        )

    # ==================================================
    # 8B. CALCULATE dNBR / BURN SEVERITY
    # ==================================================

    pre_fire_nbr_candidates = [
        results
        for results in nbr_results.values()
        if results["fire_relationship"] == "PRE-FIRE"
    ]

    post_fire_nbr_candidates = [
        results
        for results in nbr_results.values()
        if results["fire_relationship"] == "POST-DISCOVERY"
    ]

    burn_severity = None

    if pre_fire_nbr_candidates and post_fire_nbr_candidates:

        # Latest available observation before the fire.
        pre_fire_nbr = max(
            pre_fire_nbr_candidates,
            key=lambda x: x["observation_date"]
        )

        # Earliest available observation after the fire.
        post_fire_nbr = min(
            post_fire_nbr_candidates,
            key=lambda x: x["observation_date"]
        )

        dnbr = (
            pre_fire_nbr["mean"]
            - post_fire_nbr["mean"]
        )

        # Standard dNBR interpretation.
        if dnbr < -0.10:
            severity = "Enhanced regrowth"

        elif dnbr < 0.10:
            severity = "Unburned / very low change"

        elif dnbr < 0.27:
            severity = "Low severity"

        elif dnbr < 0.44:
            severity = "Moderate-low severity"

        elif dnbr < 0.66:
            severity = "Moderate-high severity"

        else:
            severity = "High severity"

        burn_severity = {
            "pre_fire_nbr": pre_fire_nbr["mean"],
            "pre_fire_observation": pre_fire_nbr["observation_date"],
            "post_fire_nbr": post_fire_nbr["mean"],
            "post_fire_observation": post_fire_nbr["observation_date"],
            "dnbr": dnbr,
            "severity_class": severity
        }

        print("\nBURN SEVERITY ANALYSIS")
        print("-" * 70)

        print(
            f"Pre-fire NBR: "
            f"{burn_severity['pre_fire_nbr']:.4f}"
        )

        print(
            f"Pre-fire observation: "
            f"{burn_severity['pre_fire_observation']}"
        )

        print(
            f"Post-fire NBR: "
            f"{burn_severity['post_fire_nbr']:.4f}"
        )

        print(
            f"Post-fire observation: "
            f"{burn_severity['post_fire_observation']}"
        )

        print(
            f"dNBR: "
            f"{burn_severity['dnbr']:+.4f}"
        )

        print(
            f"Burn severity: "
            f"{burn_severity['severity_class']}"
        )

    else:

        print("\nBURN SEVERITY ANALYSIS")
        print("-" * 70)

        print(
            "Unable to calculate dNBR because both "
            "pre-fire and post-fire observations "
            "are required."
        )
    # ==================================================
    # 9. BUILD FINAL ANALYSIS RESULT
    # ==================================================

    analysis_results = {

        "fire": {
            "name": fire["name"],
            "year": fire["year"],
            "acres": fire["acres"],
            "total_acres": fire["total_acres"],
            "agency": fire["agency"],
            "unique_id": fire["unique_id"],
            "geometry_type": fire["geometry"]["type"]
        },

        "ndvi": ndvi_results,

        "nbr": nbr_results,

        "burn_severity": burn_severity,

        "recovery": recovery

    }


# ==================================================
# 10. TEMPORARY DEVELOPMENT OUTPUT
# ==================================================

print("\n" + "=" * 50)
print("ANALYSIS COMPLETE")
print("=" * 50)

print(
    f"\nFire: "
    f"{analysis_results['fire']['name']}"
)

print(
    f"Fire year: "
    f"{analysis_results['fire']['year']}"
)

print(
    f"\nPre-fire NDVI: "
    f"{recovery['reference_ndvi']:.4f}"
)

if recovery["reference_date"] is not None:

    print(
        f"Pre-fire observation: "
        f"{recovery['reference_date']}"
    )


if recovery["fire_ndvi"] is not None:

    print(
        f"First post-discovery NDVI in fire year: "
        f"{recovery['fire_ndvi']:.4f}"
    )

    print(
        f"Fire-year observation: "
        f"{recovery['fire_observation_date']}"
    )

else:

    print(
        "No post-discovery satellite observation "
        "was available during the fire year."
    )

print(
    f"Minimum post-fire NDVI: "
    f"{recovery['minimum_post_fire_ndvi']:.4f}"
)

print(
    f"Minimum post-fire observation: "
    f"{recovery['minimum_post_fire_date']}"
)

print(
    f"Latest NDVI: "
    f"{recovery['latest_ndvi']:.4f}"
)

print(
    f"Latest observation: "
    f"{recovery['latest_date']}"
)


print(
    f"\nChange from pre-fire to latest: "
    f"{recovery['total_change']:+.4f}"
)

if recovery["recovery_percent"] is not None:

    print(
        f"Recovery toward pre-fire NDVI: "
        f"{recovery['recovery_percent']:.1f}%"
    )

else:

    print(
        "Recovery percentage could not be calculated."
    )