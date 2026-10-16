import os
from services.escalation import send_emergency_email
from dotenv import load_dotenv

load_dotenv()

# Mock data for testing
city = "mumbai"
flood_data = {
    "probability": 84.5,
    "forecast_24h": 120,
    "total_rain_72h": 340,
    "trend": "[UP] Rising",
    "risk_level": "HIGH RISK - DANGER",
    "sar_validation": "Flood Detected",
}

safe_zones = [
    {
        "name": "KEM Hospital",
        "address": "Parel, Mumbai",
        "risk_state": "SAFE",
        "risk_color": "#16a34a",
        "safety_score": 94.2,
        "elevation_m": 18,
        "recommendation_rank": 1
    },
    {
        "name": "Dharavi Relief Camp",
        "address": "Dharavi, Mumbai",
        "risk_state": "SAFE",
        "risk_color": "#16a34a",
        "safety_score": 88.5,
        "elevation_m": 12,
        "recommendation_rank": 2
    }
]

print("🚀 Starting manual escalation email test...")
success = send_emergency_email(city, flood_data, safe_zones)

if success:
    print("✅ SUCCESS: Emergency email dispatched successfully!")
else:
    print("❌ FAILED: Check SMTP settings or .env configuration.")
