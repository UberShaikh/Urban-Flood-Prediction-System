import os
import json
import glob
import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

@router.get("/scenario/{city}")
def get_city_scenario(city: str):
    city = city.lower()
    
    # Defaults
    configs = {
        "mumbai": {"elevation": 14, "drain_distance": 250},
        "pune": {"elevation": 560, "drain_distance": 600},
        "chennai": {"elevation": 6, "drain_distance": 180},
        "bengaluru": {"elevation": 920, "drain_distance": 850},
    }
    cfg = configs.get(city, {"elevation": 50, "drain_distance": 500})
    
    # 1. Look up target flood date
    dates_file = os.path.join(DATA_DIR, "processed", "target_flood_dates.json")
    try:
        with open(dates_file, "r") as f:
            flood_dates = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Missing target_flood_dates.json")
        
    if city not in flood_dates:
        raise HTTPException(status_code=404, detail="City flood date not found")
        
    start_date = pd.to_datetime(flood_dates[city]["start"])
    
    # 2. Look up historical rainfall CSV
    raw_city_dir = os.path.join(DATA_DIR, "raw", city)
    csv_files = glob.glob(os.path.join(raw_city_dir, "*hourly_rain*.csv"))
    
    if not csv_files:
        raise HTTPException(status_code=404, detail=f"No rainfall CSV found for {city}")
        
    # Read the data
    df = pd.read_csv(csv_files[0])
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df = df.sort_values("Datetime")
    
    # 3. Extract exactly 72 hours leading up to the flood start
    # We want from (start_date - 72 hours) to start_date
    end_time = start_date
    start_time = end_time - pd.Timedelta(hours=72)
    
    mask = (df["Datetime"] >= start_time) & (df["Datetime"] < end_time)
    df_window = df[mask].copy()
    
    if df_window.empty:
        raise HTTPException(status_code=404, detail="No historical rain data matches the 72h window before the flood date.")
    
    # Interpolate if missing values
    df_window["Precipitation_mm"] = df_window["Precipitation_mm"].interpolate(method="linear").fillna(0)
    
    # Only keep 72 hours just in case
    df_window = df_window.tail(72)
    
    rain_data = df_window["Precipitation_mm"].tolist()
    time_labels = df_window["Datetime"].dt.strftime("%H:00").tolist()
    
    total_rain = sum(rain_data)
    
    # Sample to 24 points visually (every 3 hours) for the sparkline chart
    visual_series = []
    for i in range(0, len(rain_data), 3):
        chunk_rain = sum(rain_data[i:i+3])
        visual_series.append({
            "h": time_labels[i],
            "mm": round(chunk_rain, 1)
        })
        
    if not visual_series:
        visual_series = [{"h": "00:00", "mm": 0}]

    return {
        "city": city,
        "flood_date": start_date.strftime("%Y-%m-%d"),
        "elevation_m": cfg["elevation"],
        "drain_distance_m": cfg["drain_distance"],
        "historical_total_mm": round(total_rain, 1),
        "rainfall_72h": rain_data,
        "visual_series": visual_series
    }
