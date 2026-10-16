# -*- coding: utf-8 -*-
"""
AquaAlert GAN Simulation Route
Generates synthetic extreme rainfall scenarios using trained conditional GAN.
Falls back to physics-based simulation if GAN model not trained yet.
"""

import os
import json
import sys
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from .live import get_live_data, CITIES
from .predict import predict_flood, PredictionRequest

router = APIRouter()

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models", "gan")
SEQ_LEN    = 72
LATENT_DIM = 32
COND_MIN   = 0.5
COND_MAX   = 3.0

# Cache loaded GAN models
_gan_cache = {}


def _normalize_cond(intensity: float) -> float:
    """Clamp intensity to the training range [COND_MIN, COND_MAX].
    The trained model received raw condition values in [0.5, 3.0] — NOT normalized.
    Values above COND_MAX are clamped to avoid out-of-distribution extrapolation
    that produces garbage sequences; physics fallback handles extreme scenarios."""
    return float(np.clip(intensity, COND_MIN, COND_MAX))


def load_gan(city: str):
    """Load GAN generator for a city, with caching."""
    if city in _gan_cache:
        return _gan_cache[city]

    model_path = os.path.join(MODELS_DIR, f"rainfall_gan_{city}.keras")
    if not os.path.exists(model_path):
        return None

    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(model_path, compile=False)
        _gan_cache[city] = model
        print(f"[GAN] Loaded generator for {city}")
        return model
    except Exception as e:
        print(f"[GAN] Load failed for {city}: {e}")
        return None


def physics_simulate(base_rain: list, intensity: float, seed: int = 42) -> list:
    """
    Physics-based fallback simulation when GAN model not available.
    Applies intensity scaling with realistic temporal patterns:
    - Gaussian storm bursts
    - Exponential decay between events
    - Diurnal variation
    """
    rng = np.random.default_rng(seed)
    base = np.array(base_rain, dtype=np.float32)

    # Scale base rainfall
    scaled = base * intensity

    # Add synthetic storm bursts
    n_bursts = rng.integers(1, 4)
    for _ in range(n_bursts):
        center = rng.integers(6, SEQ_LEN - 6)
        width  = rng.integers(3, 10)
        peak   = rng.uniform(5, 25) * intensity
        burst  = peak * np.exp(-0.5 * ((np.arange(SEQ_LEN) - center) / width) ** 2)
        scaled += burst.astype(np.float32)

    # Add diurnal variation (afternoon peaks)
    hours = np.arange(SEQ_LEN) % 24
    diurnal = 0.3 * intensity * np.sin(np.pi * hours / 12) ** 2
    scaled += diurnal.astype(np.float32)

    # Add realistic noise
    noise = rng.exponential(0.5 * intensity, SEQ_LEN).astype(np.float32)
    scaled += noise

    return np.clip(scaled, 0, None).tolist()


def gan_simulate(city: str, intensity: float, seed: int = None) -> tuple:
    """
    Generate synthetic rainfall using trained GAN.
    Returns (sequence, method_used).
    """
    G = load_gan(city)

    if G is not None:
        try:
            rng   = np.random.default_rng(seed)
            noise = rng.normal(0, 1, (1, LATENT_DIM)).astype(np.float32)
            # Pass raw clamped intensity — training used raw values in [0.5, 3.0]
            cond_val = _normalize_cond(intensity)
            cond  = np.array([[cond_val]], dtype=np.float32)
            gen   = G([noise, cond], training=False).numpy()[0]  # shape (72,) in [0,1]
            # Denormalize: gen is in [0,1] (sigmoid output trained on data/50.0)
            # Multiply by 50 to recover mm/hr, then scale by intensity for scenario amplification
            sequence = (gen * 50.0 * intensity).tolist()
            return sequence, "GAN"
        except Exception as e:
            print(f"[GAN] Inference failed: {e}")

    # Fallback to physics simulation
    return None, "PHYSICS"


class SimulateRequest(BaseModel):
    city: str = "mumbai"
    intensity: float = 2.0      # 1.0=normal, 2.0=double, 3.0=extreme, 5.0=catastrophic
    scenario: str = "custom"    # custom | monsoon_surge | cyclone | cloudburst
    seed: Optional[int] = None  # None = random each call


SCENARIO_INTENSITIES = {
    "monsoon_surge": 1.8,
    "cyclone":       3.5,
    "cloudburst":    5.0,
    "custom":        None,  # use provided intensity
}

SCENARIO_LABELS = {
    "monsoon_surge": "Monsoon Surge (1.8x)",
    "cyclone":       "Cyclonic Depression (3.5x)",
    "cloudburst":    "Urban Cloudburst (5.0x)",
    "custom":        "Custom Scenario",
}


@router.post("/simulate")
def simulate_scenario(req: SimulateRequest):
    city = req.city.lower()
    if city not in CITIES:
        city = "mumbai"

    # Resolve intensity
    intensity = SCENARIO_INTENSITIES.get(req.scenario) or req.intensity
    intensity = float(np.clip(intensity, 0.5, 10.0))

    # Get current live baseline
    live = None
    try:
        live = get_live_data(city)
        base_rain = live["rainfall_72h"]
        # Pad to exactly SEQ_LEN if API returned fewer points
        if len(base_rain) < SEQ_LEN:
            base_rain = [0.0] * (SEQ_LEN - len(base_rain)) + base_rain
        base_rain = base_rain[:SEQ_LEN]
        elevation = live["elevation_m"]
        drain     = live["drain_distance_m"]
    except Exception:
        base_rain = [0.0] * SEQ_LEN
        elevation = CITIES[city].get("elevation", 100)
        drain     = CITIES[city].get("drain", 500)

    # Use random seed if none provided — ensures different graph each call
    effective_seed = req.seed if req.seed is not None else int(np.random.randint(0, 2**31))

    # Generate synthetic sequence
    synthetic, method = gan_simulate(city, intensity, effective_seed)
    if synthetic is None:
        synthetic = physics_simulate(base_rain, intensity, effective_seed)

    # Run prediction on synthetic sequence — pass city for vulnerability correction
    pred_req = PredictionRequest(
        rainfall_72h=synthetic,
        forecast_24h=float(sum(synthetic[-24:])),
        elevation_m=elevation,
        drain_distance_m=drain,
        city=city
    )
    prediction = predict_flood(pred_req)

    # Also run baseline prediction for comparison
    base_req = PredictionRequest(
        rainfall_72h=base_rain,
        forecast_24h=live["total_24h_forecast"] if live is not None else 0,
        elevation_m=elevation,
        drain_distance_m=drain,
        city=city
    )
    try:
        base_pred = predict_flood(base_req)
        baseline_prob = base_pred["flood_probability"]
    except Exception:
        baseline_prob = 0.0

    # Build timeline for chart
    timeline = [
        {"hour": i, "mm": round(float(synthetic[i]), 2), "type": "synthetic"}
        for i in range(SEQ_LEN)
    ]

    # Risk escalation analysis
    total_synthetic = round(sum(synthetic), 1)
    total_baseline  = round(sum(base_rain), 1)
    risk_delta      = round(prediction["flood_probability"] - baseline_prob, 1)

    return {
        "status": "SUCCESS",
        "city": city.upper(),
        "scenario": SCENARIO_LABELS.get(req.scenario, "Custom"),
        "intensity_factor": intensity,
        "method": method,
        "gan_available": load_gan(city) is not None,
        "synthetic_sequence": synthetic,
        "timeline": timeline,
        "stats": {
            "total_72h_mm": total_synthetic,
            "baseline_72h_mm": total_baseline,
            "peak_hourly_mm": round(max(synthetic), 1),
            "hours_above_10mm": int(sum(1 for x in synthetic if x > 10)),
            "hours_above_25mm": int(sum(1 for x in synthetic if x > 25)),
        },
        "prediction": {
            "flood_probability": prediction["flood_probability"],
            "alert_level": prediction["final_alert_level"],
            "recommended_action": prediction["recommended_action"],
            "shap_values": prediction.get("shap_values", []),
        },
        "comparison": {
            "baseline_probability": round(baseline_prob, 1),
            "simulated_probability": prediction["flood_probability"],
            "risk_delta": risk_delta,
            "risk_escalation": "CRITICAL" if risk_delta > 40 else
                               "HIGH" if risk_delta > 20 else
                               "MODERATE" if risk_delta > 10 else "LOW",
        }
    }


@router.get("/simulate/status")
def gan_status():
    """Check which cities have trained GAN models."""
    status = {}
    for city in CITIES.keys():
        model_path = os.path.join(MODELS_DIR, f"rainfall_gan_{city}.keras")
        meta_path  = os.path.join(MODELS_DIR, f"rainfall_gan_{city}_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        status[city] = {
            "model_trained": os.path.exists(model_path),
            "meta": meta
        }

    summary_path = os.path.join(MODELS_DIR, "gan_summary.json")
    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)

    return {
        "cities": status,
        "summary": summary,
        "models_dir": MODELS_DIR
    }


@router.post("/simulate/train")
def trigger_gan_training():
    """Trigger GAN training in background (non-blocking)."""
    import subprocess

    script = os.path.join(BASE_DIR, "notebooks", "train_rainfall_gan.py")
    # Validate resolved path stays inside notebooks/ directory
    resolved = os.path.realpath(script)
    expected_dir = os.path.realpath(os.path.join(BASE_DIR, "notebooks"))
    if not resolved.startswith(expected_dir + os.sep) and resolved != expected_dir:
        return {"status": "ERROR", "message": "Invalid script path"}
    if not os.path.exists(script):
        return {"status": "ERROR", "message": "Training script not found"}

    try:
        os.makedirs(MODELS_DIR, exist_ok=True)
        log_path = os.path.join(MODELS_DIR, "gan_training.log")
        env = os.environ.copy()

        python_paths = [p for p in sys.path if p]
        if env.get("PYTHONPATH"):
            python_paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_paths))

        python_home = getattr(sys, "base_prefix", None) or getattr(sys, "prefix", None)
        if python_home:
            env["PYTHONHOME"] = python_home

        # Run training from the project root so relative save paths resolve correctly.
        with open(log_path, "a", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                [sys.executable, script],
                cwd=BASE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=env
            )
        return {
            "status": "TRAINING_STARTED",
            "pid": proc.pid,
            "log_path": log_path,
            "message": "GAN training started in background. Check /simulate/status for progress."
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
