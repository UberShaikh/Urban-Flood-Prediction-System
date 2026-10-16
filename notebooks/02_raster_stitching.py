import os
import glob
import rasterio
from rasterio.merge import merge

# Define paths
cities = ["pune", "mumbai", "bengaluru", "chennai"]
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
base_raw_dir = os.path.join(project_root, "data", "raw")
base_processed_dir = os.path.join(project_root, "data", "processed")

print(f"System Check: Looking for elevation tiles in -> {base_raw_dir}")

def stitch_city_dem(city):
    print(f"\n--- Processing Topography for {city.upper()} ---")
    raw_dir = os.path.join(base_raw_dir, city)
    processed_dir = os.path.join(base_processed_dir, city)
    
    if not os.path.exists(raw_dir): 
        return
        
    os.makedirs(processed_dir, exist_ok=True)
    
    # Find all .tif files in the city's raw folder
    search_path = os.path.join(raw_dir, "*.tif")
    dem_files = glob.glob(search_path)
    
    if not dem_files:
        print(f"  -> No .tif files found. Skipping.")
        return
        
    print(f"  -> Found {len(dem_files)} tiles. Commencing stitch operation...")
    
    src_files_to_mosaic = []
    try:
        # Open all the tiles
        for fp in dem_files:
            src = rasterio.open(fp)
            src_files_to_mosaic.append(src)
            
        # Mathematically merge them
        mosaic, out_trans = merge(src_files_to_mosaic)
        
        # Copy the metadata from the first tile
        out_meta = src_files_to_mosaic[0].meta.copy()
        
        # Update the metadata with the massive new dimensions
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans
        })
        
        # Define output path
        output_filename = f"{city}_seamless_dem.tif"
        output_path = os.path.join(processed_dir, output_filename)
        
        # Write the massive merged map to the processed folder
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)
            
        print(f"  -> Success! Seamless map saved as: {output_filename}")
        
    except Exception as e:
        print(f"  -> ERROR during stitching: {e}")
        
    finally:
        # Prevent memory leaks by closing all files
        for src in src_files_to_mosaic:
            src.close()

# Execute the loop
for city in cities:
    stitch_city_dem(city)

print("\nPipeline Step 2 Complete: All topography maps stitched and ready for modeling!")