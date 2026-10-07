This Python-based vegetation recovery tracker app uses satellite imagery to analyze vegetation changes in a selected wildfire-affected area.

Users can search for and select any recent fire (preferably from 2015 onward) to analyze. This application locates the fire's geographic perimeter, retrieves satellite imagery for the surrounding area, and analyzes vegetation conditions across multiple years before (up to 2 years preceding) and after (up to 10 years afterward) the fire.

Features:
1. Wildfire Search: Users can search for wildfire events and select a specific fire to analyze.
2. Fire Perimeter Mapping: The application will display the selected wildfire's geographic perimeter and area on an interactive map.
3. Multi-Year Satellite Analysis: Retrieves satellite imagery from two years before the fire through up to ten years after it, depending on available data.
4. NDVI Analysis: Calculates vegetation condition based on satellite imagery for each available year and tracks changes over time.
5. NBR and Burn Severity Analysis: Uses NBR and dNBR to estimate how strongly the landscape was affected by the fire.
6. Interactive Results: Presents the analysis through maps, tables, charts, and summary statistics so changes can be examined visually.

Technologies:
The application uses NASA Earthdata as its source for satellite imagery and the earthaccess Python library to search for and access the data programmatically.

From NASA Earthdata, we utilize its Harmonized Landsat and Sentinel-2 (HLS) project, which gathers information from two satellite teams: Landsat 8/Landsat 9 and Sentinel-2A/2B/2C. These databases provide key spectral bands for visible light/thermal infrared/red edge bands that this application analyzes.

Analysis is done through several processes:
1) Calculating NDVI (normalized-difference-vegetation-index): NDVI uses red and near-infrared reflectance to estimate vegetation condition, with higher values generally representing healthier or denser vegetation. The application calculates yearly NDVI within the fire perimeter to track vegetation changes before and after the wildfire.

NDVI = (NIR − Red) / (NIR + Red)
NIR = near-infrared, reflected heavily by strong vegetation
Red = visible-light, absorbed by vegetation for photosynthesis

2) Calculating NBR (Normalized Burn Ratio): NBR uses near-infrared and shortwave-infrared reflectance to highlight changes associated with burned areas. The application uses NBR to compare surface conditions before and after the fire.
3) Calculating dNBR (Differenced Normalized Burn Ratio): dNBR measures the difference between pre-fire and post-fire NBR values, estimating how much the landscape changed because of the fire. The application uses this value to classify burn severity.
