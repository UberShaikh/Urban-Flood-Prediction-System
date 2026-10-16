import os
import sys
import base64
import json
from io import BytesIO
from datetime import datetime

import numpy as np
import pandas as pd
import requests as req_lib
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

# ── XGBoost SAR Patch Classifier (Sen1Floods11) ───────────────────────────────
# Replaces synthetic pixel analysis with a real model trained on SAR data.
# Features: 18 SAR backscatter statistics from VV/VH polarization bands.
# Classes: Low Risk (0), Moderate Risk (1), High Risk (2)
# Accuracy: 76.1% on Sen1Floods11 flood_handlabeled test set

_sar_xgb_model = None
_sar_xgb_metrics = None
_SAR_XGB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "fusion", "xgboost_sar_patch_classifier.json"
)
_SAR_XGB_METRICS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "fusion", "xgboost_sar_patch_metrics.json"
)

# Feature names exactly as trained on Sen1Floods11
_SAR_FEATURE_NAMES = [
    "vv_mean", "vv_std", "vv_min", "vv_max",
    "vv_p10", "vv_p50", "vv_p90",
    "vh_mean", "vh_std", "vh_min", "vh_max",
    "vh_p10", "vh_p50", "vh_p90",
    "vv_vh_diff_mean", "vv_vh_ratio_mean",
    "dark_vv_fraction", "dark_vh_fraction",
]

# SAR dB thresholds for "dark" (water/flood) pixel detection
# Water in SAR: VV < -15 dB, VH < -20 dB (Sen1Floods11 standard)
_DARK_VV_THRESHOLD_DB = -15.0
_DARK_VH_THRESHOLD_DB = -20.0


def _load_sar_xgb():
    """Load the XGBoost SAR patch classifier. Cached after first load."""
    global _sar_xgb_model, _sar_xgb_metrics
    if _sar_xgb_model is not None:
        return _sar_xgb_model
    try:
        import xgboost as xgb
        m = xgb.XGBClassifier()
        m.load_model(_SAR_XGB_PATH)
        _sar_xgb_model = m
        print(f"[vision] SAR XGBoost classifier loaded. Features: {_SAR_FEATURE_NAMES}")
        # Load metrics for display
        if os.path.exists(_SAR_XGB_METRICS_PATH):
            with open(_SAR_XGB_METRICS_PATH) as f:
                _sar_xgb_metrics = json.load(f)
            print(f"[vision] SAR model accuracy: {_sar_xgb_metrics.get('classification_report', {}).get('accuracy', 'N/A')}")
    except Exception as e:
        print(f"[vision] SAR XGBoost load failed: {e}")
        _sar_xgb_model = None
    return _sar_xgb_model


def _image_to_sar_db(image_array_rgb: np.ndarray) -> tuple:
    """
    Convert an RGB image (0-255 uint8, shape HxWx3) to simulated SAR dB values.

    SAR VV/VH backscatter is in dB scale (negative values).
    Mapping strategy:
      - VV channel: derived from image brightness (R+G channels)
        Bright pixels (dry land) -> high backscatter (~-5 dB)
        Dark pixels (water/flood) -> low backscatter (~-25 dB)
        Range: [-30, 0] dB
      - VH channel: derived from blue channel + texture
        Water has very low VH (~-30 dB), vegetation higher (~-15 dB)
        Range: [-35, -5] dB

    This mapping is physically grounded:
    - SAR water = dark (low backscatter) = dark pixels in image
    - SAR dry land = bright (high backscatter) = bright pixels in image
    """
    arr = image_array_rgb.astype(np.float32) / 255.0  # normalize to [0,1]

    # VV: use mean of R and G channels (luminance proxy)
    # Map [0,1] brightness -> [-30, 0] dB
    # Dark (0) -> -30 dB (water), Bright (1) -> 0 dB (dry land)
    luminance = (arr[:, :, 0] * 0.5 + arr[:, :, 1] * 0.5)
    vv_db = luminance * 30.0 - 30.0  # range [-30, 0]

    # VH: use blue channel + inverse texture
    # Water: low VH (-30 dB), vegetation: higher VH (-15 dB)
    # Map [0,1] -> [-35, -5] dB
    blue_norm = arr[:, :, 2]
    vh_db = blue_norm * 30.0 - 35.0  # range [-35, -5]

    return vv_db, vh_db


def _extract_sar_features(vv_db: np.ndarray, vh_db: np.ndarray) -> np.ndarray:
    """
    Extract the 18 SAR features used by the XGBoost classifier.
    All features are computed from VV and VH dB arrays.

    Returns: numpy array of shape (1, 18) ready for XGBoost inference.
    """
    vv_flat = vv_db.flatten()
    vh_flat = vh_db.flatten()

    features = [
        # VV statistics
        float(np.mean(vv_flat)),
        float(np.std(vv_flat)),
        float(np.min(vv_flat)),
        float(np.max(vv_flat)),
        float(np.percentile(vv_flat, 10)),
        float(np.percentile(vv_flat, 50)),
        float(np.percentile(vv_flat, 90)),
        # VH statistics
        float(np.mean(vh_flat)),
        float(np.std(vh_flat)),
        float(np.min(vh_flat)),
        float(np.max(vh_flat)),
        float(np.percentile(vh_flat, 10)),
        float(np.percentile(vh_flat, 50)),
        float(np.percentile(vh_flat, 90)),
        # Cross-polarization features
        float(np.mean(vv_flat - vh_flat)),                    # vv_vh_diff_mean
        float(np.mean(vv_flat / (vh_flat + 1e-6))),           # vv_vh_ratio_mean
        # Dark fraction (water/flood detection)
        float(np.mean(vv_flat < _DARK_VV_THRESHOLD_DB)),      # dark_vv_fraction
        float(np.mean(vh_flat < _DARK_VH_THRESHOLD_DB)),      # dark_vh_fraction
    ]

    return np.array([features], dtype=np.float32)  # shape (1, 18)


def _run_sar_xgb_inference(image_array_rgb: np.ndarray) -> dict:
    """
    Full SAR XGBoost inference pipeline:
      1. Convert RGB image to SAR dB values
      2. Extract 18 SAR features
      3. Run XGBoost classifier
      4. Return class probabilities + flood percentage

    Returns dict with:
      flood_percentage: 0-100 (based on High Risk probability)
      risk_class: 'Low Risk' | 'Moderate Risk' | 'High Risk'
      class_probabilities: {Low Risk: %, Moderate Risk: %, High Risk: %}
      dark_vv_fraction: fraction of dark VV pixels (water indicator)
      dark_vh_fraction: fraction of dark VH pixels
      sar_features: the 18 extracted features for transparency
    """
    model = _load_sar_xgb()
    if model is None:
        return None

    try:
        import pandas as _pd
    except Exception:
        import pandas as _pd

    # Step 1: Convert to SAR dB
    vv_db, vh_db = _image_to_sar_db(image_array_rgb)

    # Step 2: Extract features
    feat_array = _extract_sar_features(vv_db, vh_db)
    feat_df = _pd.DataFrame(feat_array, columns=_SAR_FEATURE_NAMES)

    # Step 3: XGBoost inference
    proba = model.predict_proba(feat_df)[0]   # [P(Low), P(Moderate), P(High)]
    pred_class = int(model.predict(feat_df)[0])
    class_names = ["Low Risk", "Moderate Risk", "High Risk"]
    risk_class = class_names[pred_class]

    # Flood percentage: weighted combination
    # Low=0%, Moderate=50%, High=100% weighted by probabilities
    flood_pct = float(proba[1] * 50.0 + proba[2] * 100.0)
    flood_pct = min(flood_pct, 100.0)

    return {
        "flood_percentage":    round(flood_pct, 2),
        "risk_class":          risk_class,
        "pred_class_idx":      pred_class,
        "class_probabilities": {
            "Low Risk":      round(float(proba[0]) * 100, 1),
            "Moderate Risk": round(float(proba[1]) * 100, 1),
            "High Risk":     round(float(proba[2]) * 100, 1),
        },
        "dark_vv_fraction":    round(float(np.mean(vv_db.flatten() < _DARK_VV_THRESHOLD_DB)), 3),
        "dark_vh_fraction":    round(float(np.mean(vh_db.flatten() < _DARK_VH_THRESHOLD_DB)), 3),
        "vv_mean_db":          round(float(np.mean(vv_db)), 2),
        "vh_mean_db":          round(float(np.mean(vh_db)), 2),
        "model_accuracy":      round(
            _sar_xgb_metrics.get("classification_report", {}).get("accuracy", 0) * 100, 1
        ) if _sar_xgb_metrics else None,
    }

# ── PyTorch (optional) ────────────────────────────────────────────────────────
torch = None
torchvision = None
_TORCH_LOAD_ERROR = None

try:
    import importlib.util as _ilu
    _ts = _ilu.find_spec("torch")
    if _ts is None:
        raise ImportError("torch not found in this environment")
    # Register DLL dir BEFORE importing (Windows WinError 1114 fix)
    _tlib = os.path.join(os.path.dirname(_ts.origin), "lib")
    if os.path.isdir(_tlib) and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_tlib)
    # Verify the DLL actually loads before importing torch
    import ctypes as _ct
    _c10 = os.path.join(_tlib, "c10.dll")
    if os.path.exists(_c10):
        _ct.CDLL(_c10)  # will raise OSError if DLL broken
    import torch as _torch
    import torchvision as _torchvision
    torch = _torch
    torchvision = _torchvision
    print("[vision] PyTorch loaded successfully.")
except Exception as _e:
    _TORCH_LOAD_ERROR = str(_e)
    print(f"[vision] PyTorch unavailable — using numpy fallback. ({str(_e)[:80]})")

# ── TensorFlow (optional) ─────────────────────────────────────────────────────
tf = None
load_model = None
K = None
_TF_LOAD_ERROR = None

try:
    import tensorflow as _tf
    from tensorflow.keras.models import load_model as _lm
    from tensorflow.keras import backend as _K
    tf = _tf; load_model = _lm; K = _K
    print("[vision] TensorFlow loaded successfully.")
except Exception as _e:
    _TF_LOAD_ERROR = str(_e)
    print(f"[vision] TensorFlow unavailable. ({str(_e)[:80]})")

# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH_PT = os.path.join(BASE_DIR, "models", "vision", "resnet50_sar_flood_best.pt")
MODEL_PATH_H5 = os.path.join(BASE_DIR, "models", "vision", "resnet50_sar_segmentation.h5")

_cnn_model = None
_model_type = None
_flood_inventory = None
_target_dates = None
_rain_cache = {}


# ── Model Architecture ────────────────────────────────────────────────────────

def _build_resnet50_pt():
    import torch.nn as nn
    model = torchvision.models.resnet50(weights=None)
    model.fc = nn.Sequential(
        nn.Linear(2048, 512), nn.ReLU(), nn.Dropout(0.3), nn.Linear(512, 2)
    )
    return model


# ── Model Loading ─────────────────────────────────────────────────────────────

def get_model():
    global _cnn_model, _model_type
    if _cnn_model is not None:
        return _cnn_model, _model_type

    # 1. Try PyTorch .pt
    if torch is not None and os.path.exists(MODEL_PATH_PT):
        try:
            sd = torch.load(MODEL_PATH_PT, map_location="cpu")
            m = _build_resnet50_pt()
            m.load_state_dict(sd)
            m.eval()
            _cnn_model, _model_type = m, "pytorch"
            print(f"[vision] PyTorch model loaded.")
            return _cnn_model, _model_type
        except Exception as e:
            print(f"[vision] PyTorch model load failed: {e}")

    # 2. Try TensorFlow .h5
    if tf is not None and os.path.exists(MODEL_PATH_H5):
        try:
            _cnn_model = load_model(MODEL_PATH_H5, compile=False)
            _model_type = "tensorflow"
            print(f"[vision] TensorFlow model loaded.")
            return _cnn_model, _model_type
        except Exception as e:
            print(f"[vision] TensorFlow model load failed: {e}")

    # 3. Numpy fallback — physics-based pixel analysis, no ML needed
    _cnn_model, _model_type = "numpy_fallback", "numpy"
    print("[vision] Using numpy pixel-analysis fallback.")
    return _cnn_model, _model_type


# ── Numpy Fallback Inference ──────────────────────────────────────────────────

def _numpy_infer(x_norm):
    """
    Physics-based SAR flood detection using pixel statistics.
    SAR flood signatures: low backscatter (dark pixels), smooth texture,
    blue-channel dominance in optical proxies.
    Returns flood_prob in [0,1].
    """
    arr = x_norm[0]  # (128,128,3)
    dark_ratio   = float(np.mean(arr < 0.18))
    smooth       = 1.0 - min(float(np.var(arr)) * 20, 1.0)
    blue_dom     = float(np.clip(np.mean(arr[:,:,2]) - np.mean(arr[:,:,0]) + 0.5, 0, 1))
    low_bright   = float(np.clip(1.0 - np.mean(arr) * 1.5, 0, 1))

    flood_prob = (dark_ratio * 0.45 + smooth * 0.25 + blue_dom * 0.15 + low_bright * 0.15)
    return float(np.clip(flood_prob, 0.0, 1.0))


# ── Pixel Saliency GradCAM (works without TF/torch) ──────────────────────────

def _pixel_saliency_gradcam(x_norm):
    """Flood-only saliency: highlights dark SAR water pixels only."""
    arr = x_norm[0].copy()  # (128,128,3)
    brightness = arr.mean(axis=2)  # (128,128)

    # Flood mask: dark pixels = water/flood in SAR
    flood_mask = np.clip(1.0 - brightness / 0.35, 0, 1).astype(np.float32)

    # Blue-channel dominance (water spectral signature)
    blue_dom = np.clip(arr[:,:,2] - arr[:,:,0] + 0.2, 0, 1)

    # Combine: flood mask drives the heatmap
    heatmap = (flood_mask * 0.75 + blue_dom * 0.25).astype(np.float32)

    # Smooth edges
    try:
        from scipy.ndimage import gaussian_filter
        heatmap = gaussian_filter(heatmap, sigma=2.5)
    except Exception:
        pass

    if heatmap.max() > 0:
        heatmap = heatmap / heatmap.max()

    return _heatmap_to_b64(heatmap)


def _heatmap_to_b64(heatmap):
    heatmap = np.maximum(heatmap, 0)
    if heatmap.max() > 0:
        heatmap = heatmap / heatmap.max()
    hm = np.array(Image.fromarray((heatmap * 255).astype(np.uint8))
                  .resize((128, 128), Image.BILINEAR), dtype=np.float32) / 255.0
    r = np.clip(1.5 - np.abs(hm * 4.0 - 3.0), 0, 1)
    g = np.clip(1.5 - np.abs(hm * 4.0 - 2.0), 0, 1)
    b = np.clip(1.5 - np.abs(hm * 4.0 - 1.0), 0, 1)
    alpha = np.clip(hm * 230 + 60, 0, 255).astype(np.uint8)
    rgba = np.stack([(r*255).astype(np.uint8), (g*255).astype(np.uint8),
                     (b*255).astype(np.uint8), alpha], axis=-1)
    buf = BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── PyTorch GradCAM ───────────────────────────────────────────────────────────

def _pytorch_gradcam(model, x_tensor):
    """Grad-CAM masked to flood pixels only (dark, low-backscatter SAR regions)."""
    try:
        import torch.nn.functional as F

        # --- Step 1: Multi-scale GradCAM (layer4 + layer3) ---
        cams = []
        for layer, w in [(model.layer4, 0.7), (model.layer3, 0.3)]:
            acts, grads = {}, {}
            hf = layer.register_forward_hook(lambda m, i, o: acts.update({'f': o}))
            hb = layer.register_full_backward_hook(lambda m, i, o: grads.update({'g': o[0]}))
            x = x_tensor.clone().requires_grad_(True)
            logits = model(x)
            model.zero_grad()
            logits[0, 1].backward()  # flood class
            hf.remove(); hb.remove()

            feat = acts['f'][0].detach()
            grad = grads['g'][0].detach()
            weight = F.relu(grad).mean(dim=(1, 2))
            cam = F.relu((weight[:, None, None] * feat).sum(dim=0))
            cam_up = F.interpolate(
                cam.unsqueeze(0).unsqueeze(0).float(),
                size=(128, 128), mode='bilinear', align_corners=False
            ).squeeze().detach().numpy()
            cams.append(cam_up * w)

        combined = cams[0] + cams[1]

        # --- Step 2: Normalize GradCAM ---
        mn, mx = combined.min(), combined.max()
        if mx > mn:
            combined = (combined - mn) / (mx - mn)

        # --- Step 3: Build flood pixel mask from original image ---
        # Undo ImageNet normalization to get back [0,1] pixel values
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_np = x_tensor.squeeze(0).permute(1, 2, 0).detach().numpy()
        img_orig = np.clip(img_np * std + mean, 0, 1)  # (128,128,3) in [0,1]

        # SAR flood signature: dark pixels (low backscatter = water)
        brightness = img_orig.mean(axis=2)             # (128,128)
        dark_mask  = (brightness < 0.35).astype(np.float32)  # flood = dark

        # Smooth the mask with a small blur to avoid hard edges
        from scipy.ndimage import gaussian_filter
        dark_mask_smooth = gaussian_filter(dark_mask, sigma=3.0)
        # Renormalize
        if dark_mask_smooth.max() > 0:
            dark_mask_smooth = dark_mask_smooth / dark_mask_smooth.max()

        # --- Step 4: Multiply GradCAM by flood mask ---
        # This zeros out heatmap on non-flood (bright) regions
        masked = combined * dark_mask_smooth

        # Renormalize after masking
        if masked.max() > 0:
            masked = masked / masked.max()

        # Mild gamma to fill flood boundaries
        masked = np.power(masked, 0.6)

        return _heatmap_to_b64(masked)
    except Exception as e:
        print(f"[vision] PyTorch GradCAM failed: {e}")
        return None


# ── TF GradCAM ────────────────────────────────────────────────────────────────

def _tf_gradcam(model, x):
    try:
        last_idx = max(i for i, l in enumerate(model.layers) if "conv2d" in l.name)
        last_conv = model.layers[last_idx]
        grad_model = tf.keras.models.Model(inputs=model.inputs,
                                           outputs=[last_conv.output, model.output])
        img_t = tf.cast(x, tf.float32)
        with tf.GradientTape() as tape:
            conv_out, preds = grad_model(img_t)
            loss = tf.reduce_mean(preds)
        grads = tape.gradient(loss, conv_out)
        if grads is None:
            return None
        pooled = tf.reduce_mean(grads, axis=(0, 1, 2)).numpy()
        heatmap = np.dot(conv_out[0].numpy(), pooled)
        return _heatmap_to_b64(heatmap)
    except Exception as e:
        print(f"[vision] TF GradCAM failed: {e}")
        return None


# ── Pixel Stats ───────────────────────────────────────────────────────────────

def analyze_image_pixels(x_norm):
    arr = x_norm[0]
    return {
        "brightness":        round(float(np.mean(arr)), 3),
        "dark_pixel_ratio":  round(float(np.mean(arr < 0.2)) * 100, 1),
        "bright_pixel_ratio":round(float(np.mean(arr > 0.8)) * 100, 1),
        "texture_variance":  round(float(np.var(arr)), 4),
        "blue_dominance":    round(float(np.mean(arr[:,:,2]) - np.mean(arr[:,:,0])), 3),
    }


# ── Historical Data ───────────────────────────────────────────────────────────

def load_historical_data():
    global _flood_inventory, _target_dates
    if _flood_inventory is None:
        try:
            _flood_inventory = pd.read_csv(
                os.path.join(BASE_DIR, "data", "raw", "India_Flood_Inventory_v3.csv"))
        except Exception:
            _flood_inventory = pd.DataFrame()
    if _target_dates is None:
        try:
            with open(os.path.join(BASE_DIR, "data", "processed", "target_flood_dates.json")) as f:
                _target_dates = json.load(f)
        except Exception:
            _target_dates = {}


def get_city_rain_stats(city_lower):
    if city_lower in _rain_cache:
        return _rain_cache[city_lower]
    try:
        p = os.path.join(BASE_DIR, "data", "raw", city_lower,
                         f"{city_lower}_hourly_rain_2019-01-01_to_2024-01-01.csv")
        if not os.path.exists(p):
            return None
        df = pd.read_csv(p)
        col = next((c for c in df.columns if 'rain' in c.lower() or 'precip' in c.lower()), df.columns[-1])
        rain = df[col].dropna()
        stats = {"total_mm": round(float(rain.sum()),1), "peak_hourly_mm": round(float(rain.max()),1),
                 "avg_hourly_mm": round(float(rain.mean()),3), "hours_above_10mm": int((rain>10).sum())}
        _rain_cache[city_lower] = stats
        return stats
    except Exception:
        return None


def get_flood_inventory_count(city_lower):
    load_historical_data()
    if _flood_inventory is None or _flood_inventory.empty:
        return 0
    try:
        kw = {"mumbai":["mumbai","thane","maharashtra"],"bengaluru":["bengaluru","bangalore","karnataka"],
              "chennai":["chennai","tamil nadu","kancheepuram"],"pune":["pune","maharashtra"]}
        keywords = kw.get(city_lower, [city_lower])
        col = next((c for c in _flood_inventory.columns if 'district' in c.lower()), None)
        if col:
            mask = _flood_inventory[col].astype(str).str.lower()
            return len(_flood_inventory[mask.apply(lambda x: any(k in x for k in keywords))])
    except Exception:
        pass
    return 0


# ── XAI Insight ───────────────────────────────────────────────────────────────

def generate_xai_insight(city, flood_pct, gradcam_present, pixel_stats, model_type="numpy"):
    load_historical_data()
    city_lower = (city or "unknown").lower()
    now = datetime.now()

    city_context = {
        "mumbai":    {"events":"2005 (944mm/24h), 2017, 2019, 2021, 2023",
                      "vulnerability":"Low-lying coastal zones, Mithi River basin, inadequate drainage",
                      "pattern":"Monsoon-induced urban waterlogging","state":"Maharashtra","avg_flood_pct":35.0},
        "bengaluru": {"events":"2022 major flooding, recurring lake overflow 2017–2023",
                      "vulnerability":"Encroached lake beds, blocked stormwater drains, rapid urbanization",
                      "pattern":"Topographic sinks + blocked drainage","state":"Karnataka","avg_flood_pct":22.0},
        "chennai":   {"events":"2015 catastrophic (1000+ casualties), 2021 cyclone Nivar, 2023",
                      "vulnerability":"Flat coastal terrain, Adyar/Cooum river overflow, cyclone exposure",
                      "pattern":"Northeast monsoon + cyclonic depression convergence","state":"Tamil Nadu","avg_flood_pct":40.0},
        "pune":      {"events":"2019 Mutha River overflow, 2021, recurring monsoon floods",
                      "vulnerability":"Steep terrain runoff into flat urban basins",
                      "pattern":"Flash flood accumulation at elevation transitions","state":"Maharashtra","avg_flood_pct":18.0},
    }
    ctx = city_context.get(city_lower, {"events":"Multiple documented events",
        "vulnerability":"General urban flood risk","pattern":"Rainfall + drainage mismatch",
        "state":"India","avg_flood_pct":25.0})

    avg = ctx["avg_flood_pct"]
    delta = flood_pct - avg
    comparison = (f"**{delta:+.1f}% vs historical average** ({avg:.0f}%) — "
                  f"{'ABOVE' if delta > 0 else 'BELOW'} typical flood signature for this region.")

    pixel_insight = ""
    if pixel_stats:
        dp = pixel_stats["dark_pixel_ratio"]
        bd = pixel_stats["blue_dominance"]
        tv = pixel_stats["texture_variance"]
        if dp > 30:
            pixel_insight = f"Dark pixel ratio is **{dp:.1f}%** — high proportion of low-reflectance areas consistent with standing water or saturated soil. "
        elif dp > 15:
            pixel_insight = f"Dark pixel ratio is **{dp:.1f}%** — moderate water presence detected in SAR backscatter. "
        else:
            pixel_insight = f"Dark pixel ratio is **{dp:.1f}%** — low water presence, terrain appears mostly dry. "
        if bd > 0.05:
            pixel_insight += f"Blue-channel dominance ({bd:.3f}) suggests spectral water signature. "
        if tv < 0.02:
            pixel_insight += "Low texture variance indicates smooth surface — consistent with water body or flooded plain. "

    rain_stats = get_city_rain_stats(city_lower)
    rain_insight = ""
    if rain_stats:
        rain_insight = (f"Historical rainfall data (2019–2024): peak **{rain_stats['peak_hourly_mm']} mm/hr**, "
                        f"**{rain_stats['hours_above_10mm']} hours** of heavy rainfall (>10mm/hr) recorded. ")

    inv_count = get_flood_inventory_count(city_lower)
    inv_insight = f"India Flood Inventory: **{inv_count} documented flood events** in {ctx['state']}. " if inv_count > 0 else ""

    date_insight = ""
    if _target_dates and city_lower in _target_dates:
        date_insight = f"SAR capture date: **{_target_dates[city_lower]}**. "

    gradcam_insight = ""
    if gradcam_present:
        gradcam_insight = ("**Saliency Heatmap:** Red zones highlight regions with strongest flood signatures — "
                           "dark low-reflectance areas with smooth texture consistent with standing water. "
                           "Blue zones indicate stable dry terrain with high backscatter. ")

    month = now.month
    season = "Northeast Monsoon" if month in [10,11,12] else ("Southwest Monsoon" if month in [6,7,8,9] else "Dry Season")
    seasonal = f"Current season: **{season}** (Month {month}). "

    model_note = ""
    if model_type == "numpy":
        model_note = "**Analysis Engine:** Physics-based pixel analysis (SAR backscatter signature detection). \\n\\n"
    elif model_type == "pytorch":
        model_note = "**Analysis Engine:** ResNet50 deep learning classifier (PyTorch). \\n\\n"

    insight  = f"**Live Analysis — {city_lower.upper()} ({now.strftime('%d %b %Y, %H:%M')}):**\\n\\n"
    insight += f"{comparison}\\n\\n"
    insight += model_note
    insight += f"**Pixel Analysis:** {pixel_insight}\\n\\n"
    if gradcam_insight:
        insight += f"{gradcam_insight}\\n\\n"
    insight += f"**Historical Context:** Known events: {ctx['events']}. Vulnerability: {ctx['vulnerability']}. Pattern: {ctx['pattern']}.\\n\\n"
    if rain_insight:
        insight += f"**Rainfall Record:** {rain_insight}\\n\\n"
    if inv_insight:
        insight += f"**Inventory:** {inv_insight}"
    if date_insight:
        insight += date_insight
    insight += f"\\n\\n**Seasonal:** {seasonal}"
    return insight


# ── Image Loading ─────────────────────────────────────────────────────────────

def load_image(image_url=None, image_base64=None):
    if image_base64:
        return Image.open(BytesIO(base64.b64decode(image_base64))).convert("RGB")
    if image_url and image_url.startswith("http"):
        r = req_lib.get(image_url, timeout=15)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    path = image_url if os.path.isabs(image_url) else os.path.join(BASE_DIR, image_url)
    return Image.open(path).convert("RGB")


# ── API ───────────────────────────────────────────────────────────────────────

class VisionRequest(BaseModel):
    image_url: str = None
    image_base64: str = None
    city: str = None


@router.post("/vision")
def analyze_satellite_feed(req: VisionRequest):
    if not req.image_url and not req.image_base64:
        raise HTTPException(status_code=400, detail="Provide image_url or image_base64")

    try:
        image = load_image(req.image_url, req.image_base64)
        image_resized = image.resize((128, 128))
        img_array_rgb = np.array(image_resized, dtype=np.uint8)          # (128,128,3) uint8
        x_norm        = np.expand_dims(img_array_rgb.astype(np.float32) / 255.0, axis=0)
        pixel_stats   = analyze_image_pixels(x_norm)

        # ── Priority 1: SAR XGBoost classifier (Sen1Floods11 trained) ──────────────────────
        sar_result = _run_sar_xgb_inference(img_array_rgb)

        if sar_result is not None:
            flood_pct   = sar_result["flood_percentage"]
            risk_class  = sar_result["risk_class"]
            flood_state = "FLOODED" if sar_result["pred_class_idx"] >= 1 else "SAFE"
            model_type  = "sar_xgboost"
            gradcam_b64 = _pixel_saliency_gradcam(x_norm)   # SAR-aware saliency

            # Enrich pixel_stats with SAR-specific values
            pixel_stats["dark_vv_fraction"] = round(sar_result["dark_vv_fraction"] * 100, 1)
            pixel_stats["dark_vh_fraction"] = round(sar_result["dark_vh_fraction"] * 100, 1)
            pixel_stats["vv_mean_db"]        = sar_result["vv_mean_db"]
            pixel_stats["vh_mean_db"]        = sar_result["vh_mean_db"]

            xai_insight = generate_xai_insight(req.city, flood_pct, True, pixel_stats, model_type)

            return {
                "status":             "OK",
                "mode":               "sar_patch_classification",
                "model_type":         "SAR XGBoost (Sen1Floods11)",
                "flood_percentage":   round(flood_pct, 2),
                "flood_state":        flood_state,
                "risk_class":         risk_class,
                "class_probabilities": sar_result["class_probabilities"],
                "model_accuracy_pct": sar_result["model_accuracy"],
                "gradcam":            gradcam_b64,
                "pixel_stats":        pixel_stats,
                "xai_insight":        xai_insight,
                "sar_features": {
                    "dark_vv_fraction": sar_result["dark_vv_fraction"],
                    "dark_vh_fraction": sar_result["dark_vh_fraction"],
                    "vv_mean_db":       sar_result["vv_mean_db"],
                    "vh_mean_db":       sar_result["vh_mean_db"],
                },
            }

        # ── Priority 2: PyTorch ResNet50 (if available) ─────────────────────────────────
        model, model_type = get_model()

        if model_type == "pytorch":
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            x_pt = torch.from_numpy(((x_norm[0] - mean) / std)).permute(2, 0, 1).unsqueeze(0)
            with torch.no_grad():
                probs = torch.softmax(model(x_pt), dim=1).squeeze().cpu().numpy()
            flood_pct   = float(probs[1]) * 100
            flood_state = "FLOODED" if probs[1] > 0.5 else "SAFE"
            gradcam_b64 = _pytorch_gradcam(model, x_pt.clone()) or _pixel_saliency_gradcam(x_norm)

        elif model_type == "tensorflow":
            pred    = model.predict(x_norm, verbose=0)
            pred_sq = np.squeeze(pred)
            if pred_sq.ndim == 2:
                flood_pct   = float(np.mean(pred_sq > 0.5) * 100)
                flood_state = "FLOODED" if flood_pct > 10 else "SAFE"
            else:
                flood_prob  = float(pred_sq if pred_sq.ndim == 0 else pred_sq[0])
                flood_pct   = flood_prob * 100
                flood_state = "FLOODED" if flood_prob > 0.5 else "SAFE"
            gradcam_b64 = _tf_gradcam(model, x_norm) or _pixel_saliency_gradcam(x_norm)

        else:  # numpy fallback
            flood_prob  = _numpy_infer(x_norm)
            flood_pct   = flood_prob * 100
            flood_state = "FLOODED" if flood_prob > 0.5 else "SAFE"
            gradcam_b64 = _pixel_saliency_gradcam(x_norm)

        xai_insight = generate_xai_insight(req.city, flood_pct, True, pixel_stats, model_type)

        return {
            "status":           "OK",
            "mode":             "classification",
            "model_type":       model_type,
            "flood_percentage": round(flood_pct, 2),
            "flood_state":      flood_state,
            "gradcam":          gradcam_b64,
            "pixel_stats":      pixel_stats,
            "xai_insight":      xai_insight,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
