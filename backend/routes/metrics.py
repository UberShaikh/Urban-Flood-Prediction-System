import os
import json
from fastapi import APIRouter

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
METRICS_FILE = os.path.join(BASE_DIR, "models", "metrics.json")

@router.get("/metrics")
def get_metrics():
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Fallback default if file is missing/corrupted
    return {
        "lstm_accuracy": "N/A",
        "resnet50_accuracy": "N/A"
    }
