import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def build_ndvi_table(results, fire_year, fire_date):
    rows = []

    for year in sorted(results):
        result = results[year]

        if fire_date is None:
            relationship = (
                "Fire year"
                if year == fire_year
                else "Before fire"
                if year < fire_year
                else "After fire"
            )
        else:
            relationship = (
                "Pre-fire"
                if result["observation_date"] < fire_date
                else "Post-discovery"
            )

        rows.append({
            "Year": year,
            "Observation date": str(
                result["observation_date"]
            ),
            "Fire relationship": relationship,
            "Mean NDVI": result["mean"],
            "Median NDVI": result["median"],
            "Minimum NDVI": result["minimum"],
            "Maximum NDVI": result["maximum"],
            "Valid pixels": result["valid_pixels"],
        })

    return pd.DataFrame(rows)


def build_nbr_table(results):
    rows = []

    for year in sorted(results):
        result = results[year]

        rows.append({
            "Year": year,
            "Observation date": str(
                result["observation_date"]
            ),
            "Fire relationship": result["fire_relationship"],
            "Mean NBR": result["mean"],
            "Minimum NBR": result["minimum"],
            "Maximum NBR": result["maximum"],
            "Valid pixels": result["valid_pixels"],
        })

    return pd.DataFrame(rows)


def make_line_chart(results, value_key, title, y_title):
    available = [
        (year, results[year][value_key])
        for year in sorted(results)
        if results[year].get(value_key) is not None
    ]

    if not available:
        st.info(
            f"No {y_title} values are available to graph."
        )
        return

    years, values = zip(*available)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=list(years),
            y=list(values),
            mode="lines+markers",
            name=y_title,
            hovertemplate=(
                "Year: %{x}<br>"
                + y_title
                + ": %{y:.4f}"
                + "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=title,
        xaxis=dict(
            title="Year",
            tickmode="linear",
            dtick=1,
        ),
        yaxis=dict(title=y_title),
        hovermode="x unified",
        height=400,
        margin=dict(
            l=20,
            r=20,
            t=55,
            b=20,
        ),
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "scrollZoom": False,
            "displayModeBar": False,
        },
    )