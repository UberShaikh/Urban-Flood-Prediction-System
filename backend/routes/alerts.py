from fastapi import APIRouter, BackgroundTasks
from .live import CITIES, get_live_data, IST
from .predict import predict_flood, PredictionRequest
from .safe_zones import get_safe_zones
from services.escalation import send_emergency_email
from services.twilio_sms import send_emergency_sms
import datetime

router = APIRouter()

import numpy as np

@router.get("/alerts")
def get_alerts(background_tasks: BackgroundTasks, sim_date: str = None):
    alerts = []
    
    # Check if this is the specific demo date requested by the user
    is_demo_2017 = sim_date == "2017-08-29"

    for city_name in CITIES.keys():
        try:
            # 1. Get live weather data
            weather = get_live_data(city_name, sim_date=sim_date)
            
            # 2. Extract base values
            total_rain = weather["total_72h_rain"]
            forecast = weather["total_24h_forecast"]
            elevation = weather["elevation_m"]
            drain = weather["drain_distance_m"]

            # DEMO OVERRIDE: If it's the specific Mumbai 2017 flood demo date, 
            # we use the exact values requested by the user.
            if is_demo_2017 and city_name.lower() == "mumbai":
                total_rain = 18.0
                forecast = 42.0
                # We'll also force the prediction logic to yield 63% later
            
            # 3. Get prediction
            req = PredictionRequest(
                rainfall_72h=weather["rainfall_72h"],
                forecast_24h=forecast,
                elevation_m=elevation,
                drain_distance_m=drain,
                city=city_name,
            )
            prediction = predict_flood(req)
            
            # Force 63% for the demo
            if is_demo_2017 and city_name.lower() == "mumbai":
                prediction["flood_probability"] = 63.0
                prediction["final_alert_level"] = "MODERATE RISK - MONITOR"
                prediction["recommended_action"] = "Monitor rising water levels and prepare for potential evacuation."

            # 4. Generate historical points & Trend
            history_points = []
            base_prob = prediction["flood_probability"]
            
            # Logic for trend: Rising ONLY if significant risk (>5%) OR significant forecast (>10mm)
            if is_demo_2017 and city_name.lower() == "mumbai":
                trend = "Rising"
                trend_icon = "[UP]"
            else:
                # Determine "Rising" status based on actual danger thresholds
                is_rising = (forecast > 10) or (base_prob > 5)
                trend = "Rising" if is_rising else "Stable"
                trend_icon = "[UP]" if trend == "Rising" else "[STABLE]"

            for i in range(5):
                # Simulate past 5 days of risk
                var = (4 - i) * 6 + (np.random.random() * 8)
                ref_dt = datetime.datetime.now(tz=IST) if not sim_date else datetime.datetime.strptime(sim_date, "%Y-%m-%d").replace(tzinfo=IST)
                history_points.append({
                    "date": (ref_dt - datetime.timedelta(days=5-i)).strftime("%d %b"),
                    "prob": max(0, min(100, base_prob - var))
                })

            # 5. SAR Validation Stub
            # In a real system, this would query the vision module for recent satellite checks
            sar_status = "No Active Flood"
            if prediction["flood_probability"] > 80:
                sar_status = "Flood Detected"
            elif is_demo_2017 and city_name.lower() == "mumbai":
                sar_status = "No Active Flood" # User specifically requested this for the demo

            alert_obj = {
                "city": city_name.upper(),
                "risk_level": prediction["final_alert_level"],
                "probability": prediction["flood_probability"],
                "action": prediction["recommended_action"],
                "total_rain_72h": total_rain,
                "forecast_24h": forecast,
                "trend": f"{trend_icon} {trend}",
                "sar_validation": sar_status,
                "timestamp": weather["timestamp"],
                "history": history_points,
                "id": f"alert_{city_name}_{datetime.datetime.now(tz=IST).strftime('%H%M%S')}",
                "escalation_status": "PENDING"
            }

            # 6. Escalation logic: Dispatch email + SMS if risk is MONITOR or DANGER
            if base_prob >= 30:
                # Fetch safe zones for both email and SMS
                sz_data   = get_safe_zones(city_name)
                top_zones = sz_data.get("top_recommendations", [])

                # Fetch high-risk areas to evacuate from the flood risk engine
                evacuate_areas = []
                try:
                    import os, pandas as pd
                    from ml_engine.flood_risk_engine import run_flood_risk_pipeline
                    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    FILE_MAP = {
                        "mumbai":    "mumbai_flood_data.csv",
                        "bengaluru": "bangalore_flood_data.csv",
                        "chennai":   "chennai_flood_data.csv",
                        "pune":      "pune_flood_data.csv",
                    }
                    csv_path = os.path.join(BASE_DIR, "..", "Data_Urban", FILE_MAP.get(city_name.lower(), ""))
                    if os.path.exists(csv_path):
                        df = pd.read_csv(csv_path)
                        for col in ["Elevation_m","Urban_Density_sqkm","Drain_Distance_m",
                                    "Historical_Rainfall_mm","Water_Logging_Zones",
                                    "Near_River","Near_Coastline","Flood_Hotspot"]:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                        pipeline = run_flood_risk_pipeline(
                            city_name.lower(), base_prob,
                            weather["total_72h_rain"],
                            df.to_dict("records")
                        )
                        # Top areas with risk_score > 25 (Moderate and above)
                        evacuate_areas = [
                            {
                                "name":       a["Area"],
                                "risk_score": round(a["risk_score"], 1),
                                "category":   a["category"],
                                "elevation_m": a.get("Elevation_m", 0),
                                "waterlog":   a.get("Water_Logging_Zones", 0),
                            }
                            for a in pipeline["ranked_areas"]
                            if a["risk_score"] > 25
                        ][:8]   # top 8 at-risk areas
                except Exception as ae:
                    print(f"[alerts] Could not fetch evacuate areas for {city_name}: {ae}")

                # Dispatch email in background (existing)
                background_tasks.add_task(
                    send_emergency_email, city_name, alert_obj, top_zones, evacuate_areas
                )

                # Dispatch SMS in background (parallel to email)
                background_tasks.add_task(
                    send_emergency_sms, city_name, alert_obj, top_zones, evacuate_areas
                )

                alert_obj["escalation_status"]    = "DISPATCHED"
                alert_obj["authorities_notified"] = ["Municipal Commissioner", "NDRF Base", "Regional EOC"]
                alert_obj["top_recommendations"]  = top_zones
                alert_obj["evacuate_areas"]        = evacuate_areas
                alert_obj["channels"]              = ["email", "whatsapp"]

            alerts.append(alert_obj)
        except Exception as e:
            print(f"Failed to generate alert for {city_name}: {e}")
            
    alerts = sorted(alerts, key=lambda x: x["probability"], reverse=True)
    
    return {
        "status": "SUCCESS",
        "alerts": alerts,
        "summary": {
            "critical": len([a for a in alerts if "DANGER" in a["risk_level"]]),
            "warning": len([a for a in alerts if "MONITOR" in a["risk_level"]]),
            "clear": len([a for a in alerts if "SAFE" in a["risk_level"]])
        }
    }
