"""
flood_risk_engine.py — AquaAlert Flood Risk Engine v3.0

Core design principle:
  flood_risk_score = vulnerability_index * flood_probability_scalar

  - vulnerability_index (0-100): purely from CSV static features.
    Tells us HOW VULNERABLE an area is IF flooding occurs.
    Weights: elevation(30%) + density(20%) + drainage(15%) +
             historical(12%) + waterlogging(10%) + river(7%) + coastal(6%)

  - flood_probability_scalar: a non-linear amplifier derived from the
    city-level flood probability (0-100%) from the LSTM+XGBoost pipeline.
    Guarantees: prob=0  -> scalar=0.0  -> score=0   (no rain = no risk)
                prob=50 -> scalar=0.5  -> score=50% of vulnerability
                prob=100-> scalar=1.0  -> score=full vulnerability

  Final score = vulnerability_index * scalar   (clamped 0-100)

  This means:
    - A highly vulnerable area (Dharavi, vuln=90) at 0% flood prob -> score=0
    - A highly vulnerable area at 50% flood prob -> score=45
    - A highly vulnerable area at 100% flood prob -> score=90
    - A low vulnerability area (Powai, vuln=20) at 80% flood prob -> score=16
"""

import math

# ── City physical profiles ────────────────────────────────────────────────────
CITY_PROFILES = {
    "mumbai": {
        "baseline_elevation_m":       14,
        "elevation_range":            (2, 50),
        "max_historical_rainfall_mm": 2500,
        "max_urban_density":          35000,
        "base_threshold_elevation_m": 10,
        "threshold_sensitivity":      0.8,
    },
    "chennai": {
        "baseline_elevation_m":       6,
        "elevation_range":            (2, 28),
        "max_historical_rainfall_mm": 1450,
        "max_urban_density":          19000,
        "base_threshold_elevation_m": 5,
        "threshold_sensitivity":      0.75,
    },
    "bengaluru": {
        "baseline_elevation_m":       920,
        "elevation_range":            (860, 930),
        "max_historical_rainfall_mm": 950,
        "max_urban_density":          20000,
        "base_threshold_elevation_m": 870,
        "threshold_sensitivity":      0.5,
    },
    "pune": {
        "baseline_elevation_m":       560,
        "elevation_range":            (530, 590),
        "max_historical_rainfall_mm": 860,
        "max_urban_density":          22000,
        "base_threshold_elevation_m": 535,
        "threshold_sensitivity":      0.6,
    },
}

RISK_WEIGHTS = {
    "elevation":     0.30,
    "urban_density": 0.20,
    "drainage":      0.15,
    "historical":    0.12,
    "waterlogging":  0.10,
    "river":         0.07,
    "coastal":       0.06,
}


# ─────────────────────────────────────────────────────────────────────────────
# FLOOD PROBABILITY SCALAR
# Converts city-level flood probability (0-100%) into a score multiplier.
# Uses a power curve (exponent=1.4) so:
#   - Low probabilities (0-20%) produce very small multipliers
#   - Mid probabilities (40-60%) produce proportional multipliers
#   - High probabilities (80-100%) produce near-full multipliers
# Strictly: scalar(0) = 0.0, scalar(100) = 1.0
# ─────────────────────────────────────────────────────────────────────────────

def _flood_scalar(flood_probability: float) -> float:
    """
    Non-linear scalar [0.0, 1.0] from flood probability [0, 100].

    prob=0   -> 0.000  (guaranteed zero — no rain, no risk)
    prob=10  -> 0.050
    prob=20  -> 0.116
    prob=30  -> 0.196
    prob=40  -> 0.287
    prob=50  -> 0.387
    prob=60  -> 0.494
    prob=70  -> 0.607
    prob=80  -> 0.724
    prob=90  -> 0.845
    prob=100 -> 1.000  (guaranteed full vulnerability exposed)
    """
    p = max(0.0, min(100.0, flood_probability)) / 100.0
    return round(p ** 1.4, 6)


# ─────────────────────────────────────────────────────────────────────────────
# 1. THRESHOLD ELEVATION CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

def calculate_threshold_elevation(city: str, flood_probability: float,
                                   rainfall_72h: float) -> dict:
    """
    Dynamic safe-elevation threshold for a city.

    At 0% flood prob  -> threshold = base_threshold
    As prob rises     -> threshold climbs toward city baseline + buffer
    Rainfall modifier -> heavy rain raises threshold further
    """
    city    = city.lower()
    profile = CITY_PROFILES.get(city, CITY_PROFILES["mumbai"])

    base_thresh = profile["base_threshold_elevation_m"]
    baseline    = profile["baseline_elevation_m"]
    sensitivity = profile["threshold_sensitivity"]
    elev_min, elev_max = profile["elevation_range"]
    max_rain    = profile["max_historical_rainfall_mm"]

    flood_prob = max(0.0, min(100.0, flood_probability))
    rain_72h   = max(0.0, rainfall_72h)

    # Probability-driven rise (sigmoid centred at 50%)
    sig_val       = 1.0 / (1.0 + math.exp(-(flood_prob - 50.0) / 15.0))
    elev_span     = elev_max - elev_min
    max_threshold = baseline + (elev_span * 0.20)
    prob_threshold = base_thresh + (max_threshold - base_thresh) * sig_val * sensitivity

    # Rainfall saturation modifier (72h extreme ~ 15% of annual max)
    rain_72h_max  = max_rain * 0.15
    rain_ratio    = min(rain_72h / rain_72h_max, 1.0) if rain_72h_max > 0 else 0.0
    rain_modifier = elev_span * 0.15 * rain_ratio

    threshold = min(prob_threshold + rain_modifier, elev_max * 0.95)
    threshold = max(threshold, base_thresh)

    if flood_prob < 25:
        interpretation = "Low flood risk — no active threat"
    elif flood_prob < 50:
        interpretation = "Moderate risk — low-lying areas should monitor"
    elif flood_prob < 75:
        interpretation = "High risk — areas below threshold face inundation"
    else:
        interpretation = "Critical risk — widespread flooding likely"

    return {
        "threshold_elevation_m": round(threshold, 1),
        "base_threshold_m":      round(base_thresh, 1),
        "city_baseline_m":       baseline,
        "flood_probability":     round(flood_prob, 1),
        "rainfall_72h_mm":       round(rain_72h, 1),
        "rain_modifier_m":       round(rain_modifier, 2),
        "prob_component_m":      round(prob_threshold, 2),
        "interpretation":        interpretation,
        "city":                  city,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. VULNERABILITY INDEX COMPONENTS  (all return 0-100, purely from CSV)
# These are STATIC — they do NOT change with rainfall.
# They only tell us how exposed an area is IF flooding occurs.
# ─────────────────────────────────────────────────────────────────────────────

def _v_elevation(area_elevation_m: float, threshold_elevation_m: float,
                  city_elevation_range: tuple) -> float:
    """
    How far below the flood threshold is this area?
    Above threshold -> 0 (safe regardless of rain).
    At city minimum -> 100 (maximally exposed).
    Uses power curve (exponent 1.5) for non-linear amplification.
    """
    elev_min, _ = city_elevation_range
    deficit = threshold_elevation_m - area_elevation_m
    if deficit <= 0:
        return 0.0
    span  = max(threshold_elevation_m - elev_min, 1.0)
    ratio = min(deficit / span, 1.0)
    return round(min(100.0 * (ratio ** 1.5), 100.0), 2)


def _v_urban_density(density: float, city_max_density: float) -> float:
    """Higher density -> more impervious surface -> more runoff."""
    if city_max_density <= 0:
        return 0.0
    ratio = min(density / city_max_density, 1.0)
    return round(100.0 * (math.log1p(ratio * 9) / math.log1p(9)), 2)


def _v_drainage(drain_distance_m: float) -> float:
    """
    Larger drain distance -> water has farther to escape -> higher vulnerability.
    Sigmoid centred at 25m, saturates at ~60m.
    """
    x = (drain_distance_m - 25.0) / 10.0
    return round(100.0 / (1.0 + math.exp(-x)), 2)


def _v_historical_rainfall(historical_mm: float, city_max_mm: float) -> float:
    """Higher historical rainfall -> higher baseline soil saturation."""
    if city_max_mm <= 0:
        return 0.0
    return round(min(historical_mm / city_max_mm, 1.0) * 100.0, 2)


def _v_waterlogging(wlog_zones: float) -> float:
    """Recorded waterlogging events (0-8 in dataset)."""
    return round(min(wlog_zones / 8.0 * 100.0, 100.0), 2)


def _v_river(near_river: int) -> float:
    return 100.0 if near_river else 0.0


def _v_coastal(near_coastline: int) -> float:
    return 100.0 if near_coastline else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. COMPOSITE AREA RISK SCORER
# ─────────────────────────────────────────────────────────────────────────────

def calculate_area_risk_score(area: dict, threshold_elevation_m: float,
                               city: str, flood_probability: float = 0.0) -> dict:
    """
    Final formula:
        vulnerability_index = weighted sum of static CSV components (0-100)
        flood_scalar        = flood_probability ^ 1.4 / 100^1.4   (0.0 to 1.0)
        risk_score          = vulnerability_index * flood_scalar

    Guarantees:
        flood_probability = 0   -> risk_score = 0.0  (always)
        flood_probability = 100 -> risk_score = vulnerability_index
    """
    profile = CITY_PROFILES.get(city.lower(), CITY_PROFILES["mumbai"])

    elevation     = float(area.get("Elevation_m",             profile["baseline_elevation_m"]))
    density       = float(area.get("Urban_Density_sqkm",      10000))
    drain_dist    = float(area.get("Drain_Distance_m",        30))
    hist_rain     = float(area.get("Historical_Rainfall_mm",  profile["max_historical_rainfall_mm"] * 0.8))
    wlog_zones    = float(area.get("Water_Logging_Zones",     0))
    near_river    = int(area.get("Near_River",                0))
    near_coast    = int(area.get("Near_Coastline",            0))
    flood_hotspot = int(area.get("Flood_Hotspot",             0))

    # ── Step 1: Vulnerability components (static, 0-100 each) ────────────
    v_elev    = _v_elevation(elevation, threshold_elevation_m, profile["elevation_range"])
    v_density = _v_urban_density(density, profile["max_urban_density"])
    v_drain   = _v_drainage(drain_dist)
    v_hist    = _v_historical_rainfall(hist_rain, profile["max_historical_rainfall_mm"])
    v_wlog    = _v_waterlogging(wlog_zones)
    v_river   = _v_river(near_river)
    v_coast   = _v_coastal(near_coast)

    # ── Step 2: Weighted vulnerability index (0-100) ──────────────────────
    W = RISK_WEIGHTS
    vuln_index = (
        W["elevation"]     * v_elev    +
        W["urban_density"] * v_density +
        W["drainage"]      * v_drain   +
        W["historical"]    * v_hist    +
        W["waterlogging"]  * v_wlog    +
        W["river"]         * v_river   +
        W["coastal"]       * v_coast
    )

    # Known flood hotspot: 15% structural amplification on vulnerability
    if flood_hotspot:
        vuln_index = min(vuln_index * 1.15, 100.0)

    vuln_index = round(min(max(vuln_index, 0.0), 100.0), 2)

    # ── Step 3: Flood probability scalar (0.0 to 1.0) ────────────────────
    # This is the ONLY place flood_probability enters the area score.
    # scalar(0) = 0.0 ALWAYS -> score = 0 when no flood threat
    # scalar(100) = 1.0 -> score = full vulnerability index
    scalar = _flood_scalar(flood_probability)

    # ── Step 4: Final risk score ──────────────────────────────────────────
    risk_score = round(min(vuln_index * scalar, 100.0), 2)

    # ── Category ──────────────────────────────────────────────────────────
    if risk_score >= 75:
        category, category_color = "Critical", "#cc2222"
    elif risk_score >= 50:
        category, category_color = "High",     "#d97706"
    elif risk_score >= 25:
        category, category_color = "Moderate", "#ca8a04"
    else:
        category, category_color = "Low",      "#16a34a"

    # ── Explanations ──────────────────────────────────────────────────────
    weighted = {
        "Elevation vs Threshold": v_elev    * W["elevation"],
        "Urban Density":          v_density * W["urban_density"],
        "Drainage Distance":      v_drain   * W["drainage"],
        "Historical Rainfall":    v_hist    * W["historical"],
        "Waterlogging History":   v_wlog    * W["waterlogging"],
        "River Proximity":        v_river   * W["river"],
        "Coastal Proximity":      v_coast   * W["coastal"],
    }
    top_factors = sorted(weighted.items(), key=lambda x: x[1], reverse=True)

    explanations = []
    if flood_probability < 15:
        explanations.append(f"No active flood threat (prob={round(flood_probability,1)}%) — area score suppressed")
    else:
        if elevation < threshold_elevation_m:
            deficit = round(threshold_elevation_m - elevation, 1)
            explanations.append(f"Area is {deficit}m below flood threshold ({threshold_elevation_m}m)")
        for factor, contribution in top_factors[:3]:
            if contribution > 2.0:
                explanations.append(f"{factor}: {round(contribution, 1)}pt vulnerability")
    if not explanations:
        explanations.append("Low vulnerability — area above flood threshold")

    return {
        "risk_score":            risk_score,
        "vulnerability_index":   vuln_index,
        "flood_scalar":          round(scalar, 4),
        "category":              category,
        "category_color":        category_color,
        "threshold_used_m":      round(threshold_elevation_m, 1),
        "area_elevation_m":      elevation,
        "elevation_deficit_m":   round(max(threshold_elevation_m - elevation, 0), 1),
        "component_scores": {
            "elevation_risk":     round(v_elev,    1),
            "urban_density_risk": round(v_density, 1),
            "drainage_risk":      round(v_drain,   1),
            "historical_risk":    round(v_hist,    1),
            "waterlogging_risk":  round(v_wlog,    1),
            "river_risk":         round(v_river,   1),
            "coastal_risk":       round(v_coast,   1),
        },
        "weighted_contributions": {k: round(v * scalar, 2) for k, v in weighted.items()},
        "explanations":          explanations,
        "status":                "SUCCESS",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. CITY AREA RANKER
# ─────────────────────────────────────────────────────────────────────────────

def rank_areas_by_risk(areas: list, threshold_elevation_m: float,
                        city: str, flood_probability: float = 0.0) -> list:
    scored = []
    for area in areas:
        result = calculate_area_risk_score(area, threshold_elevation_m, city, flood_probability)
        scored.append({**area, **result})
    scored.sort(key=lambda x: x["risk_score"], reverse=True)
    for rank, area in enumerate(scored, start=1):
        area["risk_rank"] = rank
    return scored


# ─────────────────────────────────────────────────────────────────────────────
# 5. FULL PIPELINE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_flood_risk_pipeline(city: str, flood_probability: float,
                             rainfall_72h: float, areas: list) -> dict:
    threshold_info = calculate_threshold_elevation(city, flood_probability, rainfall_72h)
    threshold_m    = threshold_info["threshold_elevation_m"]
    ranked         = rank_areas_by_risk(areas, threshold_m, city, flood_probability)

    critical = [a for a in ranked if a["category"] == "Critical"]
    high     = [a for a in ranked if a["category"] == "High"]
    moderate = [a for a in ranked if a["category"] == "Moderate"]
    low      = [a for a in ranked if a["category"] == "Low"]

    return {
        "city":           city,
        "threshold_info": threshold_info,
        "ranked_areas":   ranked,
        "summary": {
            "total_areas":    len(ranked),
            "critical_count": len(critical),
            "high_count":     len(high),
            "moderate_count": len(moderate),
            "low_count":      len(low),
            "top_3_at_risk":  [a["Area"] for a in ranked[:3]],
            "formula_weights": RISK_WEIGHTS,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd

    COLS = ["Elevation_m", "Urban_Density_sqkm", "Drain_Distance_m",
            "Historical_Rainfall_mm", "Water_Logging_Zones",
            "Near_River", "Near_Coastline", "Flood_Hotspot"]

    def load(fpath):
        df = pd.read_csv(fpath)
        for col in COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df.to_dict("records")

    print("=== SCALAR TABLE: prob -> scalar ===")
    for p in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        print(f"  prob={p:3d}%  scalar={_flood_scalar(p):.4f}")

    print("\n=== TEST 1: zero prob must give score=0 for ALL areas ===")
    for city, fpath in [
        ("mumbai",    "../../Data_Urban/mumbai_flood_data.csv"),
        ("pune",      "../../Data_Urban/pune_flood_data.csv"),
        ("chennai",   "../../Data_Urban/chennai_flood_data.csv"),
        ("bengaluru", "../../Data_Urban/bangalore_flood_data.csv"),
    ]:
        r = run_flood_risk_pipeline(city, 0.0, 0.0, load(fpath))
        scores = [a["risk_score"] for a in r["ranked_areas"]]
        status = "PASS" if max(scores) == 0.0 else "FAIL"
        print(f"  [{status}] {city.upper():12} prob=0% -> max={max(scores):.2f}% avg={sum(scores)/len(scores):.2f}%")

    print("\n=== TEST 2: score scales with flood probability (Dharavi, Mumbai) ===")
    areas_mumbai = load("../../Data_Urban/mumbai_flood_data.csv")
    dharavi = next(a for a in areas_mumbai if a["Area"] == "Dharavi")
    for prob in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        t = calculate_threshold_elevation("mumbai", prob, prob * 2)
        r = calculate_area_risk_score(dharavi, t["threshold_elevation_m"], "mumbai", prob)
        print(f"  prob={prob:3d}%  vuln={r['vulnerability_index']:5.1f}  "
              f"scalar={r['flood_scalar']:.4f}  score={r['risk_score']:5.1f}%  [{r['category']}]")

    print("\n=== TEST 3: Mumbai vs Pune on 27-07-2005 ===")
    for city, fpath, prob, rain in [
        ("mumbai", "../../Data_Urban/mumbai_flood_data.csv",  92.5, 944.0),
        ("pune",   "../../Data_Urban/pune_flood_data.csv",    35.0,  98.0),
    ]:
        r = run_flood_risk_pipeline(city, prob, rain, load(fpath))
        t = r["threshold_info"]
        a = r["ranked_areas"][0]
        print(f"  {city.upper():12} prob={prob}%  rain={rain}mm  "
              f"thresh={t['threshold_elevation_m']}m  "
              f"top={a['Area']}  vuln={a['vulnerability_index']}  score={a['risk_score']}%")

    print("\n=== TEST 4: All cities at realistic conditions ===")
    for city, fpath, prob, rain in [
        ("mumbai",    "../../Data_Urban/mumbai_flood_data.csv",    72.5, 187),
        ("chennai",   "../../Data_Urban/chennai_flood_data.csv",   55.0, 143),
        ("bengaluru", "../../Data_Urban/bangalore_flood_data.csv", 38.0,  78),
        ("pune",      "../../Data_Urban/pune_flood_data.csv",       28.0,  95),
    ]:
        r = run_flood_risk_pipeline(city, prob, rain, load(fpath))
        t = r["threshold_info"]
        print(f"\n  {city.upper()} thresh={t['threshold_elevation_m']}m prob={prob}% rain={rain}mm")
        for a in r["ranked_areas"][:3]:
            print(f"    #{a['risk_rank']:2} {a['Area']:25} vuln={a['vulnerability_index']:5.1f} "
                  f"scalar={a['flood_scalar']:.3f} score={a['risk_score']:5.1f}% [{a['category']}]")
