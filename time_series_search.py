import os
import earthaccess
import re
from datetime import datetime


def search_hls_scenes(bounding_box, years):
    """
    Search NASA HLS Sentinel-2 imagery for the selected fire.

    The analysis uses a fixed growing-season window of
    July 1 through September 30 for every requested year.

    Scenes are later selected based on their proximity to
    August 1, providing seasonally comparable observations.

    The requested years are supplied by the calling application,
    allowing the analysis window to expand through the latest
    complete year of satellite data.

    Returns candidate scenes grouped by year.
    Each scene includes its HLS/MGRS tile ID and observation date.
    """

    print("\nAuthenticating with NASA Earthdata...")

    # Project-specific Earthdata account.
    # Replace the two placeholder values with the credentials
    # for your dedicated Earthdata account.
    os.environ["EARTHDATA_USERNAME"] = "firerecovery22211jof"
    os.environ["EARTHDATA_PASSWORD"] = "MnuTV184Qwer!"

    earthaccess.login(
        strategy="environment"
    )

    all_scenes = {}

    for year in years:

        print()
        print("=" * 50)
        print(f"SEARCHING {year}")
        print("=" * 50)

        start_date = f"{year}-07-01"
        end_date = f"{year}-09-30"

        results = earthaccess.search_data(
            short_name="HLSS30",
            version="2.0",
            bounding_box=bounding_box,
            temporal=(start_date, end_date),
            count=100
        )

        scenes = []
        seen_ids = set()

        for result in results:

            scene_id = result["meta"]["native-id"]

            if scene_id in seen_ids:
                continue

            if not scene_id.startswith("HLS.S30."):
                continue

            # Extract YYYYDDD from the HLS scene ID.
            date_match = re.search(
                r"\.(\d{7})T",
                scene_id
            )

            if not date_match:
                continue

            date_code = date_match.group(1)

            # Convert YYYYDDD into a calendar date.
            year_from_id = int(date_code[:4])
            day_of_year = int(date_code[4:])

            scene_date = datetime.strptime(
                f"{year_from_id} {day_of_year}",
                "%Y %j"
            ).date()

            # Extract MGRS tile.
            tile_match = re.search(
                r"\.T([A-Z0-9]{5})\.",
                scene_id
            )

            if not tile_match:
                continue

            tile_id = tile_match.group(1)

            scenes.append({
                "id": scene_id,
                "date_code": date_code,
                "date": scene_date,
                "tile": tile_id,
                "result": result
            })

            seen_ids.add(scene_id)

        all_scenes[year] = scenes

        # Show tile coverage.
        tiles = sorted(
            set(scene["tile"] for scene in scenes)
        )

        print(
            f"Usable HLS S30 scenes found: "
            f"{len(scenes)}"
        )

        print(
            f"HLS tiles found: "
            f"{len(tiles)}"
        )

        for tile in tiles:

            tile_scenes = [
                scene
                for scene in scenes
                if scene["tile"] == tile
            ]

            print(
                f"  Tile {tile}: "
                f"{len(tile_scenes)} scene(s)"
            )

    return all_scenes