import os
import pandas as pd
import json

# Define paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
csv_path = os.path.join(project_root, "data", "raw", "India_Flood_Inventory_v3.csv")
output_json_path = os.path.join(project_root, "data", "processed", "target_flood_dates.json")

print("Initializing IFI Database Extraction...")

if not os.path.exists(csv_path):
    print(f"ERROR: Cannot find {csv_path}. Make sure it is in the data/raw/ folder.")
    exit()

# Load the massive dataset
df = pd.read_csv(csv_path)

# Normalize column names to avoid trailing spaces and capitalization issues
df.columns = df.columns.str.strip().str.lower()

# Map our internal city names to the standard Indian district naming conventions
city_to_district = {
    "pune": ["pune"],
    "mumbai": ["mumbai", "mumbai suburban"],
    "bengaluru": ["bengaluru urban", "bangalore urban", "bengaluru"],
    "chennai": ["chennai"]
}

# Lock in the exact columns based on your provided schema
district_col = "districts"
start_col = "start date"
end_col = "end date"

extracted_dates = {}

# Process each city
for city_key, district_names in city_to_district.items():
    # Filter the dataframe for the specific district. 
    # We use na=False to drop empty rows so the string matcher doesn't crash
    city_data = df[df[district_col].str.lower().isin(district_names) == True].copy()
    
    if city_data.empty:
        print(f"  -> WARNING: No flood records found for {city_key.upper()} in the 'Districts' column.")
        continue
        
    # Convert start dates to proper datetime objects so we can sort them chronologically
    city_data[start_col] = pd.to_datetime(city_data[start_col], errors='coerce')
    
    # Sort by date descending (newest floods first) and drop any rows with corrupted dates
    city_data = city_data.dropna(subset=[start_col]).sort_values(by=start_col, ascending=False)
    
    if city_data.empty:
        continue
        
    # Grab the most recent major flood event
    latest_flood = city_data.iloc[0]
    
    # Extract clean string formats (YYYY-MM-DD)
    start_dt = latest_flood[start_col]
    extracted_dates[city_key] = {
        "start": start_dt.strftime('%Y-%m-%d'),
        "end": (start_dt + pd.Timedelta(days=12)).strftime('%Y-%m-%d')
    }
    
    print(f"  -> {city_key.upper()}: Locked in flood event starting {extracted_dates[city_key]['start']}")

# Save the dynamic JSON file
with open(output_json_path, 'w') as f:
    json.dump(extracted_dates, f, indent=4)

print(f"\nSuccess! Dynamic flood dates saved to: {output_json_path}")