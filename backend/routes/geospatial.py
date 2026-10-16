import os
import pandas as pd
import requests
import datetime
import xml.etree.ElementTree as ET
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from ml_engine.flood_risk_engine import (
    run_flood_risk_pipeline,
    calculate_threshold_elevation,
    calculate_area_risk_score,
    CITY_PROFILES,
)

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "Data_Urban")

CITIES_CONFIG = {
    "pune":      {"lat": 18.5204, "lon": 73.8567},
    "mumbai":    {"lat": 19.0760, "lon": 72.8777},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "chennai":   {"lat": 13.0827, "lon": 80.2707},
}

FILE_MAPPING = {
    "mumbai":    "mumbai_flood_data.csv",
    "bengaluru": "bangalore_flood_data.csv",
    "chennai":   "chennai_flood_data.csv",
    "pune":      "pune_flood_data.csv",
}

NUMERIC_COLS = [
    "Urban_Density_sqkm", "Flood_Hotspot", "Near_Coastline",
    "Near_River", "Water_Logging_Zones", "Historical_Rainfall_mm",
    "Elevation_m", "Drain_Distance_m", "Lat", "Lon",
]


# ─────────────────────────────────────────────────────────────────────────────
# KML → GeoJSON converter (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def kml_to_geojson(kml_path: str):
    if not os.path.exists(kml_path):
        return None
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        features = []
        for placemark in root.findall(f".//{ns}Placemark"):
            name_node = placemark.find(f"{ns}name")
            name = name_node.text if name_node is not None else "Unnamed"
            ls = placemark.find(f".//{ns}LineString")
            if ls is not None:
                coords_node = ls.find(f"{ns}coordinates")
                if coords_node is not None:
                    points = []
                    for pair in coords_node.text.strip().split():
                        parts = pair.split(",")
                        if len(parts) >= 2:
                            try:
                                points.append([float(parts[0]), float(parts[1])])
                            except Exception:
                                continue
                    if points:
                        features.append({
                            "type": "Feature",
                            "properties": {"name": name, "type": "drain"},
                            "geometry": {"type": "LineString", "coordinates": points},
                        })
            poly = placemark.find(f".//{ns}Polygon")
            if poly is not None:
                coords_node = poly.find(f".//{ns}outerBoundaryIs//{ns}coordinates")
                if coords_node is not None:
                    points = []
                    for pair in coords_node.text.strip().split():
                        parts = pair.split(",")
                        if len(parts) >= 2:
                            try:
                                points.append([float(parts[0]), float(parts[1])])
                            except Exception:
                                continue
                    if points:
                        features.append({
                            "type": "Feature",
                            "properties": {"name": name, "type": "catchment"},
                            "geometry": {"type": "Polygon", "coordinates": [points]},
                        })
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        print(f"[KML Error] {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Weather fetcher (unchanged logic, kept here for geospatial context)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_weather(city: str, sim_date: Optional[str] = None) -> dict:
    cfg = CITIES_CONFIG.get(city.lower(), CITIES_CONFIG["mumbai"])
    print(f"[geospatial] Fetching weather for {city} | SimDate: {sim_date or 'LIVE'}")

    if sim_date:
        url = "https://archive-api.open-meteo.com/v1/archive"
        dt_sim = datetime.datetime.strptime(sim_date, "%Y-%m-%d")
        params = {
            "latitude": cfg["lat"], "longitude": cfg["lon"],
            "start_date": (dt_sim - datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
            "end_date":   (dt_sim + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            "hourly": "precipitation,relative_humidity_2m,temperature_2m,wind_speed_10m",
            "timezone": "Asia/Kolkata",
        }
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": cfg["lat"], "longitude": cfg["lon"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "hourly": "precipitation,precipitation_probability",
            "past_hours": 72, "forecast_hours": 24,
            "timezone": "Asia/Kolkata",
        }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        hourly = data.get("hourly", {})
        precip = hourly.get("precipitation", [])

        if sim_date:
            day_precip = precip[72:96] or [0] * 24
            peak_idx = 72 + day_precip.index(max(day_precip))
            return {
                "current_rainfall": precip[peak_idx],
                "rainfall_1h":  precip[peak_idx],
                "rainfall_3h":  sum(precip[max(peak_idx-2, 72):peak_idx+1]),
                "rainfall_24h": sum(day_precip),
                "rainfall_72h": sum(precip[:72]),
                "precipitation_probability": 90 if max(day_precip) > 2 else 15,
                "humidity":     hourly.get("relative_humidity_2m", [80]*96)[peak_idx],
                "wind_speed":   hourly.get("wind_speed_10m", [10]*96)[peak_idx],
                "temperature":  hourly.get("temperature_2m", [28]*96)[peak_idx],
            }

        current = data.get("current", {})
        prob = hourly.get("precipitation_probability", [])
        return {
            "current_rainfall": current.get("precipitation", 0),
            "rainfall_1h":  sum(precip[71:72]),
            "rainfall_3h":  sum(precip[69:72]),
            "rainfall_24h": sum(precip[48:72]),
            "rainfall_72h": sum(precip[:72]),
            "precipitation_probability": prob[72] if len(prob) > 72 else 50,
            "humidity":    current.get("relative_humidity_2m", 80),
            "wind_speed":  current.get("wind_speed_10m", 10),
            "temperature": current.get("temperature_2m", 28),
        }
    except Exception as e:
        print(f"[geospatial] Weather Fetch Error: {e}")
        return {
            "current_rainfall": 0, "rainfall_1h": 0, "rainfall_3h": 0,
            "rainfall_24h": 0, "rainfall_72h": 0,
            "precipitation_probability": 0, "humidity": 80,
            "wind_speed": 10, "temperature": 28,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load + clean CSV
# ─────────────────────────────────────────────────────────────────────────────

def _load_city_csv(city_name: str) -> pd.DataFrame:
    filename = FILE_MAPPING.get(city_name.lower())
    if not filename:
        raise HTTPException(status_code=404, detail="City data not found")
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    df = pd.read_csv(file_path)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Helper: get flood probability for a city (calls live + predict internally)
# ─────────────────────────────────────────────────────────────────────────────

def _get_city_flood_probability(city: str, sim_date: Optional[str] = None) -> tuple:
    """Returns (flood_probability, rainfall_72h_total_mm)."""
    try:
        from routes.live import get_live_data
        from routes.predict import predict_flood, PredictionRequest
        weather = get_live_data(city, sim_date=sim_date)
        req = PredictionRequest(
            rainfall_72h=weather["rainfall_72h"],        # list of 72 hourly values
            forecast_24h=weather["total_24h_forecast"],
            elevation_m=weather["elevation_m"],
            drain_distance_m=weather["drain_distance_m"],
            city=city,
        )
        pred = predict_flood(req)
        # total_72h_rain is the float sum — NOT the list
        return float(pred["flood_probability"]), float(weather["total_72h_rain"])
    except Exception as e:
        print(f"[geospatial] Flood prob fetch failed for {city}: {e}")
        return 0.0, 0.0


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /city-areas/{city_name}
# Returns all areas ranked by refined flood risk score
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/city-areas/{city_name}")
def get_city_areas(city_name: str, sim_date: Optional[str] = None):
    city = city_name.lower()
    df = _load_city_csv(city)
    areas = df.to_dict(orient="records")

    # Get current flood probability + 72h rainfall for this city
    flood_prob, rainfall_72h = _get_city_flood_probability(city, sim_date)

    # Run full pipeline: threshold → score → rank
    pipeline_result = run_flood_risk_pipeline(city, flood_prob, rainfall_72h, areas)
    threshold_info  = pipeline_result["threshold_info"]
    ranked_areas    = pipeline_result["ranked_areas"]

    # Normalise lat/lng keys for frontend compatibility
    output = []
    for area in ranked_areas:
        area["lat"] = float(area.get("Lat", 0))
        area["lng"] = float(area.get("Lon", 0))
        # Keep calculated_risk as alias for backward compat with CommandCenter.jsx
        area["calculated_risk"] = area["risk_score"]
        area["risk_category"]   = area["category"]
        output.append(area)

    return {
        "areas": output,
        "threshold_info": threshold_info,
        "summary": pipeline_result["summary"],
        "flood_probability": flood_prob,
        "rainfall_72h": rainfall_72h,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /predict-area
# Single-area prediction with full component breakdown
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/predict-area")
def predict_area_risk(city: str, area_name: str, sim_date: Optional[str] = None):
    city = city.lower()
    df = _load_city_csv(city)
    area_row = df[df["Area"] == area_name]
    if area_row.empty:
        raise HTTPException(status_code=404, detail="Area not found")

    area_data = area_row.iloc[0].to_dict()
    for k, v in area_data.items():
        try:
            area_data[k] = float(v)
        except Exception:
            pass

    # Get flood probability and 72h rainfall total for this city right now
    flood_prob, rainfall_72h = _get_city_flood_probability(city, sim_date)

    # Calculate threshold using the float rainfall total
    threshold_info = calculate_threshold_elevation(city, flood_prob, rainfall_72h)
    threshold_m    = threshold_info["threshold_elevation_m"]

    # Score this area — flood_probability MUST be passed so scalar is applied
    prediction = calculate_area_risk_score(area_data, threshold_m, city, flood_prob)

    print(f"[predict-area] {city}/{area_name} flood_prob={flood_prob} "
          f"rain={rainfall_72h}mm thresh={threshold_m}m score={prediction['risk_score']}%")

    return {
        "area":              area_name,
        "city":              city,
        "prediction":        prediction,
        "threshold_info":    threshold_info,
        "flood_probability": flood_prob,
        "rainfall_72h":      rainfall_72h,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /city-risk-ranking
# Cross-city area ranking — all 4 cities, all areas, sorted by risk score
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/city-risk-ranking")
def get_city_risk_ranking(sim_date: Optional[str] = None):
    """
    Computes risk scores for every area across all 4 cities and returns
    a unified ranked list. Useful for cross-city comparison.
    """
    all_areas = []

    for city in ["mumbai", "chennai", "bengaluru", "pune"]:
        try:
            df = _load_city_csv(city)
            areas = df.to_dict(orient="records")
            flood_prob, rainfall_72h = _get_city_flood_probability(city, sim_date)
            result = run_flood_risk_pipeline(city, flood_prob, rainfall_72h, areas)

            for area in result["ranked_areas"]:
                all_areas.append({
                    "city":              city.upper(),
                    "area":              area.get("Area", ""),
                    "risk_score":        area["risk_score"],
                    "category":          area["category"],
                    "category_color":    area["category_color"],
                    "elevation_m":       area.get("Elevation_m", 0),
                    "threshold_m":       area["threshold_used_m"],
                    "elevation_deficit": area["elevation_deficit_m"],
                    "urban_density":     area.get("Urban_Density_sqkm", 0),
                    "waterlog_zones":    area.get("Water_Logging_Zones", 0),
                    "flood_hotspot":     area.get("Flood_Hotspot", 0),
                    "component_scores":  area["component_scores"],
                    "explanations":      area["explanations"],
                    "city_flood_prob":   flood_prob,
                    "lat":               float(area.get("Lat", 0)),
                    "lng":               float(area.get("Lon", 0)),
                })
        except Exception as e:
            print(f"[city-risk-ranking] Failed for {city}: {e}")

    all_areas.sort(key=lambda x: x["risk_score"], reverse=True)
    for i, a in enumerate(all_areas, start=1):
        a["global_rank"] = i

    return {
        "ranked_areas": all_areas,
        "total":        len(all_areas),
        "critical":     len([a for a in all_areas if a["category"] == "Critical"]),
        "high":         len([a for a in all_areas if a["category"] == "High"]),
        "moderate":     len([a for a in all_areas if a["category"] == "Moderate"]),
        "low":          len([a for a in all_areas if a["category"] == "Low"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /threshold/{city}
# Expose threshold calculation directly for debugging / UI display
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/threshold/{city}")
def get_city_threshold(city: str, sim_date: Optional[str] = None):
    city = city.lower()
    if city not in CITY_PROFILES:
        raise HTTPException(status_code=404, detail="City not supported")
    flood_prob, rainfall_72h = _get_city_flood_probability(city, sim_date)
    return calculate_threshold_elevation(city, flood_prob, rainfall_72h)


# ─────────────────────────────────────────────────────────────────────────────
# Static file endpoints (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cities")
def get_available_cities():
    if not os.path.exists(DATA_DIR):
        return []
    return [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]


@router.get("/data/{file_path:path}")
def serve_geospatial_data(file_path: str):
    full_path = os.path.join(DATA_DIR, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File {file_path} not found")
    return FileResponse(full_path)


@router.get("/drainage/{city}")
def get_city_drainage(city: str):
    city = city.lower()
    drain_dir = os.path.join(DATA_DIR, "drainage")
    paths = {
        "mumbai":    "Mumbai/mumbai_micro_watersheds.geojson",
        "bengaluru": "Bengluru/bengaluru stormwater map/bengaluru_stormwater_drains_map.kml",
        "chennai":   "Chennai/SWD chennai/chennai_stormwater_drains.kml",
        "pune":      "Pune/Pune Stormwater Drains/pune_river_map.kml",
    }
    relative_path = paths.get(city)
    if not relative_path:
        raise HTTPException(status_code=404, detail=f"Drainage path not mapped for {city}")
    full_path = os.path.join(drain_dir, relative_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File not found at {full_path}")
    if full_path.endswith(".geojson"):
        import json
        with open(full_path, "r") as f:
            return json.load(f)
    if full_path.endswith(".kml"):
        geojson = kml_to_geojson(full_path)
        if geojson:
            return geojson
        raise HTTPException(status_code=500, detail="Failed to parse KML drainage data")
    raise HTTPException(status_code=400, detail="Unsupported drainage file format")
