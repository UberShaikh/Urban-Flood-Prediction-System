import os
import numpy as np
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from tensorflow.keras.models import load_model

# 1. Initialize the FastAPI App
app = FastAPI(
    title="Urban Flood Early Warning System API",
    description="Live inference engine using LSTM + XGBoost Fusion Architecture",
    version="1.0"
)

# Define Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
lstm_path = os.path.join(project_root, "models", "temporal", "pune_lstm_v1.keras")
xgb_path = os.path.join(project_root, "models", "fusion", "xgboost_decision_layer.json")

# Global variables to hold our models in memory
lstm_model = None

xgb_model = None

# 2. Load Models on Startup
@app.on_event("startup")
def load_brains():
    global lstm_model, xgb_model
    print("Booting up AI Engine...")
    
    try:
        lstm_model = load_model(lstm_path)
        print(" -> LSTM Temporal Model loaded successfully.")
    except Exception as e:
        print(f" -> ERROR loading LSTM: {e}")
        
    try:
        xgb_model = xgb.XGBClassifier()
        xgb_model.load_model(xgb_path)
        print(" -> XGBoost Fusion Model loaded successfully.")
    except Exception as e:
        print(f" -> ERROR loading XGBoost: {e}")

# 3. Define the Expected Incoming Data (The Payload)
class FloodRequest(BaseModel):
    # We expect exactly 72 hours of rain data (our sliding window size)
    rainfall_72h: list[float] = Field(..., min_length=72, max_length=72, description="Hourly rainfall in mm for the last 72 hours")
    elevation_m: float = Field(..., description="Elevation of the location in meters")
    drain_distance_m: float = Field(..., description="Distance to nearest major drain in meters")

# 4. The Prediction Endpoint
@app.post("/predict")
def predict_flood_risk(request: FloodRequest):
    if lstm_model is None or xgb_model is None:
        raise HTTPException(status_code=500, detail="AI Models are not fully loaded into memory.")
    
    try:
        # --- PHASE 1: Temporal Prediction (LSTM) ---
        # The LSTM expects a 3D Tensor: (Samples, TimeSteps, Features) -> (1, 72, 1)
        rain_array = np.array(request.rainfall_72h).reshape(1, 72, 1)
        
        # In production, we'd scale this rain data using the MinMaxScaler we saved earlier.
        # For this PoC, we will assume the data coming in is raw and pass it.
        # (Note: Neural nets prefer scaled 0-1 data, but we'll bypass the scaler for testing logic)
        lstm_prob = float(lstm_model.predict(rain_array, verbose=0)[0][0])
        
        # --- PHASE 2: Fusion Decision (XGBoost) ---
        # XGBoost expects a 2D array: [[prob, elevation, distance]]
        fusion_features = np.array([[lstm_prob, request.elevation_m, request.drain_distance_m]])
        
        # Predict the final class (0: Low, 1: Medium, 2: High)
        final_class = int(xgb_model.predict(fusion_features)[0])
        
        risk_map = {0: "LOW RISK", 1: "MEDIUM RISK", 2: "HIGH RISK"}
        
        # --- PHASE 3: The Response ---
        return {
            "status": "success",
            "lstm_flood_probability": round(lstm_prob * 100, 2),
            "spatial_profile": {
                "elevation": request.elevation_m,
                "drain_distance": request.drain_distance_m
            },
            "final_alert_level": risk_map[final_class]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {str(e)}")