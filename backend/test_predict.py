import requests
import json

url = "http://localhost:8000/api/v1/predict"
payload = {
    "rainfall_72h": [1.0] * 72,
    "forecast_24h": 68.4,
    "elevation_m": 14,
    "drain_distance_m": 250
}
try:
    response = requests.post(url, json=payload)
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
