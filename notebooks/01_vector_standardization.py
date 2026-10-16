import geopandas as gpd
import fiona
import os
import glob
import zipfile
import tempfile

fiona.drvsupport.supported_drivers['KML'] = 'rw'

cities = ["pune", "mumbai", "bengaluru", "chennai"]
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
base_raw_dir = os.path.join(project_root, "data", "raw")
base_processed_dir = os.path.join(project_root, "data", "processed")

print(f"System Check: Looking for data in -> {base_raw_dir}")

def process_gdf(gdf, output_path, filename):
    if gdf is not None and not gdf.empty:
        if gdf.crs is None or gdf.crs.to_string() != 'EPSG:4326':
            print(f"  -> Reprojecting to EPSG:4326...")
            gdf = gdf.to_crs("EPSG:4326")
        gdf.to_file(output_path, driver="GeoJSON")
        print(f"  -> Success! Saved as: {os.path.basename(output_path)}")

def standardize_city_vectors(city):
    print(f"\n--- Processing vectors for {city.upper()} ---")
    raw_dir = os.path.join(base_raw_dir, city)
    processed_dir = os.path.join(base_processed_dir, city)
    
    if not os.path.exists(raw_dir): return
    os.makedirs(processed_dir, exist_ok=True)
    
    target_files = [os.path.join(raw_dir, f) for f in os.listdir(raw_dir) if f.lower().endswith(('.kml', '.kmz', '.geojson'))]

    for file_path in target_files:
        filename = os.path.basename(file_path)
        base_name = filename.rsplit('.', 1)[0]
        print(f"Loading: {filename}")
        
        try:
            # Handle KMZ
            if file_path.lower().endswith('.kmz'):
                with tempfile.TemporaryDirectory() as tmpdirname:
                    with zipfile.ZipFile(file_path, 'r') as kmz:
                        kml_files = [f for f in kmz.namelist() if f.lower().endswith('.kml')]
                        if kml_files:
                            extracted_path = kmz.extract(kml_files[0], path=tmpdirname)
                            layers = fiona.listlayers(extracted_path)
                            for layer in layers:
                                gdf = gpd.read_file(extracted_path, driver='KML', layer=layer)
                                out_name = f"{base_name}_{layer.replace(' ', '_')}_standardized.geojson"
                                process_gdf(gdf, os.path.join(processed_dir, out_name), filename)
            
            # Handle KML (Now with Multi-Layer Support)
            elif file_path.lower().endswith('.kml'):
                layers = fiona.listlayers(file_path)
                for layer in layers:
                    print(f"  -> Extracting layer: {layer}")
                    gdf = gpd.read_file(file_path, driver='KML', layer=layer)
                    # If there's only one layer, keep the name simple. If multiple, append layer name.
                    out_name = f"{base_name}_standardized.geojson" if len(layers) == 1 else f"{base_name}_{layer.replace(' ', '_')}_standardized.geojson"
                    process_gdf(gdf, os.path.join(processed_dir, out_name), filename)
                    
            # Handle GeoJSON
            elif file_path.lower().endswith('.geojson'):
                gdf = gpd.read_file(file_path)
                process_gdf(gdf, os.path.join(processed_dir, f"{base_name}_standardized.geojson"), filename)

        except Exception as e:
            print(f"  -> ERROR processing {filename}: {e}")

for city in cities:
    standardize_city_vectors(city)

print("\nPipeline Step 1 Complete: All civic vector data standardized!")