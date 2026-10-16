# -*- coding: utf-8 -*-
from fastapi import APIRouter
from pydantic import BaseModel
from .live import get_live_data, CITIES
from .predict import predict_flood, PredictionRequest
import google.generativeai as genai
import os
import re
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
if not TARGET_MODEL.startswith("models/"):
    TARGET_MODEL = f"models/{TARGET_MODEL}"
IS_LLM_ACTIVE = False

print("\n" + "="*60)
print("[System] AQUA-AI: PERFORMING AGENTIC HANDSHAKE")

if API_KEY and API_KEY != "YOUR_KEY_HERE":
    try:
        genai.configure(api_key=API_KEY)
        # Verify model access
        model = genai.GenerativeModel(TARGET_MODEL)
        IS_LLM_ACTIVE = True
        print(f"[OK] [System] AQUA-AI ACTIVE: {TARGET_MODEL}")
    except Exception as e:
        print(f"[Error] [System] AQUA-AI Init error: {e}")
else:
    print("[Info] [System] No GEMINI_API_KEY found. Safe Mode Ready.")

if not IS_LLM_ACTIVE:
    print("[Warning] [System] AQUA-AI: FALLBACK SAFE MODE ACTIVE")
print("="*60 + "\n")

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    city: str = "mumbai"
    context_city: Optional[str] = None

# --- ANALYTICAL TOOLBOX ---

class FloodAnalyticsTools:
    @staticmethod
    def get_risk_data(city: str, date: Optional[str] = None):
        """Analytical tool for fetching regional flood risk, telemetry, and metrics."""
        try:
            city = city.lower().strip()
            if city not in CITIES: city = "mumbai"
            
            # Smart Date Resolution
            weather = get_live_data(city, sim_date=date)
            
            req = PredictionRequest(
                rainfall_72h=weather["rainfall_72h"],
                forecast_24h=weather["total_24h_forecast"],
                elevation_m=weather["elevation_m"],
                drain_distance_m=weather["drain_distance_m"]
            )
            prediction = predict_flood(req)
            
            # Derived insights for the LLM
            sat = (weather["total_72h_rain"] / 100.0) * 100
            load = (weather["total_24h_forecast"] / 50.0) * 100
            
            return {
                "status": "SUCCESS",
                "city": city.upper(),
                "date": date or "LIVE (IST)",
                "telemetry": {
                    "rain_72h_mm": weather["total_72h_rain"],
                    "forecast_24h_mm": weather["total_24h_forecast"],
                    "elevation_msl": weather["elevation_m"],
                    "drain_dist_m": weather["drain_distance_m"],
                    "soil_saturation_pct": round(min(sat, 100), 1),
                    "drain_load_pct": round(min(load, 100), 1)
                },
                "model_output": {
                    "risk_probability": prediction["flood_probability"],
                    "alert_level": prediction["final_alert_level"],
                    "recommendation": prediction["recommended_action"]
                }
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"Tool Failure: {str(e)}"}

def get_risk_data(city: str, date: Optional[str] = None):
    return FloodAnalyticsTools.get_risk_data(city, date)

SYSTEM_PROMPT = f"""You are AquaAlert Dispatcher, an agentic AI assistant for the Urban Flood Prediction System.
CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
TIMEZONE: India Standard Time (IST)

CORE PROTOCOLS:
1. DOMAIN GUARDRAIL: Only answer flood, rainfall, climate, and disaster resilience queries. Redirect others.
2. FACTUAL GROUNDING: ALWAYS call 'get_risk_data' for city status or flood risk queries. Never hallucinate risk scores.
3. TEMPORAL AWARENESS: If the user mentions "today", "yesterday", or a specific date, pass it to the tool as YYYY-MM-DD.
4. TECHNICAL DEPTH: Explain terms like "MSL Elevation" and "Drainage Proximity" when they contribute to risk.
5. RECOMMENDATION: Always prioritize human safety based on the tool's 'recommendation' field.

STRICT TONE: Clinical, analytical, and urgent when risk is HIGH."""

@router.post("/chat")
def agentic_assistant(req: ChatRequest):
    try:
        # Fallback if LLM is offline
        if not IS_LLM_ACTIVE:
            msg = req.message.lower()
            city = req.city or "mumbai"
            for c in CITIES.keys():
                if c in msg: city = c
            
            target_date = None
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})|(\d{4}-\d{2}-\d{2})', msg)
            if date_match:
                raw_date = date_match.group(0)
                if "/" in raw_date:
                    d, m, y = raw_date.split("/")
                    target_date = f"{y}-{m}-{d}"
                else:
                    target_date = raw_date
            
            if not any(k in msg for k in ["flood", "rain", "risk", "status", "hi", "hello"]):
                return { "reply": "I am AquaAlert AI. (Guardrail Active: Analytical Mode Only)", "is_llm": False }
            
            data = FloodAnalyticsTools.get_risk_data(city, date=target_date)
            p = data.get("model_output", {})
            reply = f"**AquaAlert AI (Analytical Mode)**\nCity: {city.upper()} | Risk: {p.get('risk_probability', 0)}% | Status: {p.get('alert_level', 'UNKNOWN')}\nRecommendation: {p.get('recommendation', 'N/A')}"
            return { "reply": reply, "city": city, "is_llm": False }

        # --- AGENTIC AI LOOP ---
        model = genai.GenerativeModel(
            model_name=TARGET_MODEL,
            tools=[get_risk_data],
            system_instruction=SYSTEM_PROMPT
        )
        
        gemini_history = []
        for h in req.history:
            gemini_history.append({"role": "user" if h["role"] == "user" else "model", "parts": [h["text"]]})

        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
        response = chat.send_message(req.message)
        
        # Log tool calls for transparency
        for content in chat.history[-2:]:
            for part in content.parts:
                if hasattr(part, 'function_call'):
                    print(f">>> [Agent] TOOL CALL: {part.function_call.name}")

        detected_city = req.context_city
        for c in CITIES.keys():
            if c in req.message.lower(): detected_city = c

        return { "reply": response.text, "city": detected_city, "is_llm": True }

    except Exception as e:
        print(f"ERROR [Agent Loop]: {str(e)}")
        return { "reply": f"AI Engine Logic Error: {str(e)}", "error": True, "is_llm": IS_LLM_ACTIVE }
