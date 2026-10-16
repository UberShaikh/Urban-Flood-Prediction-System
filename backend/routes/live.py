import requests
from fastapi import APIRouter, HTTPException
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# India Standard Time offset (+05:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

router = APIRouter()

CITIES = {
    "pune": {"lat": 18.5204, "lon": 73.8567, "elevation": 560, "drain": 600},
    "mumbai": {"lat": 19.0760, "lon": 72.8777, "elevation": 14, "drain": 250},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946, "elevation": 920, "drain": 850},
    "chennai": {"lat": 13.0827, "lon": 80.2707, "elevation": 6, "drain": 180}
}

@router.get("/live/{city}")
def get_live_data(city: str, sim_date: str = None):
    city = city.lower()
    if city not in CITIES:
        city = "pune"
        
    cfg = CITIES[city]
    
    # Simulation Logic: Center the window on the target date to show transition
    if sim_date:
        dt_sim = datetime.datetime.strptime(sim_date, "%Y-%m-%d")
        # Fetch 5 days centered on sim_date
        start_date = (dt_sim - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = (dt_sim + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "precipitation",
            "timezone": "Asia/Kolkata"
        }
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
            "hourly": "precipitation",
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            "past_hours": 72,
            "forecast_hours": 24,
            "timezone": "Asia/Kolkata"
        }
    
    try:
        req = requests.get(url, params=params)
        req.raise_for_status()
        data = req.json()
        
        times = data["hourly"]["time"]
        precip = data["hourly"]["precipitation"]

        # Extract real current weather values (live mode only)
        current = data.get("current", {})
        real_temp     = current.get("temperature_2m", None)
        real_humidity = current.get("relative_humidity_2m", None)
        real_wind     = current.get("wind_speed_10m", None)
        real_precip_now = current.get("precipitation", None)
        
        # In simulation mode, we define "now" as sim_date at 12:00 PM IST
        if sim_date:
            ref_now = datetime.datetime.strptime(sim_date, "%Y-%m-%d").replace(
                hour=12, tzinfo=IST
            )
        else:
            # Use current IST time — matches Open-Meteo's Asia/Kolkata timezone
            ref_now = datetime.datetime.now(tz=IST)
            
        visual_series = []
        hist_rain = []
        forecast_rain = []
        
        for t, p in zip(times, precip):
            dt = datetime.datetime.fromisoformat(t)
            # Attach IST timezone if the parsed datetime is naive (Open-Meteo v1 returns naive ISO strings)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)
            is_forecast = dt > ref_now
            
            # Fill the 72h historical block (up to ref_now)
            if not is_forecast and dt >= (ref_now - datetime.timedelta(hours=72)):
                hist_rain.append(p)
                
            # Fill the 24h forecast block (after ref_now)
            if is_forecast and dt <= (ref_now + datetime.timedelta(hours=24)):
                forecast_rain.append(p)

            visual_series.append({
                "time": dt.strftime("%a %H:00"),
                "mm": p,
                "is_forecast": is_forecast
            })
            
        return {
            "city": city,
            "elevation_m": cfg["elevation"],
            "drain_distance_m": cfg["drain"],
            "total_72h_rain": round(sum(hist_rain), 2),
            "total_24h_forecast": round(sum(forecast_rain), 2),
            "rainfall_72h": hist_rain[:72],
            "timeline": visual_series,
            "timestamp": ref_now.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": round(real_temp, 1) if real_temp is not None else None,
            "humidity":    round(real_humidity, 1) if real_humidity is not None else None,
            "wind":        round(real_wind, 1) if real_wind is not None else None,
            "precip_now":  round(real_precip_now, 2) if real_precip_now is not None else None,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/history/{city}")
def get_historical_weather(city: str, days: int = 7):
    city = city.lower()
    if city not in CITIES:
        city = "pune"
        
    cfg = CITIES[city]
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": cfg["lat"],
        "longitude": cfg["lon"],
        "hourly": "precipitation",
        "past_days": days,
        "forecast_hours": 0,
        "timezone": "Asia/Kolkata"
    }
    
    try:
        req = requests.get(url, params=params)
        req.raise_for_status()
        data = req.json()
        
        return {
            "city": city,
            "hourly_precip": data["hourly"]["precipitation"],
            "hourly_time": data["hourly"]["time"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/archive/{city}")
def get_archive_records(city: str, start_date: str, end_date: str):
    """
    Fetch historical data from the Archive API (back to 1940).
    Dates should be in YYYY-MM-DD format.
    """
    city = city.lower()
    if city not in CITIES:
        raise HTTPException(status_code=404, detail="City not tracked")
        
    cfg = CITIES[city]
    # Archive API uses a different base URL
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": cfg["lat"],
        "longitude": cfg["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata"
    }
    
    try:
        req = requests.get(url, params=params)
        req.raise_for_status()
        data = req.json()
        
        return {
            "city": city.upper(),
            "start": start_date,
            "end": end_date,
            "hourly_precip": data["hourly"]["precipitation"],
            "hourly_time": data["hourly"]["time"],
            "total_precipitation": round(sum(data["hourly"]["precipitation"]), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Archive API Error: {str(e)}")


@router.get("/live-feed/{city}")
def get_live_feed(city: str):
    """
    Fetch live feed with real news from News API for the last 30 days.
    Returns all news from India without any filtering.
    """
    city = city.lower()
    if city not in CITIES:
        city = "mumbai"
    
    cfg = CITIES[city]
    news_api_key = os.getenv("NEWS_API_KEY")
    
    # Fetch real news from News API
    news_items = []
    if news_api_key and news_api_key != "your_newsapi_key_here":
        try:
            # Calculate date range - last 30 days
            to_date = datetime.datetime.now(tz=IST)
            from_date = to_date - datetime.timedelta(days=30)
            
            # Fetch all news from India for the last 30 days
            news_url = "https://newsapi.org/v2/everything"
            news_params = {
                "apiKey": news_api_key,
                # Search for news from India (no specific keywords)
                "q": "India",
                "language": "en",
                "sortBy": "publishedAt",
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "pageSize": 100  # Get maximum allowed
            }
            
            news_response = requests.get(news_url, params=news_params, timeout=10)
            
            print(f"News API Request URL: {news_response.url}")
            print(f"News API Status: {news_response.status_code}")
            
            if news_response.status_code == 200:
                news_data = news_response.json()
                total_articles = len(news_data.get("articles", []))
                print(f"News API returned {total_articles} articles")
                
                for article in news_data.get("articles", []):
                    # Filter out articles without proper content
                    if not article.get("title") or article.get("title") == "[Removed]":
                        continue
                    if not article.get("url"):
                        continue
                    
                    # Parse published date
                    pub_date = article.get("publishedAt", "")
                    
                    news_items.append({
                        "type": "news",
                        "title": article.get("title", "Untitled"),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "time": pub_date,
                        "location": city.title(),
                        "url": article.get("url", "#"),
                        "description": article.get("description", "")[:200] if article.get("description") else ""
                    })
                
                print(f"Total articles collected: {len(news_items)}")
                
                # Sort by date (newest first) and limit to 50
                news_items = sorted(news_items, key=lambda x: x["time"], reverse=True)[:50]
                print(f"Final result: {len(news_items)} articles")
            else:
                print(f"News API error: {news_response.status_code}")
                print(f"Response: {news_response.text[:500]}")
        
        except Exception as e:
            print(f"Error fetching news: {str(e)}")
    
    # If no news found, add a placeholder message
    if not news_items:
        print("No news found for the last 30 days.")
        news_items = []
    
    # Fetch current weather data for weather events
    weather_events = []
    try:
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
            "current": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m",
            "hourly": "precipitation",
            "past_hours": 3,
            "forecast_hours": 1,
            "timezone": "Asia/Kolkata"
        }
        
        weather_response = requests.get(weather_url, params=weather_params, timeout=10)
        
        if weather_response.status_code == 200:
            weather_data = weather_response.json()
            current = weather_data.get("current", {})
            
            # Current precipitation
            precip = current.get("precipitation", 0)
            wind = current.get("wind_speed_10m", 0)
            temp = current.get("temperature_2m", 0)
            humidity = current.get("relative_humidity_2m", 0)
            
            current_time = datetime.datetime.now(tz=IST).isoformat()
            
            # Create weather event if significant precipitation
            if precip > 5:
                severity = "HIGH" if precip > 15 else "MEDIUM" if precip > 10 else "LOW"
                weather_events.append({
                    "type": "weather",
                    "title": f"⚠ {'Heavy' if precip > 15 else 'Moderate'} rainfall {precip}mm/hr detected — {city.title()}",
                    "source": "Open-Meteo Live",
                    "time": current_time,
                    "location": city.title(),
                    "severity": severity
                })
            
            # High wind event
            if wind > 40:
                weather_events.append({
                    "type": "weather",
                    "title": f"💨 High wind speed {wind}km/h — {city.title()}",
                    "source": "Open-Meteo Live",
                    "time": current_time,
                    "location": city.title(),
                    "severity": "MEDIUM"
                })
            
            # High humidity + temperature (potential storm)
            if humidity > 85 and temp > 28:
                weather_events.append({
                    "type": "weather",
                    "title": f"🌧 Storm conditions detected: {humidity}% humidity, {temp}°C — {city.title()}",
                    "source": "Open-Meteo Live",
                    "time": current_time,
                    "location": city.title(),
                    "severity": "MEDIUM"
                })
                
    except Exception as e:
        print(f"Error fetching weather: {str(e)}")
    
    # Generate AI alerts based on current conditions
    ai_alerts = []
    try:
        # Fetch recent rainfall data
        live_url = "https://api.open-meteo.com/v1/forecast"
        live_params = {
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
            "hourly": "precipitation",
            "past_hours": 72,
            "forecast_hours": 24,
            "timezone": "Asia/Kolkata"
        }
        
        live_response = requests.get(live_url, params=live_params, timeout=10)
        
        if live_response.status_code == 200:
            live_data = live_response.json()
            precip_data = live_data["hourly"]["precipitation"]
            
            # Calculate 72h rainfall
            rainfall_72h = sum(precip_data[:72])
            forecast_24h = sum(precip_data[72:96]) if len(precip_data) > 72 else 0
            
            current_time = datetime.datetime.now(tz=IST).isoformat()
            
            # High rainfall accumulation alert
            if rainfall_72h > 100:
                ai_alerts.append({
                    "type": "ai_alert",
                    "title": f"🧠 AI: 72h rainfall saturation {round(rainfall_72h, 1)}mm — drainage stress detected",
                    "source": "LSTM Temporal Model",
                    "time": current_time,
                    "location": city.title(),
                    "severity": "HIGH" if rainfall_72h > 150 else "MEDIUM"
                })
            
            # Low elevation risk
            if cfg["elevation"] < 20:
                ai_alerts.append({
                    "type": "ai_alert",
                    "title": f"🧠 AI: Low elevation zone ({cfg['elevation']}m MSL) — flood accumulation risk",
                    "source": "Spatial Clustering",
                    "time": current_time,
                    "location": city.title(),
                    "severity": "MEDIUM"
                })
            
            # Forecast-based alert
            if forecast_24h > 50:
                ai_alerts.append({
                    "type": "ai_alert",
                    "title": f"🧠 AI: Heavy rainfall forecast {round(forecast_24h, 1)}mm in next 24h — prepare for flooding",
                    "source": "XGBoost Fusion v2",
                    "time": current_time,
                    "location": city.title(),
                    "severity": "HIGH"
                })
                
    except Exception as e:
        print(f"Error generating AI alerts: {str(e)}")
    
    # Calculate early warning system score
    ews_score = 0
    ews_factors = []
    
    # Check conditions
    try:
        if weather_events:
            for event in weather_events:
                if event.get("severity") == "HIGH":
                    ews_score += 1
                    ews_factors.append(event["title"].split("—")[0].strip())
        
        if ai_alerts:
            for alert in ai_alerts:
                if alert.get("severity") == "HIGH":
                    ews_score += 1
                    ews_factors.append(alert["title"].split("—")[0].strip())
    except:
        pass
    
    # Determine EWS status
    if ews_score >= 3:
        ews_status = "HIGH RISK"
        ews_color = "#cc4444"
        ews_action = "⚠ Evacuate low-lying areas. Move to nearest safe zone immediately."
    elif ews_score >= 2:
        ews_status = "MODERATE RISK"
        ews_color = "#c08030"
        ews_action = "⚠ Stay alert. Avoid travel to flood-prone areas. Monitor updates."
    elif ews_score >= 1:
        ews_status = "LOW RISK"
        ews_color = "#d4924a"
        ews_action = "ℹ Conditions improving. Continue monitoring weather updates."
    else:
        ews_status = "SAFE"
        ews_color = "#2a8a4a"
        ews_action = "✓ No immediate flood risk. Normal operations."
    
    # Generate risk timeline (simplified)
    timeline = [
        {"hour": "1h", "risk": min(ews_score * 20 + 10, 85)},
        {"hour": "3h", "risk": min(ews_score * 25, 90)},
        {"hour": "6h", "risk": max(ews_score * 15, 20)},
    ]
    
    return {
        "news": news_items[:50],  # Return up to 50 articles (full month of news)
        "weather_events": weather_events,
        "ai_alerts": ai_alerts,
        "early_warning": {
            "score": min(ews_score, 4),
            "status": ews_status,
            "color": ews_color,
            "action": ews_action,
            "factors": ews_factors[:5],  # Top 5 factors
            "timeline": timeline
        }
    }
