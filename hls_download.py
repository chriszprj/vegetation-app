import os
import earthaccess


def download_scene(scene_result, output_dir):
    """
    Download only the HLS bands required by the analysis.

    Required files:
        B04   -> Red
        B8A   -> NIR
        B11   -> SWIR
        Fmask -> Quality mask

    Files are downloaded into the temporary analysis directory.
    """

    selected_urls = {
        "red": None,
        "nir": None,
        "swir": None,
        "fmask": None
    }

    # --------------------------------------------------
    # Find the required asset URLs
    # --------------------------------------------------

    for url in scene_result.data_links():

        filename = os.path.basename(url)

        if ".B04." in filename:
            selected_urls["red"] = url

        elif ".B8A." in filename:
            selected_urls["nir"] = url

        elif ".B11." in filename:
            selected_urls["swir"] = url

        elif ".Fmask." in filename:
            selected_urls["fmask"] = url

    # --------------------------------------------------
    # Make sure all required assets were found
    # --------------------------------------------------

    missing = [
        band
        for band, url in selected_urls.items()
        if url is None
    ]

    if missing:
        raise RuntimeError(
            "Could not find required HLS assets: "
            + ", ".join(missing)
        )

    # --------------------------------------------------
    # Download only the four required files
    # --------------------------------------------------

    session = earthaccess.get_requests_https_session()

    selected_files = {}

    for band, url in selected_urls.items():

        filename = os.path.basename(url)

        output_path = os.path.join(
            output_dir,
            filename
        )

        with session.get(url, stream=True) as response:

            response.raise_for_status()

            with open(output_path, "wb") as file:

                for chunk in response.iter_content(
                    chunk_size=64 * 1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

        selected_files[band] = output_path

    return selected_files