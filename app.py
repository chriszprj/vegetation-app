import streamlit as st
import tempfile
import time
from datetime import date

from fire_search import find_fires
from time_series_search import search_hls_scenes
from scene_selection import select_scenes
from hls_download import download_scene
from recovery_analysis import analyze_recovery
from map_utils import fire_map, geometry_bounds
from display_utils import (
    build_ndvi_table,
    build_nbr_table,
    make_line_chart,
)
from analysis_utils import (
    safe_ndvi_for_year,
    safe_nbr_for_year,
)


st.set_page_config(
    page_title="Wildfire Vegetation Recovery Analyzer",
    page_icon="🔥",
    layout="wide",
)


# -----------------------------
# Helpers
# -----------------------------
def format_acres(value):
    if value is None:
        return "Area unavailable"
    try:
        return f"{float(value):,.0f} acres"
    except (TypeError, ValueError):
        return "Area unavailable"


def size_text(value):
    if value is None:
        return "The fire's reported acreage is unavailable."
    try:
        a = float(value)
    except (TypeError, ValueError):
        return "The fire's reported acreage is unavailable."

    if a < 100:
        return "Very small fire: less than 100 acres."
    if a < 1_000:
        return "Small fire: hundreds of acres."
    if a < 10_000:
        return "Moderate-sized fire: thousands of acres."
    if a < 50_000:
        return "Large fire: tens of thousands of acres."
    if a < 100_000:
        return "Very large fire: tens of thousands of acres."

    return "Massive fire: more than 100,000 acres."


def recovery_text(percent):
    if percent is None:
        return (
            "A recovery percentage could not be calculated "
            "from the available observations."
        )

    if percent < 20:
        return (
            "Very limited recovery: the latest vegetation "
            "measurement has moved only a small distance back "
            "toward the pre-fire level."
        )

    if percent < 40:
        return (
            "Some recovery is visible, but vegetation remains "
            "substantially below the pre-fire level."
        )

    if percent < 60:
        return (
            "Moderate recovery is visible: a meaningful portion "
            "of the vegetation loss has been regained."
        )

    if percent < 80:
        return (
            "Strong recovery is visible: vegetation has moved "
            "much of the way back toward its pre-fire level."
        )

    return (
        "Near-complete recovery in the measured signal: the "
        "latest NDVI is close to the pre-fire level."
    )


def ndvi_change_text(pre, latest):
    if pre is None or latest is None:
        return ""

    change = latest - pre

    if change > 0.03:
        return (
            "The latest NDVI is above the pre-fire reference, "
            "indicating the measured vegetation signal has "
            "recovered beyond that reference."
        )

    if change > -0.03:
        return (
            "The latest NDVI is very close to the pre-fire "
            "reference, suggesting little remaining difference "
            "in the measured vegetation signal."
        )

    return (
        "The latest NDVI remains below the pre-fire reference, "
        "so the measured vegetation signal has not fully returned "
        "to its earlier level."
    )


def severity_text(severity):
    return {
        "Enhanced regrowth": (
            "The post-fire NBR was higher than the pre-fire value. "
            "This is not a strong burn signature and can reflect "
            "vegetation or surface changes rather than severe burning."
        ),
        "Unburned / very low change": (
            "Little overall spectral change was measured between "
            "the selected pre-fire and post-fire observations."
        ),
        "Low severity": (
            "The measurements indicate a relatively small "
            "fire-related change in the analyzed area."
        ),
        "Moderate-low severity": (
            "A noticeable fire-related change was measured, but "
            "it is below the stronger severity categories."
        ),
        "Moderate-high severity": (
            "The measurements indicate substantial fire-related "
            "change across the analyzed area."
        ),
        "High severity": (
            "The measurements indicate a very large fire-related "
            "change between the selected observations."
        ),
    }.get(
        severity,
        "The burn-severity classification could not be interpreted.",
    )


def get_analysis_years(fire_year):
    """
    Build the analysis window dynamically.

    The analysis begins two years before the fire.

    After the fire, the analysis extends for up to ten years,
    but never beyond the most recent complete calendar year.

    Examples:
        2015 -> 2013-2025
        2019 -> 2017-2025
        2023 -> 2021-2025
        2025 -> 2023-2025
    """

    current_year = date.today().year
    latest_complete_year = current_year - 1

    start_year = fire_year - 2
    end_year = min(
        fire_year + 10,
        latest_complete_year,
    )

    if end_year < start_year:
        return []

    return range(
        start_year,
        end_year + 1,
    )


# -----------------------------
# Header / educational material
# -----------------------------
st.title("🔥 Wildfire Vegetation Recovery Analyzer")

st.write(
    "Select a wildfire and examine its footprint, vegetation condition, "
    "burn-related spectral change, and recovery over time. The analysis "
    "uses two years before the fire as a baseline and follows vegetation "
    "for up to ten years afterward, or through the most recent complete "
    "year when fewer years are available."
)

with st.expander("ℹ️ What are NDVI, NBR, dNBR, and recovery?"):
    st.markdown(
        """
**NDVI — vegetation condition**

NDVI is a satellite measurement used to describe the amount and condition
of green vegetation. In general, higher NDVI means a stronger vegetation
signal, while lower NDVI means a weaker vegetation signal.

**NBR — burn-related surface signal**

NBR is another satellite measurement that is useful for identifying changes
associated with burned vegetation and exposed surfaces.

**dNBR — estimated fire-related change**

dNBR compares a pre-fire NBR measurement with a post-fire NBR measurement.
In this project, a larger positive dNBR corresponds to a stronger measured
change between those observations.

**Recovery percentage**

The recovery percentage asks: after the lowest measured post-fire NDVI,
how far has the latest NDVI moved back toward the pre-fire NDVI?

For example, 20% recovery does **not** mean that 20% of the forest is alive.
It means the latest measured NDVI has closed about one-fifth of the gap
between the lowest observed post-fire condition and the pre-fire reference.

These are satellite indicators, not a complete ecological assessment.
"""
    )

st.warning(
    "⚠️ Data availability: this analyzer uses NASA HLS satellite data, "
    "which is generally available for this project from 2016 onward. "
    "Earlier years may not have usable satellite observations."
)

with st.expander("Read more about data availability and processing"):
    st.write(
        "The satellite archive used by this analyzer does not provide the "
        "same usable HLS coverage for years before 2016. Because the "
        "analysis depends on HLS Sentinel-2 imagery, an older fire may "
        "therefore have missing years rather than complete historical data."
    )
    st.write(
        "The analyzer also searches a seasonal window and applies quality "
        "filtering. Clouds, invalid pixels, missing scenes, and individual "
        "download failures can leave some years unavailable. When a "
        "satellite download fails, the app retries it and skips the affected "
        "year or tile if the retry attempts do not succeed."
    )

with st.expander("⚠️ Processing time and data limitations"):
    st.write(
        "The analyzer searches NASA HLS satellite data and downloads the "
        "selected scenes before calculating the results. Large fires can "
        "cover multiple satellite tiles and may take several minutes to "
        "process. Cloud and quality filtering can also leave some years "
        "without enough valid pixels."
    )


# -----------------------------
# Search
# -----------------------------
st.header("Find a wildfire")

fire_name = st.text_input(
    "Fire name or partial name",
    placeholder="Try CARR, Bobcat, or even a single letter",
)

fire_year = st.number_input(
    "Fire year",
    min_value=1900,
    max_value=2100,
    value=2020,
    step=1,
)

if st.button(
    "🔎 Search for fires",
    type="primary",
):
    with st.spinner("Searching wildfire records..."):
        fires = find_fires(
            fire_name.strip(),
            int(fire_year),
        )

    if not fires:
        st.session_state.pop("fires", None)
        st.error("No matching fires were found.")

    else:
        st.session_state["fires"] = fires
        st.session_state["run_analysis"] = False
        st.session_state.pop(
            "selected_fire",
            None,
        )


# -----------------------------
# Fire selection
# -----------------------------
if "fires" in st.session_state:
    fires = st.session_state["fires"]

    st.success(
        f"Found {len(fires)} matching fire(s)."
    )

    if len(fires) > 100:
        st.info(
            "This search returned many fires. Use the selector below "
            "to choose one. Missing acreage is shown as "
            "'Area unavailable' rather than stopping the search."
        )

    options = []

    for fire in fires:
        options.append(
            f"{fire.get('name') or 'Unnamed fire'} — "
            f"{fire.get('year') or 'Unknown year'} — "
            f"{format_acres(fire.get('acres'))} — "
            f"{fire.get('unique_id') or 'No ID'}"
        )

    selected_index = st.selectbox(
        "Select the fire you want to analyze:",
        range(len(fires)),
        format_func=lambda i: options[i],
    )

    fire = fires[selected_index]

    st.session_state["selected_fire"] = fire

    st.divider()
    st.header("Selected Fire")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Fire",
            fire.get("name") or "Unnamed",
        )

        st.write(
            f"**Year:** "
            f"{fire.get('year') or 'Unknown'}"
        )

        st.write(
            f"**Agency:** "
            f"{fire.get('agency') or 'Unavailable'}"
        )

    with c2:
        st.metric(
            "Fire size",
            format_acres(
                fire.get("acres")
            ),
        )

        st.write(
            size_text(
                fire.get("acres")
            )
        )

    with c3:
        st.write(
            f"**Unique ID:** "
            f"{fire.get('unique_id') or 'Unavailable'}"
        )

        st.write(
            f"**Geometry:** "
            f"{fire.get('geometry', {}).get('type', 'Unavailable')}"
        )

        if fire.get("discovery_date") is not None:
            st.write(
                f"**Discovery date:** "
                f"{fire['discovery_date'].date()}"
            )
        else:
            st.write(
                "**Discovery date:** unavailable"
            )

    st.subheader("Fire Location")

    st.caption(
        "The red area is the recorded fire perimeter. "
        "Hover for details and click a perimeter section to inspect it."
    )

    if st.button("🎯 Recenter map on fire"):
        st.session_state["map_reset"] = (
            st.session_state.get("map_reset", 0) + 1
        )
        st.rerun()

    fire_map(fire)

    if st.button(
        "🔥 Analyze this fire",
        type="primary",
    ):
        st.session_state["selected_fire"] = fire
        st.session_state["run_analysis"] = True
        st.rerun()


# -----------------------------
# Analysis
# -----------------------------
if (
    st.session_state.get("run_analysis")
    and "selected_fire" in st.session_state
):
    fire = st.session_state["selected_fire"]
    fire_year = fire["year"]
    geometry = fire["geometry"]

    st.divider()

    st.header(
        f"Analysis of the "
        f"{fire.get('name') or 'Selected'} Fire"
    )

    years = get_analysis_years(fire_year)

    if not years:
        st.error(
            "No valid analysis years are available for this fire."
        )
        st.stop()

    start_year = years.start
    end_year = years.stop - 1

    st.info(
        f"This analysis covers {start_year}–{end_year}. "
        f"It uses two years before the fire as the pre-fire baseline "
        f"and follows the vegetation for up to ten years afterward, "
        f"ending at the most recent complete calendar year. "
        f"The exact satellite observation date in each year depends "
        f"on data availability."
    )

    bounds = geometry_bounds(geometry)

    if bounds is None:
        st.error(
            "The selected fire has no usable perimeter coordinates."
        )
        st.stop()

    fire_date = (
        fire["discovery_date"].date()
        if fire.get("discovery_date") is not None
        else None
    )

    try:
        with st.status(
            "Searching NASA HLS satellite imagery...",
            expanded=True,
        ) as status:

            st.write(
                f"Finding suitable Sentinel-2 HLS scenes "
                f"for {start_year}–{end_year}..."
            )

            scenes = search_hls_scenes(
                bounds,
                years,
            )

            status.update(
                label="Satellite search complete.",
                state="complete",
            )

    except Exception as exc:
        st.error(
            f"Satellite search failed: {exc}"
        )
        st.stop()

    selected_scenes = select_scenes(
        scenes,
        fire_date,
    )

    if not selected_scenes:
        st.error(
            "No usable satellite scenes were found for this fire."
        )
        st.stop()

    downloaded_scenes = {}
    download_failures = []

    try:
        with tempfile.TemporaryDirectory() as temp_dir:

            with st.status(
                "Downloading satellite data...",
                expanded=True,
            ) as status:

                for year, tile_scenes in selected_scenes.items():

                    if not tile_scenes:
                        continue

                    downloaded_scenes[year] = {}

                    # Show one simple message per year.
                    st.write(f"Downloading {year}...")

                    for tile, scene in tile_scenes.items():

                        success = False
                        last_error = None

                        for attempt in range(1, 4):

                            try:
                                files = download_scene(
                                    scene["result"],
                                    temp_dir,
                                )

                                downloaded_scenes[year][tile] = {
                                    "files": files,
                                    "scene_date": scene["date"],
                                }

                                success = True
                                break

                            except Exception as exc:
                                last_error = exc

                                if attempt < 3:
                                    time.sleep(2)

                        if not success:
                            download_failures.append(
                                {
                                    "year": year,
                                    "tile": tile,
                                    "error": str(last_error),
                                }
                            )

                    # If every tile for a year failed, remove the
                    # empty year so it does not enter later analysis.
                    if not downloaded_scenes[year]:
                        del downloaded_scenes[year]

                        st.warning(
                            f"No satellite data could be downloaded "
                            f"for {year}. That year will be skipped."
                        )

                status.update(
                    label="Satellite download complete.",
                    state="complete",
                )

            if download_failures:
                st.info(
                    f"{len(download_failures)} satellite download(s) "
                    "could not be completed. The affected scenes were "
                    "skipped instead of stopping the entire analysis."
                )

            if not downloaded_scenes:
                st.error(
                    "No satellite scenes could be downloaded successfully "
                    "for this fire."
                )
                st.stop()

            # -------------------------
            # NDVI
            # -------------------------
            with st.status(
                "Analyzing vegetation condition (NDVI)...",
                expanded=True,
            ) as status:

                ndvi_results = {}
                ndvi_failures = []

                for year, tile_files in downloaded_scenes.items():

                    result = safe_ndvi_for_year(
                        tile_files,
                        geometry,
                    )

                    if result is None:
                        ndvi_failures.append(year)
                        continue

                    result["observation_date"] = next(
                        iter(tile_files.values())
                    )["scene_date"]

                    ndvi_results[year] = result

                status.update(
                    label="NDVI analysis complete.",
                    state="complete",
                )

            if ndvi_failures:
                st.warning(
                    "No valid NDVI pixels remained after quality filtering "
                    f"for {', '.join(map(str, ndvi_failures))}. "
                    "Those years are shown as unavailable instead of "
                    "crashing the analysis."
                )

            if not ndvi_results:
                st.error(
                    "No valid NDVI observations were available for this fire."
                )
                st.stop()

            recovery = analyze_recovery(
                ndvi_results,
                fire_year,
                fire_date,
            )


            # -------------------------
            # NBR
            # -------------------------
            with st.status(
                "Analyzing burn-related change (NBR)...",
                expanded=True,
            ) as status:

                nbr_results = {}
                nbr_failures = []

                for year, tile_files in downloaded_scenes.items():

                    result = safe_nbr_for_year(
                        tile_files,
                        geometry,
                        fire_date,
                    )

                    if result is None:
                        nbr_failures.append(year)
                        continue

                    nbr_results[year] = result

                status.update(
                    label="NBR analysis complete.",
                    state="complete",
                )

            if nbr_failures:
                st.warning(
                    "No valid NBR pixels remained after quality filtering "
                    f"for {', '.join(map(str, nbr_failures))}. "
                    "Those years are shown as unavailable."
                )


            # -------------------------
            # Burn severity
            # -------------------------
            burn_severity = None

            pre_fire = [
                result
                for result in nbr_results.values()
                if result["fire_relationship"] == "PRE-FIRE"
            ]

            post_fire = [
                result
                for result in nbr_results.values()
                if result["fire_relationship"] == "POST-DISCOVERY"
            ]

            if pre_fire and post_fire:

                pre = max(
                    pre_fire,
                    key=lambda x: x["observation_date"],
                )

                post = min(
                    post_fire,
                    key=lambda x: x["observation_date"],
                )

                dnbr = (
                    pre["mean"]
                    - post["mean"]
                )

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
                    "pre_fire_nbr": pre["mean"],
                    "pre_fire_observation":
                        pre["observation_date"],
                    "post_fire_nbr": post["mean"],
                    "post_fire_observation":
                        post["observation_date"],
                    "dnbr": dnbr,
                    "severity_class": severity,
                }

    except Exception as exc:
        st.error(
            "The satellite analysis could not be completed. "
            "This can happen when a selected scene contains no usable "
            "pixels inside the fire perimeter.\n\n"
            f"Details: {exc}"
        )
        st.stop()


    # -------------------------
    # Results overview
    # -------------------------
    st.success("Analysis complete!")

    st.divider()

    st.header("🌱 Vegetation Recovery")

    a, b, c = st.columns(3)

    with a:
        st.metric(
            "Pre-fire NDVI",
            (
                f"{recovery['reference_ndvi']:.4f}"
                if recovery["reference_ndvi"] is not None
                else "N/A"
            ),
        )

    with b:
        st.metric(
            "Latest NDVI",
            (
                f"{recovery['latest_ndvi']:.4f}"
                if recovery["latest_ndvi"] is not None
                else "N/A"
            ),
        )

    with c:
        st.metric(
            "Recovery toward pre-fire",
            (
                f"{recovery['recovery_percent']:.1f}%"
                if recovery["recovery_percent"] is not None
                else "N/A"
            ),
        )

    if recovery["recovery_percent"] is not None:

        st.subheader(
            "What does the recovery percentage mean?"
        )

        st.write(
            recovery_text(
                recovery["recovery_percent"]
            )
        )

        st.caption(
            "This percentage describes movement of the NDVI "
            "measurement toward the pre-fire reference; it is "
            "not a percentage of forest area recovered."
        )

    if (
        recovery["reference_ndvi"] is not None
        and recovery["latest_ndvi"] is not None
    ):
        st.write(
            ndvi_change_text(
                recovery["reference_ndvi"],
                recovery["latest_ndvi"],
            )
        )

    detail_cols = st.columns(4)

    detail_cols[0].metric(
        "Lowest post-fire NDVI",
        (
            f"{recovery['minimum_post_fire_ndvi']:.4f}"
            if recovery["minimum_post_fire_ndvi"] is not None
            else "N/A"
        ),
    )

    detail_cols[1].metric(
        "Change from pre-fire",
        (
            f"{recovery['total_change']:+.4f}"
            if recovery["total_change"] is not None
            else "N/A"
        ),
    )

    detail_cols[2].write(
        "**Pre-fire date**\n\n"
        f"{recovery['reference_date'] or 'Unavailable'}"
    )

    detail_cols[3].write(
        "**Latest date**\n\n"
        f"{recovery['latest_date'] or 'Unavailable'}"
    )


    # -------------------------
    # NDVI table / chart
    # -------------------------
    st.subheader(
        "NDVI across the full analysis window"
    )

    st.caption(
        "Every available year is shown. NDVI is a vegetation "
        "signal, so the important question is how the values "
        "change relative to the fire."
    )

    st.dataframe(
        build_ndvi_table(
            ndvi_results,
            fire_year,
            fire_date,
        ),
        width="stretch",
        hide_index=True,
    )

    make_line_chart(
        ndvi_results,
        "mean",
        "Vegetation condition over time",
        "Mean NDVI",
    )


    # -------------------------
    # Burn severity
    # -------------------------
    st.divider()

    st.header("🔥 Burn Severity")

    if burn_severity is not None:

        a, b, c = st.columns(3)

        a.metric(
            "Pre-fire NBR",
            f"{burn_severity['pre_fire_nbr']:.4f}",
        )

        b.metric(
            "Post-fire NBR",
            f"{burn_severity['post_fire_nbr']:.4f}",
        )

        c.metric(
            "dNBR",
            f"{burn_severity['dnbr']:+.4f}",
        )

        st.subheader(
            "Classification: "
            f"{burn_severity['severity_class']}"
        )

        st.write(
            severity_text(
                burn_severity["severity_class"]
            )
        )

        st.write(
            f"**Compared observations:** "
            f"{burn_severity['pre_fire_observation']} "
            f"→ {burn_severity['post_fire_observation']}"
        )

    else:
        st.warning(
            "Burn severity could not be classified because "
            "a usable pre-fire and post-fire NBR comparison "
            "was not available."
        )


    st.subheader(
        "NBR across the full analysis window"
    )

    st.caption(
        "NBR values are shown for every available year. "
        "dNBR is calculated separately from the selected "
        "pre-fire and post-fire observations."
    )

    if nbr_results:

        st.dataframe(
            build_nbr_table(nbr_results),
            width="stretch",
            hide_index=True,
        )

        make_line_chart(
            nbr_results,
            "mean",
            "Burn-related satellite measurements over time",
            "Mean NBR",
        )

    else:
        st.info(
            "No NBR observations were available."
        )


    # -------------------------
    # Overall interpretation
    # -------------------------
    st.divider()

    st.header("📋 Overall Interpretation")

    st.write(
        f"**Fire size:** "
        f"{format_acres(fire.get('acres'))}. "
        f"{size_text(fire.get('acres'))}"
    )

    st.write(
        f"**Vegetation:** "
        f"{recovery_text(recovery.get('recovery_percent'))}"
    )

    if (
        recovery.get("reference_ndvi") is not None
        and recovery.get("latest_ndvi") is not None
    ):
        st.write(
            ndvi_change_text(
                recovery["reference_ndvi"],
                recovery["latest_ndvi"],
            )
        )

    if burn_severity:
        st.write(
            f"**Burn-related change:** "
            f"{severity_text(burn_severity['severity_class'])}"
        )

    st.info(
        "Important: these conclusions describe changes in "
        "satellite-derived spectral measurements. They do not "
        "by themselves prove the ecological cause of every "
        "change or establish that an ecosystem has fully recovered."
    )

st.markdown(
    "<div style='text-align: center; font-size: 12px; margin-top: 40px;'>"
    "Made by CZ."
    "</div>",
    unsafe_allow_html=True,
)