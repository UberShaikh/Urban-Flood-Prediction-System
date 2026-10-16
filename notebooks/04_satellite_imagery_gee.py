import ee
import os
import requests
import zipfile
import io
import json

# ==========================================
# STEP 1: AUTHENTICATION & INITIALIZATION
# ==========================================
PROJECT_ID = "project-b484fa4f-a5a3-4f84-837"

print("Initializing Dynamic Google Earth Engine Pipeline...")
try:
    # Initialize with the project ID. This requires that 'gcloud auth application-default login' 
    # or 'earthengine authenticate' has been run once on this machine.
    ee.Initialize(project=PROJECT_ID)
    print("Earth Engine Initialized successfully!")
except Exception as e:
    print(f"CRITICAL ERROR: Earth Engine failed to initialize. {e}")
    print("Ensure you have authenticated via 'earthengine authenticate' in your terminal.")
    exit(1)


# ==========================================
# STEP 2: PATH SETUP & DATA LOADING
# ==========================================
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
base_raw_dir = os.path.join(project_root, "data", "raw")
json_path = os.path.join(project_root, "data", "processed", "target_flood_dates.json")

# Load the dynamically extracted dates
if not os.path.exists(json_path):
    print(f"ERROR: {json_path} not found. Run 04a_extract_flood_dates.py first.")
    exit()

with open(json_path, 'r') as f:
    flood_events = json.load(f)

# Define tighter Bounding Boxes to bypass GEE 50MB sync limit at 10m scale (approx 10x10 km)
city_bounds = {
    "pune": ee.Geometry.Rectangle([73.80, 18.48, 73.90, 18.58]),
    "mumbai": ee.Geometry.Rectangle([72.80, 19.00, 72.90, 19.10]),
    "bengaluru": ee.Geometry.Rectangle([77.55, 12.92, 77.65, 13.02]),
    "chennai": ee.Geometry.Rectangle([80.20, 13.00, 80.30, 13.10])
}

# ==========================================
# STEP 3: THE SATELLITE EXTRACTION ENGINE
# ==========================================
def download_sar_imagery(city):
    if city not in flood_events:
        print(f"--- Skipping {city.upper()}: No dynamic date data found ---")
        return
        
    print(f"\n--- Extracting Sentinel-1 SAR for {city.upper()} ---")
    raw_dir = os.path.join(base_raw_dir, city)
    os.makedirs(raw_dir, exist_ok=True)
    
    roi = city_bounds[city]
    start_date = flood_events[city]["start"]
    end_date = flood_events[city]["end"]
    
    print(f"  -> Querying Copernicus database for dates: {start_date} to {end_date}")
    
    # Filter for SAR VV and VH polarizations (Sen1Floods11 compatibility)
    collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
        .select(['VV', 'VH'])

    # SAFETY CHECK: Did the satellite actually record anything?
    image_count = collection.size().getInfo()
    if image_count == 0:
        print("  -> WARNING: The satellite did not record any data for this location during these dates.")
        print("  -> Skipping extraction to prevent pipeline crash.")
        return

    flood_image = collection.mosaic().clip(roi)

    try:
        download_url = flood_image.getDownloadURL({
            'scale': 10, 
            'crs': 'EPSG:4326',
            'region': roi,
            'format': 'GEO_TIFF'
        })
        
        print("  -> Download link generated. Pulling data...")
        
        response = requests.get(download_url)
        response.raise_for_status()
        
        extracted_path = os.path.join(raw_dir, f"{city}_flood_sar_{start_date}.tif")
        
        # BULLETPROOF SAVE LOGIC: Handle both Zipped and Unzipped files
        try:
            # Assume it's a zip file first
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                tif_filename = z.namelist()[0]
                with open(extracted_path, 'wb') as f:
                    f.write(z.read(tif_filename))
        except zipfile.BadZipFile:
            # If it's not a zip file, it's the raw .tif. Save it directly!
            with open(extracted_path, 'wb') as f:
                f.write(response.content)
                
        print(f"  -> Success! Saved SAR imagery to: {city}_flood_sar_{start_date}.tif")

    except Exception as e:
        print(f"  -> ERROR during Earth Engine extraction: {e}")

# ==========================================
# STEP 4: EXECUTE
# ==========================================
for city in city_bounds.keys():
    download_sar_imagery(city)

print("\nPipeline Step 4 Complete: Ground Truth Satellite Data Acquired Dynamically!")