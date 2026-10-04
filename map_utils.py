import streamlit as st
import pydeck as pdk


def format_acres(value):
    if value is None:
        return "Area unavailable"

    try:
        return f"{float(value):,.0f} acres"
    except (TypeError, ValueError):
        return "Area unavailable"


def geometry_coordinates(geometry):
    coords = []

    if geometry.get("type") == "Polygon":
        for ring in geometry["coordinates"]:
            coords.append(ring)

    elif geometry.get("type") == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            coords.extend(polygon)

    return coords


def geometry_bounds(geometry):
    rings = geometry_coordinates(geometry)

    points = [
        p
        for ring in rings
        for p in ring
    ]

    if not points:
        return None

    lons = [p[0] for p in points]
    lats = [p[1] for p in points]

    return (
        min(lons),
        min(lats),
        max(lons),
        max(lats)
    )


def make_fire_features(fire):
    geometry = fire["geometry"]
    features = []

    if geometry.get("type") == "Polygon":
        polygons = [geometry["coordinates"]]

    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry["coordinates"]

    else:
        return []

    for i, polygon in enumerate(polygons, 1):

        features.append({
            "type": "Feature",

            "properties": {
                "part": i,
                "fire": fire.get("name") or "Unnamed fire",
                "year": fire.get("year") or "Unknown",
                "acres": format_acres(
                    fire.get("acres")
                ),
                "description": (
                    "Fire perimeter area. "
                    "Click this area for details."
                ),
            },

            "geometry": {
                "type": "Polygon",
                "coordinates": polygon,
            },
        })

    return features


def fire_map(fire):
    bounds = geometry_bounds(
        fire["geometry"]
    )

    features = make_fire_features(fire)

    if not bounds or not features:
        st.warning(
            "The fire perimeter could not be mapped."
        )
        return

    min_lon, min_lat, max_lon, max_lat = bounds

    center_lon = (
        min_lon + max_lon
    ) / 2

    center_lat = (
        min_lat + max_lat
    ) / 2

    span = max(
        max_lon - min_lon,
        max_lat - min_lat
    )

    if span > 4:
        zoom = 6

    elif span > 2:
        zoom = 7

    elif span > 0.8:
        zoom = 8

    elif span > 0.3:
        zoom = 9

    elif span > 0.1:
        zoom = 10

    else:
        zoom = 11

    map_key = (
        f"fire_map_"
        f"{st.session_state.get('map_reset', 0)}"
    )

    deck = pdk.Deck(
        map_style=None,

        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
        ),

        layers=[
            pdk.Layer(
                "GeoJsonLayer",

                data={
                    "type": "FeatureCollection",
                    "features": features,
                },

                pickable=True,
                stroked=True,
                filled=True,

                get_fill_color=[
                    220,
                    40,
                    40,
                    100
                ],

                get_line_color=[
                    180,
                    20,
                    20,
                    220
                ],

                get_line_width=3,
                line_width_min_pixels=2,
                auto_highlight=True,
            )
        ],

        tooltip={
            "html": (
                "<b>{fire}</b><br/>"
                "Fire year: {year}<br/>"
                "Reported area: {acres}<br/>"
                "Perimeter part: {part}<br/>"
                "{description}"
            ),

            "style": {
                "backgroundColor": "white",
                "color": "black",
            },
        },
    )

    event = st.pydeck_chart(
        deck,
        width="stretch",
        height=520,
        selection_mode="single-object",
        on_select="rerun",
        key=map_key,
    )

    if event and hasattr(event, "selection"):

        selected = event.selection.objects.get(
            "default",
            []
        )

        if selected:

            part = selected[0].get(
                "part",
                "unknown"
            )

            st.info(
                f"**Selected perimeter section {part}.** "
                f"This section is part of the mapped "
                f"{fire.get('name') or 'fire'} perimeter and is "
                "included in the area used for the satellite analysis."
            )