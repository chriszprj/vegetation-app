import requests
from datetime import datetime, timezone


URL = "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_FireOccurrenceAndPerimeter_01/MapServer/13/query"


def convert_arcgis_date(value):
    """
    Convert an ArcGIS timestamp in milliseconds since
    Unix epoch into a UTC datetime.
    """

    if value is None:
        return None

    return datetime.fromtimestamp(
        value / 1000,
        tz=timezone.utc
    )


def find_fires(fire_name, fire_year):
    """
    Search the USFS fire perimeter database.

    Returns a list of matching fire records, including
    the recorded discovery date when available.
    """

    params = {
        "where": (
            f"UPPER(firename) LIKE '%{fire_name.upper()}%' "
            f"AND fireyear = {fire_year}"
        ),
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson"
    }

    response = requests.get(
        URL,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Fire database request failed: "
            f"{response.status_code} {response.text}"
        )

    data = response.json()

    features = data.get("features", [])

    fires = []

    for feature in features:

        properties = feature.get("properties", {})

        if (
            properties.get("firename") is not None
            and properties.get("fireyear") is not None
        ):

            discovery_date = convert_arcgis_date(
                properties.get("discoverydatetime")
            )

            fires.append({
                "name": properties.get("firename"),
                "year": properties.get("fireyear"),
                "acres": properties.get("gisacres"),
                "total_acres": properties.get("totalacres"),
                "agency": properties.get("owneragency"),
                "unique_id": properties.get("uniqfireid"),

                "discovery_date": discovery_date,

                "geometry": feature.get("geometry"),
                "properties": properties
            })

    return fires