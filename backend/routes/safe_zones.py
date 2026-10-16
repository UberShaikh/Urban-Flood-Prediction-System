"""
safe_zones.py — AquaAlert Evacuation Intelligence Engine
Routes:
  GET /api/v1/safe-zones/{city}
  GET /api/v1/safe-zones/{city}/recommendation

Integrates:
  • Hardcoded curated shelter data (moved from frontend)
  • Open-Elevation API (with in-memory cache)
  • Overpass API — dynamic nearby POI enrichment
  • Flood probability coupling (calls predict internally)
  • AI shelter scoring: elevation + occupancy + flood proximity + rainfall
"""

from fastapi import APIRouter, BackgroundTasks
from typing import Optional
import requests, math, time, datetime

router = APIRouter()

# ── IST timezone ─────────────────────────────────────────────────
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# ── In-memory caches ─────────────────────────────────────────────
_elevation_cache: dict = {}   # (lat, lon) → elevation_m
_overpass_cache: dict  = {}   # city → (timestamp, list[zone])
_OVERPASS_TTL = 3600          # 1 h

# ── City meta (matches live.py CITIES) ───────────────────────────
CITY_META = {
    "mumbai":    {"lat": 19.0760, "lon": 72.8777, "name": "Mumbai",    "elevation": 14,  "drain": 250},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946, "name": "Bengaluru", "elevation": 920, "drain": 850},
    "chennai":   {"lat": 13.0827, "lon": 80.2707, "name": "Chennai",   "elevation": 6,   "drain": 180},
    "pune":      {"lat": 18.5204, "lon": 73.8567, "name": "Pune",      "elevation": 560, "drain": 600},
}

# ── Curated shelter data (migrated from SafeZonesTab.jsx) ────────
STATIC_ZONES = {
    "mumbai": {
        "hospitals": [
            {"id": 1001, "name": "KEM Hospital",         "lat": 19.0012, "lon": 72.8416, "category": "hospital", "capacity": 1800, "phone": "022-2410-7000", "address": "Parel, Mumbai"},
            {"id": 1002, "name": "Sion Hospital",        "lat": 19.0437, "lon": 72.8614, "category": "hospital", "capacity": 1500, "phone": "022-2407-6381", "address": "Sion, Mumbai"},
            {"id": 1003, "name": "Nair Hospital",        "lat": 18.9647, "lon": 72.8258, "category": "hospital", "capacity": 1200, "phone": "022-2308-5000", "address": "Mumbai Central"},
            {"id": 1010, "name": "Lokmanya Tilak Hospital","lat": 19.0407,"lon": 72.8553,"category": "hospital", "capacity": 1600, "phone": "022-2404-6000", "address": "Sion, Mumbai"},
        ],
        "schools": [
            {"id": 1004, "name": "Municipal School Dharavi",  "lat": 19.0437, "lon": 72.8553, "category": "school", "capacity": 800,  "phone": "—",        "address": "Dharavi, Mumbai"},
            {"id": 1005, "name": "BMC School Bandra",         "lat": 19.0596, "lon": 72.8295, "category": "school", "capacity": 700,  "phone": "—",        "address": "Bandra West"},
            {"id": 1011, "name": "Kurla Municipal School",    "lat": 19.0726, "lon": 72.8826, "category": "school", "capacity": 600,  "phone": "—",        "address": "Kurla, Mumbai"},
        ],
        "shelters": [
            {"id": 1006, "name": "Dharavi Flood Relief Camp",  "lat": 19.0437, "lon": 72.8553, "category": "shelter", "capacity": 2500, "phone": "1077", "address": "Dharavi, Mumbai"},
            {"id": 1007, "name": "Govandi Sports Complex",     "lat": 19.0500, "lon": 72.9126, "category": "shelter", "capacity": 3000, "phone": "1077", "address": "Govandi, Mumbai"},
            {"id": 1008, "name": "Bandra-Kurla Relief Centre", "lat": 19.0665, "lon": 72.8684, "category": "shelter", "capacity": 1800, "phone": "1077", "address": "BKC, Mumbai"},
            {"id": 1009, "name": "Andheri Relief Camp",        "lat": 19.1136, "lon": 72.8697, "category": "shelter", "capacity": 2000, "phone": "1077", "address": "Andheri West"},
        ],
    },
    "bengaluru": {
        "hospitals": [
            {"id": 2001, "name": "Victoria Hospital",      "lat": 12.9660, "lon": 77.5714, "category": "hospital", "capacity": 1800, "phone": "080-2670-1150", "address": "Fort Rd, Bengaluru"},
            {"id": 2002, "name": "St. John's Hospital",    "lat": 12.9340, "lon": 77.6100, "category": "hospital", "capacity": 1300, "phone": "080-2206-5000", "address": "Sarjapur Rd, Bengaluru"},
            {"id": 2006, "name": "NIMHANS Campus Shelter", "lat": 12.9404, "lon": 77.5964, "category": "hospital", "capacity": 900,  "phone": "080-2699-5000", "address": "Hosur Rd, Bengaluru"},
        ],
        "schools": [
            {"id": 2003, "name": "Cubbon Park Shelter School",   "lat": 12.9763, "lon": 77.5929, "category": "school", "capacity": 600, "phone": "—", "address": "Cubbon Park, Bengaluru"},
            {"id": 2007, "name": "Kendriya Vidyalaya Hebbal",    "lat": 13.0358, "lon": 77.5970, "category": "school", "capacity": 800, "phone": "—", "address": "Hebbal, Bengaluru"},
        ],
        "shelters": [
            {"id": 2004, "name": "BBMP Shelter Koramangala",  "lat": 12.9279, "lon": 77.6271, "category": "shelter", "capacity": 1500, "phone": "1533", "address": "Koramangala, Bengaluru"},
            {"id": 2005, "name": "Lalbagh Emergency Camp",    "lat": 12.9507, "lon": 77.5848, "category": "shelter", "capacity": 2000, "phone": "1533", "address": "Lalbagh, Bengaluru"},
            {"id": 2008, "name": "Palace Grounds Relief Camp","lat": 13.0027, "lon": 77.5926, "category": "shelter", "capacity": 4000, "phone": "1533", "address": "Palace Grounds, Bengaluru"},
        ],
    },
    "chennai": {
        "hospitals": [
            {"id": 3001, "name": "Government General Hospital",     "lat": 13.0800, "lon": 80.2700, "category": "hospital", "capacity": 2700, "phone": "044-2530-5000", "address": "Park Town, Chennai"},
            {"id": 3002, "name": "Rajiv Gandhi Govt Hospital",      "lat": 13.0950, "lon": 80.2900, "category": "hospital", "capacity": 1600, "phone": "044-2530-6000", "address": "Perambur, Chennai"},
            {"id": 3006, "name": "Stanley Medical College Hospital", "lat": 13.1082, "lon": 80.2876, "category": "hospital", "capacity": 1400, "phone": "044-2528-4656", "address": "Stanley, Chennai"},
        ],
        "schools": [
            {"id": 3003, "name": "Govt High School Egmore",   "lat": 13.0789, "lon": 80.2619, "category": "school", "capacity": 500, "phone": "—", "address": "Egmore, Chennai"},
            {"id": 3007, "name": "CSI Bain School Mylapore",  "lat": 13.0338, "lon": 80.2685, "category": "school", "capacity": 600, "phone": "—", "address": "Mylapore, Chennai"},
        ],
        "shelters": [
            {"id": 3004, "name": "Marina Beach Relief Shelter", "lat": 13.0521, "lon": 80.2825, "category": "shelter", "capacity": 5000, "phone": "1913", "address": "Marina Beach, Chennai"},
            {"id": 3005, "name": "YMCA Flood Relief Camp",      "lat": 13.0602, "lon": 80.2485, "category": "shelter", "capacity": 2000, "phone": "044-2827-5880", "address": "Nandanam, Chennai"},
            {"id": 3008, "name": "Velachery Relief Centre",     "lat": 12.9815, "lon": 80.2180, "category": "shelter", "capacity": 2500, "phone": "1913", "address": "Velachery, Chennai"},
        ],
    },
    "pune": {
        "hospitals": [
            {"id": 4001, "name": "Sassoon General Hospital",     "lat": 18.5200, "lon": 73.8744, "category": "hospital", "capacity": 1400, "phone": "020-2612-9800", "address": "Sassoon Rd, Pune"},
            {"id": 4005, "name": "KEM Hospital Pune",            "lat": 18.5289, "lon": 73.8634, "category": "hospital", "capacity": 900,  "phone": "020-2612-8100", "address": "Rasta Peth, Pune"},
        ],
        "schools": [
            {"id": 4002, "name": "BMC School Hadapsar",          "lat": 18.5089, "lon": 73.9260, "category": "school", "capacity": 600, "phone": "—", "address": "Hadapsar, Pune"},
            {"id": 4006, "name": "Fergusson College Relief",     "lat": 18.5204, "lon": 73.8400, "category": "school", "capacity": 800, "phone": "—", "address": "Shivajinagar, Pune"},
        ],
        "shelters": [
            {"id": 4003, "name": "Nehru Stadium Flood Camp",     "lat": 18.5308, "lon": 73.8685, "category": "shelter", "capacity": 3000, "phone": "1800-233-4567", "address": "Lashkar, Pune"},
            {"id": 4004, "name": "PMC Shelter Shivajinagar",     "lat": 18.5308, "lon": 73.8478, "category": "shelter", "capacity": 2500, "phone": "020-2512-2000", "address": "Shivajinagar, Pune"},
            {"id": 4007, "name": "Balewadi Relief Ground",       "lat": 18.5636, "lon": 73.7728, "category": "shelter", "capacity": 4000, "phone": "020-2729-4000", "address": "Balewadi, Pune"},
        ],
    },
}

# ── Flood-prone area centroids per city (lat/lon) ─────────────────
FLOOD_ZONES = {
    "mumbai":    [(19.015, 72.855), (19.063, 72.838), (19.18, 72.97)],
    "bengaluru": [(12.935, 77.55),  (12.998, 77.62),  (12.975, 77.49)],
    "chennai":   [(13.063, 80.25),  (13.05,  80.27),  (13.12,  80.21)],
    "pune":      [(18.51,  73.86),  (18.56,  73.83),  (18.498, 73.87)],
}

# ── Helpers ───────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in km."""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _get_elevation_batch(locations: list) -> list:
    """
    Fetch elevation for multiple lat/lon pairs in a single API call.
    locations: list of (lat, lon) tuples
    Returns: list of elevation floats (same order), None on failure.
    """
    if not locations:
        return []
    # Check cache first — only fetch uncached ones
    results = [None] * len(locations)
    uncached_indices = []
    uncached_locs = []
    for i, (lat, lon) in enumerate(locations):
        key = (round(lat, 4), round(lon, 4))
        if key in _elevation_cache:
            results[i] = _elevation_cache[key]
        else:
            uncached_indices.append(i)
            uncached_locs.append((lat, lon))

    if uncached_locs:
        try:
            loc_str = "|".join(f"{lat},{lon}" for lat, lon in uncached_locs)
            r = requests.get(
                "https://api.open-elevation.com/api/v1/lookup",
                params={"locations": loc_str},
                timeout=15
            )
            if r.status_code == 200:
                fetched = r.json().get("results", [])
                for j, elev_data in enumerate(fetched):
                    elev = elev_data.get("elevation")
                    orig_i = uncached_indices[j]
                    lat, lon = uncached_locs[j]
                    key = (round(lat, 4), round(lon, 4))
                    _elevation_cache[key] = elev
                    results[orig_i] = elev
        except Exception as e:
            print(f"[safe_zones] Batch elevation fetch failed: {e}")
    return results


def _fetch_overpass(city: str, cfg: dict) -> list:
    """Fetch nearby hospitals, schools, shelters from Overpass API."""
    now = time.time()
    cached = _overpass_cache.get(city)
    if cached and (now - cached[0]) < _OVERPASS_TTL:
        return cached[1]

    lat, lon = cfg["lat"], cfg["lon"]
    # Overpass QL — pull hospitals, schools, community centres within 15 km
    query = f"""
    [out:json][timeout:20];
    (
      node["amenity"="hospital"](around:15000,{lat},{lon});
      node["amenity"="school"](around:15000,{lat},{lon});
      node["amenity"="community_centre"](around:15000,{lat},{lon});
      node["amenity"="shelter"](around:15000,{lat},{lon});
    );
    out body;
    """
    zones = []
    try:
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=18
        )
        if r.status_code == 200:
            elements = r.json().get("elements", [])
            for el in elements:
                amenity = el.get("tags", {}).get("amenity", "")
                cat = "hospital" if amenity == "hospital" else "school" if amenity == "school" else "shelter"
                name = el.get("tags", {}).get("name", "")
                if not name:
                    continue
                zones.append({
                    "id": f"osm_{el['id']}",
                    "name": name,
                    "lat": el["lat"],
                    "lon": el["lon"],
                    "category": cat,
                    "capacity": None,
                    "phone": el.get("tags", {}).get("phone", "—"),
                    "address": el.get("tags", {}).get("addr:full", "—"),
                    "source": "OpenStreetMap",
                })
    except Exception as e:
        print(f"[safe_zones] Overpass error: {e}")

    _overpass_cache[city] = (now, zones)
    return zones


def _merge_dedup(static: list, dynamic: list, threshold_km: float = 0.3) -> list:
    """Merge static + dynamic zones, removing near-duplicates."""
    merged = list(static)
    for dz in dynamic:
        too_close = any(
            _haversine(dz["lat"], dz["lon"], sz["lat"], sz["lon"]) < threshold_km
            for sz in merged
        )
        if not too_close:
            merged.append(dz)
    return merged


def _compute_risk_state(
    flood_prob: float,
    rainfall_72h: float,
    zone_elevation: float,
    city_elevation: float,
    min_flood_dist_km: float,
) -> dict:
    """
    Determines shelter risk state based on:
      flood_prob       — 0–100 from prediction engine
      rainfall_72h     — mm in last 72h
      zone_elevation   — elevation of shelter (m MSL)
      city_elevation   — baseline city elevation (m MSL)
      min_flood_dist_km— distance to nearest flood-prone zone
    Returns: {state, color, description}
    """
    # Elevation advantage vs city baseline
    elev_delta = zone_elevation - city_elevation
    elev_bonus = min(max(elev_delta / 10, -5), 10)  # capped ±

    adjusted = flood_prob - elev_bonus

    # Proximity penalty
    if min_flood_dist_km < 1.5:
        adjusted += 15
    elif min_flood_dist_km < 3:
        adjusted += 8

    # Rainfall modifier
    if rainfall_72h > 200:
        adjusted += 12
    elif rainfall_72h > 100:
        adjusted += 6

    if adjusted >= 70:
        return {"state": "EVACUATE",  "color": "#cc2222", "description": "Immediate evacuation risk — do not use as shelter"}
    if adjusted >= 45:
        return {"state": "AT_RISK",   "color": "#d97706", "description": "Elevated risk — prepare for rapid evacuation"}
    if adjusted >= 20:
        return {"state": "MONITOR",   "color": "#ca8a04", "description": "Monitor closely — conditions may deteriorate"}
    return     {"state": "SAFE",      "color": "#16a34a", "description": "Currently safe for sheltering"}


def _ai_score(zone: dict, flood_prob: float, rainfall_72h: float, city_elev: float) -> float:
    """
    Weighted AI safety score 0–100 (100 = safest).
    Weights:
      40% elevation advantage
      25% flood distance
      20% inverse flood probability
      15% inverse rainfall
    """
    zone_elev = zone.get("elevation_m") or city_elev
    elev_score = min(max((zone_elev - city_elev + 50) / 100 * 100, 0), 100)

    min_dist = zone.get("min_flood_dist_km", 10)
    dist_score = min(min_dist / 5 * 100, 100)

    prob_score = max(100 - flood_prob, 0)
    rain_score = max(100 - (rainfall_72h / 3), 0)

    return round(0.40*elev_score + 0.25*dist_score + 0.20*prob_score + 0.15*rain_score, 1)


# ── Main route ────────────────────────────────────────────────────

@router.get("/safe-zones/{city}")
def get_safe_zones(city: str, sim_date: Optional[str] = None):
    city = city.lower()
    if city not in CITY_META:
        city = "mumbai"

    cfg = CITY_META[city]
    flood_zones = FLOOD_ZONES.get(city, [])
    city_elev = cfg["elevation"]

    # 1. Get current flood prediction context
    flood_prob = 0.0
    rainfall_72h = 0.0
    try:
        from .live import get_live_data
        from .predict import predict_flood, PredictionRequest
        weather = get_live_data(city, sim_date=sim_date)
        rainfall_72h = weather["total_72h_rain"]
        req = PredictionRequest(
            rainfall_72h=weather["rainfall_72h"],
            forecast_24h=weather["total_24h_forecast"],
            elevation_m=weather["elevation_m"],
            drain_distance_m=weather["drain_distance_m"],
            city=city,
        )
        pred = predict_flood(req)
        flood_prob = pred["flood_probability"]
    except Exception as e:
        print(f"[safe_zones] Prediction fetch failed: {e}")

    # 2. Gather static zones
    static_data = STATIC_ZONES.get(city, {"hospitals": [], "schools": [], "shelters": []})
    all_static = (
        static_data.get("hospitals", []) +
        static_data.get("schools", []) +
        static_data.get("shelters", [])
    )

    # 3. Fetch dynamic Overpass POIs
    dynamic_zones = _fetch_overpass(city, cfg)

    # 4. Merge + dedup
    merged = _merge_dedup(all_static, dynamic_zones)

    # 5. Enrich each zone — batch elevation fetch to avoid timeout
    # Collect all locations needing elevation
    locations = [(z["lat"], z["lon"]) for z in merged]
    elevations = _get_elevation_batch(locations)

    enriched = []
    for z, elev in zip(merged, elevations):
        # Use fetched elevation or fall back to city baseline
        z["elevation_m"] = elev if elev is not None else city_elev

        # Flood zone proximity
        if flood_zones:
            min_dist = min(_haversine(z["lat"], z["lon"], fz[0], fz[1]) for fz in flood_zones)
        else:
            min_dist = 10.0
        z["min_flood_dist_km"] = round(min_dist, 2)

        # Risk state
        risk = _compute_risk_state(
            flood_prob, rainfall_72h,
            z["elevation_m"], city_elev, min_dist
        )
        z["risk_state"]   = risk["state"]
        z["risk_color"]   = risk["color"]
        z["risk_desc"]    = risk["description"]

        # AI safety score
        z["safety_score"] = _ai_score(z, flood_prob, rainfall_72h, city_elev)

        # Ensure capacity is numeric or None
        cap = z.get("capacity")
        if isinstance(cap, str):
            try:    z["capacity"] = int(cap.replace(",", ""))
            except: z["capacity"] = None

        enriched.append(z)

    # 6. Sort by safety score descending
    enriched.sort(key=lambda x: x["safety_score"], reverse=True)

    # 7. Re-split into categories for frontend compatibility
    hospitals = [z for z in enriched if z["category"] == "hospital"]
    schools   = [z for z in enriched if z["category"] == "school"]
    shelters  = [z for z in enriched if z["category"] == "shelter"]

    # 8. Top-N recommendation
    top_recommendations = sorted(enriched, key=lambda x: x["safety_score"], reverse=True)[:3]
    for i, r in enumerate(top_recommendations):
        r["recommendation_rank"] = i + 1
        r["confidence"] = f"{min(r['safety_score'], 99):.0f}%"

    now_ist = datetime.datetime.now(tz=IST).strftime("%Y-%m-%d %H:%M:%S IST")

    return {
        "city": city,
        "city_name": cfg["name"],
        "flood_probability": flood_prob,
        "rainfall_72h": rainfall_72h,
        "hospitals": hospitals,
        "schools":   schools,
        "shelters":  shelters,
        "top_recommendations": top_recommendations,
        "meta": {
            "total_zones": len(enriched),
            "safe_count":     len([z for z in enriched if z["risk_state"] == "SAFE"]),
            "monitor_count":  len([z for z in enriched if z["risk_state"] == "MONITOR"]),
            "at_risk_count":  len([z for z in enriched if z["risk_state"] == "AT_RISK"]),
            "evacuate_count": len([z for z in enriched if z["risk_state"] == "EVACUATE"]),
            "timestamp": now_ist,
        }
    }
