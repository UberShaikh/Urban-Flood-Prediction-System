from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import os

router = APIRouter()

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XGB_PATH  = os.path.join(BASE_DIR, "models", "fusion", "xgboost_decision_layer.json")
LSTM_PATH = os.path.join(BASE_DIR, "models", "temporal", "pune_lstm_v1.keras")

xgb_model  = None
lstm_model = None

try:
    import xgboost as xgb
    xgb_model = xgb.XGBClassifier()
    xgb_model.load_model(XGB_PATH)
    print(f"[predict] XGBoost fusion loaded. Features: {list(xgb_model.feature_names_in_)}")
except Exception as e:
    print(f"[predict] XGBoost load failed: {e}")

try:
    from tensorflow.keras.models import load_model
    lstm_model = load_model(LSTM_PATH)
    print(f"[predict] LSTM loaded. Output: {lstm_model.output_shape}")
except Exception as e:
    print(f"[predict] LSTM load failed: {e}")


# ── City-specific vulnerability profiles ─────────────────────────────────────
# Used to differentiate probability output per city even when rainfall is similar.
# Fixes Bug 2: same sim_date rainfall was producing identical probabilities for
# Mumbai and Pune because the LSTM is Pune-trained and the override only checked
# rainfall thresholds, not city-specific physical characteristics.
CITY_VULNERABILITY = {
    "mumbai":    {"elev_ref": 14,  "drain_ref": 250, "coastal": True,  "base_sensitivity": 1.5},
    "chennai":   {"elev_ref": 6,   "drain_ref": 180, "coastal": True,  "base_sensitivity": 1.4},
    "bengaluru": {"elev_ref": 920, "drain_ref": 850, "coastal": False, "base_sensitivity": 0.7},
    "pune":      {"elev_ref": 560, "drain_ref": 600, "coastal": False, "base_sensitivity": 0.9},
}


class PredictionRequest(BaseModel):
    rainfall_72h:     List[float]    = None
    forecast_24h:     float          = 0.0
    elevation_m:      float          = None
    drain_distance_m: float          = None
    city:             Optional[str]  = None   # NEW: city key for differentiation
    # Legacy fields
    rainfall:         float          = None
    elevation:        float          = None
    river_discharge:  float          = None


@router.post("/predict")
def predict_flood(req: PredictionRequest):
    if xgb_model is None:
        return {
            "algorithm": "XGBoost Fusion",
            "prediction_status": "API OFFLINE",
            "flood_probability": 0.0,
            "lstm_flood_probability": 0.0,
            "recommended_action": "Backend model not loaded",
            "shap_values": [],
        }

    # ── Extract inputs ────────────────────────────────────────────────────
    if req.rainfall_72h is not None:
        rain_seq   = np.array(req.rainfall_72h, dtype=np.float32)
        elevation  = float(req.elevation_m  or 500)
        drain_dist = float(req.drain_distance_m or 600)
    else:
        total      = float(req.rainfall or 145)
        rain_seq   = np.full(72, total / 72, dtype=np.float32)
        elevation  = float(req.elevation or 500)
        drain_dist = float(req.river_discharge or 600)

    total_72h = float(np.sum(rain_seq))
    city_key  = (req.city or "").lower()

    print(f"[predict] city={city_key or 'unknown'} elev={elevation} drain={drain_dist} "
          f"rain_72h={total_72h:.1f} forecast={req.forecast_24h}")

    # ── Phase 1: LSTM temporal probability ───────────────────────────────
    # LSTM is Pune-trained → output is a raw temporal signal, not city-specific.
    # We treat it as a rainfall-intensity score and apply a city correction below.
    lstm_prob = 0.05
    if lstm_model is not None:
        try:
            rain_scaled = np.clip(rain_seq / 50.0, 0.0, 1.0)
            rain_input  = rain_scaled.reshape(1, 72, 1)
            lstm_prob   = float(lstm_model.predict(rain_input, verbose=0)[0][0])
        except Exception as e:
            print(f"LSTM inference failed: {e}")
            lstm_prob = float(total_72h / 800)

    # ── Phase 2: City-specific vulnerability correction (Bug 2 fix) ──────
    # The LSTM gives the same output for the same rainfall regardless of city.
    # We correct this by computing a city vulnerability multiplier based on:
    #   - How much lower the city's actual elevation is vs a reference (500m)
    #   - How much shorter the drain distance is vs a reference (500m)
    #   - Coastal bonus
    # This ensures Mumbai (elev=14, drain=250, coastal) gets a higher adjusted
    # lstm_prob than Pune (elev=560, drain=600) for the same rainfall sequence.

    vuln = CITY_VULNERABILITY.get(city_key)
    if vuln:
        # Elevation factor: lower elevation → higher multiplier
        # Normalised: 0m elev → factor=2.0, 1000m elev → factor=0.5
        elev_factor  = max(0.5, 2.0 - (elevation / 500.0))

        # Drain factor: shorter drain distance → water escapes faster → lower risk
        # Normalised: 0m drain → factor=0.5, 1000m drain → factor=1.5
        drain_factor = max(0.5, 0.5 + (drain_dist / 1000.0))

        # Coastal adds a fixed 20% amplification
        coastal_bonus = 1.20 if vuln["coastal"] else 1.0

        city_multiplier = elev_factor * drain_factor * coastal_bonus * vuln["base_sensitivity"]
        # Clamp multiplier to [0.4, 2.5] to prevent extreme values
        city_multiplier = max(0.4, min(2.5, city_multiplier))

        lstm_prob_adjusted = min(lstm_prob * city_multiplier, 1.0)
        print(f"[predict] lstm_raw={lstm_prob:.3f} city_mult={city_multiplier:.2f} "
              f"lstm_adj={lstm_prob_adjusted:.3f}")
    else:
        lstm_prob_adjusted = lstm_prob
        city_multiplier    = 1.0

    # ── Phase 3: XGBoost fusion decision ─────────────────────────────────
    fusion_input = np.array([[lstm_prob_adjusted, elevation, drain_dist]])
    try:
        pred_class = int(xgb_model.predict(fusion_input)[0])
        proba      = xgb_model.predict_proba(fusion_input)[0]
        if len(proba) == 3:
            probability = float(proba[1] * 50 + proba[2] * 100)
        else:
            probability = float(proba[-1] * 100)
    except Exception as e:
        print(f"XGBoost fusion failed: {e}")
        pred_class  = 1 if lstm_prob_adjusted > 0.5 else 0
        probability = lstm_prob_adjusted * 100

    # ── Phase 4: City-aware safety override ──────────────────────────────
    # Thresholds are now scaled by the city vulnerability multiplier so that
    # a coastal low-elevation city (Mumbai) triggers at lower raw rainfall
    # than a high-elevation inland city (Pune/Bengaluru).
    #
    # Base thresholds (mm):
    #   high_threshold_24h = 100mm / city_multiplier
    #   mod_threshold_24h  =  50mm / city_multiplier
    #   high_threshold_72h = 300mm / city_multiplier
    #   mod_threshold_72h  = 150mm / city_multiplier
    #
    # Example at city_multiplier=1.8 (Mumbai):
    #   high_24h ≈ 55mm, mod_24h ≈ 28mm, high_72h ≈ 167mm, mod_72h ≈ 83mm
    # Example at city_multiplier=0.9 (Pune):
    #   high_24h ≈ 111mm, mod_24h ≈ 56mm, high_72h ≈ 333mm, mod_72h ≈ 167mm

    eff_mult = city_multiplier if vuln else 1.0

    high_24h = 100.0 / eff_mult
    mod_24h  =  50.0 / eff_mult
    high_72h = 300.0 / eff_mult
    mod_72h  = 150.0 / eff_mult

    if req.forecast_24h > high_24h or total_72h > high_72h:
        pred_class  = 2
        probability = max(probability, 92.5)
    elif req.forecast_24h > mod_24h or total_72h > mod_72h:
        if pred_class < 1:
            pred_class = 1
        probability = max(probability, 65.0)

    # ── Status label ──────────────────────────────────────────────────────
    risk_map = {0: "LOW RISK - SAFE", 1: "MODERATE RISK - MONITOR", 2: "HIGH RISK - DANGER"}
    status   = risk_map.get(pred_class, "MODERATE RISK - MONITOR")

    # ── XAI: feature importances as SHAP proxy ────────────────────────────
    shap_values = []
    try:
        fi     = xgb_model.feature_importances_
        labels = ["Temporal Risk Score", "Elevation", "Drain Distance"]
        total  = float(np.sum(fi)) or 1.0
        shap_values = sorted([
            {"feature": labels[i], "value": round(float(fi[i]), 4),
             "pct": round(float(fi[i]) / total * 100, 1), "direction": "positive"}
            for i in range(len(fi))
        ], key=lambda x: x["value"], reverse=True)
    except Exception:
        pass

    return {
        "algorithm":              "Predictive Fusion Pipeline v2.1",
        "prediction_status":      status,
        "final_alert_level":      status,
        "flood_probability":      round(probability, 2),
        "lstm_flood_probability": round(lstm_prob * 100, 2),
        "lstm_adjusted":          round(lstm_prob_adjusted * 100, 2),
        "city_vulnerability_multiplier": round(city_multiplier, 3),
        "recommended_action": (
            "Evacuate immediately" if pred_class == 2
            else "Monitor closely" if pred_class == 1
            else "No action needed"
        ),
        "shap_values": shap_values,
    }
