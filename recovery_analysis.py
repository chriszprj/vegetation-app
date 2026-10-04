def analyze_recovery(ndvi_results, fire_year, fire_date=None):
    """Analyze vegetation recovery from yearly NDVI observations."""

    if not ndvi_results:
        raise ValueError("No NDVI results available.")

    pre_fire = []
    post_fire = []

    for year, result in ndvi_results.items():
        date = result.get("observation_date")

        if fire_date and date:
            if date < fire_date:
                pre_fire.append((year, result))
            else:
                post_fire.append((year, result))
        elif year < fire_year:
            pre_fire.append((year, result))
        else:
            post_fire.append((year, result))

    # Pre-fire reference
    if pre_fire:
        ref_year, ref = max(
            pre_fire,
            key=lambda x: x[1].get("observation_date") or x[0]
        )
        reference_ndvi = ref["mean"]
        reference_date = ref.get("observation_date")
    else:
        ref_year = reference_ndvi = reference_date = None

    # Fire-year post-fire observation
    fire_obs = [
        (year, result)
        for year, result in post_fire
        if year == fire_year
    ]

    if fire_obs:
        fire_result_year, fire_result = min(
            fire_obs,
            key=lambda x: x[1].get("observation_date") or x[0]
        )
        fire_ndvi = fire_result["mean"]
        fire_date_result = fire_result.get("observation_date")
    else:
        fire_result_year = fire_ndvi = fire_date_result = None

    # Minimum post-fire condition
    if post_fire:
        min_year, min_result = min(
            post_fire,
            key=lambda x: x[1]["mean"]
        )
        minimum_ndvi = min_result["mean"]
        minimum_date = min_result.get("observation_date")
    else:
        min_year = minimum_ndvi = minimum_date = None

    # Latest post-fire condition
    if post_fire:
        latest_year, latest_result = max(
            post_fire,
            key=lambda x: x[1].get("observation_date") or x[0]
        )
        latest_ndvi = latest_result["mean"]
        latest_date = latest_result.get("observation_date")
    else:
        latest_year = latest_ndvi = latest_date = None

    # Change from pre-fire to latest
    if reference_ndvi is not None and latest_ndvi is not None:
        total_change = latest_ndvi - reference_ndvi
    else:
        total_change = None

    # Recovery toward pre-fire condition
    if (
        reference_ndvi is not None
        and minimum_ndvi is not None
        and latest_ndvi is not None
        and reference_ndvi > minimum_ndvi
    ):
        recovery_percent = (
            (latest_ndvi - minimum_ndvi)
            / (reference_ndvi - minimum_ndvi)
        ) * 100

        recovery_percent = max(0, min(100, recovery_percent))
    else:
        recovery_percent = None

    return {
        "reference_year": ref_year,
        "reference_date": reference_date,
        "reference_ndvi": reference_ndvi,

        "fire_year": fire_result_year,
        "fire_observation_date": fire_date_result,
        "fire_ndvi": fire_ndvi,

        "minimum_post_fire_year": min_year,
        "minimum_post_fire_date": minimum_date,
        "minimum_post_fire_ndvi": minimum_ndvi,

        "latest_year": latest_year,
        "latest_date": latest_date,
        "latest_ndvi": latest_ndvi,

        "total_change": total_change,
        "recovery_percent": recovery_percent
    }