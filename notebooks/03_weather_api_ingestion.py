import os
import time
import requests
import pandas as pd

# Define paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
base_raw_dir = os.path.join(project_root, "data", "raw")

print("Initializing Open-Meteo API connection...")

# 1. Define the Quad-City coordinates (Exact lat/lon for the API)
cities = {
    "pune": {"lat": 18.5204, "lon": 73.8567},
    "mumbai": {"lat": 19.0760, "lon": 72.8777},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "chennai": {"lat": 13.0827, "lon": 80.2707}
}

# 2. Define the training timeframe (e.g., Last 5 years to capture recent extremes)
# You can easily change these dates to pull more or less data later
start_date = "2019-01-01"
end_date = "2024-01-01"

def fetch_historical_rain(city_name, coords):
    print(f"\n--- Fetching hourly precipitation for {city_name.upper()} ---")
    
    # Ensure the city's raw directory exists
    city_raw_dir = os.path.join(base_raw_dir, city_name)
    os.makedirs(city_raw_dir, exist_ok=True)
    
    # Open-Meteo Historical Archive Endpoint
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata" # Lock to Indian Standard Time
    }
    
    try:
        # Ping the API
        response = requests.get(url, params=params)
        response.raise_for_status() # Will trigger an exception if the API rejects us
        
        data = response.json()
        
        # 3. Parse the JSON into a clean Pandas DataFrame
        df = pd.DataFrame({
            "Datetime": data['hourly']['time'],
            "Precipitation_mm": data['hourly']['precipitation']
        })
        
        # Convert string dates to actual datetime objects
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        
        # 4. Save to CSV
        output_filename = f"{city_name}_hourly_rain_{start_date}_to_{end_date}.csv"
        output_path = os.path.join(city_raw_dir, output_filename)
        
        df.to_csv(output_path, index=False)
        print(f"  -> Success! Saved {len(df)} hourly records to {output_filename}")
        
    except requests.exceptions.RequestException as e:
        print(f"  -> API ERROR for {city_name}: {e}")

# 5. Execute the automation loop
for city, coords in cities.items():
    fetch_historical_rain(city, coords)
    # Be polite to free APIs: Pause for 2 seconds between requests so we don't get IP banned
    time.sleep(2)

print("\nPipeline Step 3 Complete: All high-frequency weather data acquired!")