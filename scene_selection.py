from datetime import datetime


def select_scenes(all_scenes, fire_date):
    """
    Select one representative HLS scene for each tile in each year.

    Scenes are selected based on their proximity to August 1,
    providing a consistent seasonal target across years.

    Only scenes within the July-September growing-season window
    are considered because the search stage already restricts
    the available scenes to that period.

    Each selected scene is classified relative to the actual
    fire discovery date.
    """

    selected = {}

    for year, scenes in all_scenes.items():

        if not scenes:
            print(f"No usable scenes found for {year}.")
            continue

        # ----------------------------------------
        # Seasonal target
        # ----------------------------------------

        target_date = datetime(
            year,
            8,
            1
        ).date()

        # ----------------------------------------
        # Group scenes by HLS tile
        # ----------------------------------------

        tiles = {}

        for scene in scenes:

            tile = scene["tile"]

            if tile not in tiles:
                tiles[tile] = []

            tiles[tile].append(scene)

        selected[year] = {}

        for tile, tile_scenes in tiles.items():

            # ----------------------------------------
            # Select scene closest to August 1
            # ----------------------------------------

            selected_scene = min(
                tile_scenes,
                key=lambda scene: abs(
                    scene["date"] - target_date
                )
            )

            # ----------------------------------------
            # Observation date
            # ----------------------------------------

            observation_date = selected_scene["date"]

            # ----------------------------------------
            # Determine temporal relationship
            # ----------------------------------------

            if fire_date is None:

                fire_relationship = "UNKNOWN"

            elif observation_date < fire_date:

                fire_relationship = "PRE-FIRE"

            else:

                fire_relationship = "POST-DISCOVERY"

            selected_scene["fire_relationship"] = fire_relationship

            selected[year][tile] = selected_scene

            print()
            print(
                f"{year} - Tile {tile} selected scene:"
            )

            print(
                f"  {selected_scene['id']}"
            )

            print(
                f"  Observation date: "
                f"{observation_date}"
            )

            print(
                f"  Fire relationship: "
                f"{fire_relationship}"
            )

    return selected