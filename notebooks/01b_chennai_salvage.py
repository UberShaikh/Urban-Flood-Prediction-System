import os
import geopandas as gpd
from shapely.geometry import LineString
from bs4 import BeautifulSoup

# Define paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
kml_path = os.path.join(project_root, "data", "raw", "chennai", "chennai_stormwater_drains.kml")
output_path = os.path.join(project_root, "data", "processed", "chennai", "chennai_stormwater_drains_standardized.geojson")

print("Initiating brute-force XML extraction for Chennai SWD...")

if not os.path.exists(kml_path):
    print(f"ERROR: Could not find {kml_path}")
    exit()

# 1. Open the broken KML file as raw text, ignoring encoding errors
with open(kml_path, 'r', encoding='utf-8', errors='ignore') as f:
    soup = BeautifulSoup(f, 'xml')

salvaged_lines = []

# 2. Hunt down every 'Placemark' tag (which represents a drain on the map)
placemarks = soup.find_all('Placemark')
print(f"Found {len(placemarks)} potential features. Extracting geometries...")

for placemark in placemarks:
    # Stormwater drains are drawn as LineStrings
    linestring = placemark.find('LineString')
    
    if linestring:
        coords_tag = linestring.find('coordinates')
        if coords_tag:
            coords_text = coords_tag.text.strip()
            
            # KML coordinates are formatted as: "lon,lat,elevation lon,lat,elevation"
            points = []
            for coord_set in coords_text.split():
                parts = coord_set.split(',')
                # We only need Lon and Lat (ignore elevation if it exists)
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        points.append((lon, lat))
                    except ValueError:
                        continue # Skip if the text is corrupted
            
            # A valid line must have at least 2 points (a start and an end)
            if len(points) >= 2:
                salvaged_lines.append(LineString(points))

# 3. Rebuild the map from scratch using Shapely and Geopandas
if salvaged_lines:
    print(f"Successfully rebuilt {len(salvaged_lines)} drainage lines. Formatting map...")
    gdf = gpd.GeoDataFrame(geometry=salvaged_lines, crs="EPSG:4326")
    
    # Export as a perfectly clean, standardized GeoJSON
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"Success! Salvaged data saved to: {output_path}")
else:
    print("Failed to salvage any lines. The file might be completely empty.")