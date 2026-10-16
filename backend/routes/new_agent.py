# -*- coding: utf-8 -*-
"""
AquaAlert Agentic AI - Extended with:
  1. Real-time news fetching (GDELT API, no key required)
  2. Urban planning advisor (drainage gap analysis + mitigation suggestions)
  3. Emergency action protocol (structured "why + what to do" reasoning)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from .live import get_live_data, CITIES
from .predict import predict_flood, PredictionRequest
import google.generativeai as genai
import os
import re
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
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


# ============================================================
# TOOL 1: Risk Data (existing — unchanged)
# ============================================================
class FloodAnalyticsTools:
    @staticmethod
    def get_risk_data(city: str, date: Optional[str] = None):
        """Fetch real-time flood risk score, telemetry, and ML prediction for a city."""
        try:
            city = city.lower().strip()
            if city not in CITIES:
                city = "mumbai"

            weather = get_live_data(city, sim_date=date)
            req = PredictionRequest(
                rainfall_72h=weather["rainfall_72h"],
                forecast_24h=weather["total_24h_forecast"],
                elevation_m=weather["elevation_m"],
                drain_distance_m=weather["drain_distance_m"],
                city=city,
            )
            prediction = predict_flood(req)
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


# ============================================================
# TOOL 2: News Fetcher (NEW) — uses GDELT (free, no API key)
# ============================================================
def fetch_flood_news(city: str, max_results: int = 5):
    """
    Fetch the latest verified news about floods/rainfall in a specified Indian city.
    Returns up to 5 articles with title, source, date, and URL.

    Uses GDELT 2.0 Doc API — free, no API key needed, indexes 100,000+ news sources globally.
    """
    try:
        city = city.lower().strip()
        if city not in CITIES:
            city = "mumbai"

        # GDELT query: city + flood/rain terms, India domain, last 7 days
        query = f'"{city}" (flood OR flooding OR rainfall OR waterlogging OR monsoon) sourcecountry:IN'
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": max_results * 2,  # over-fetch for filtering
            "format": "json",
            "sort": "datedesc",  # newest first
            "timespan": "7d"  # last 7 days
        }
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return _news_fallback(city, "GDELT API unreachable")

        data = r.json()
        articles = data.get("articles", [])
        if not articles:
            return _news_fallback(city, "No recent news indexed")

        # Trusted Indian sources (filter for credibility)
        trusted_domains = [
            "timesofindia", "hindustantimes", "ndtv", "indianexpress",
            "thehindu", "deccanherald", "mid-day", "mumbaimirror",
            "punemirror", "reuters", "bbc", "aljazeera", "scroll.in",
            "thewire.in", "news18", "indiatoday"
        ]

        seen_titles = set()
        results = []
        for art in articles:
            title = art.get("title", "").strip()
            domain = art.get("domain", "").lower()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            # Prefer trusted domains
            is_trusted = any(td in domain for td in trusted_domains)

            results.append({
                "title": title[:200],
                "source": art.get("domain", "unknown"),
                "date": art.get("seendate", ""),
                "url": art.get("url", ""),
                "trusted": is_trusted
            })
            if len(results) >= max_results:
                break

        # Re-sort: trusted first, then by recency
        results.sort(key=lambda x: (not x["trusted"], x["date"]), reverse=False)

        return {
            "status": "SUCCESS",
            "city": city.upper(),
            "article_count": len(results),
            "timespan": "last 7 days",
            "articles": results
        }
    except requests.exceptions.Timeout:
        return _news_fallback(city, "Request timed out")
    except Exception as e:
        return _news_fallback(city, f"Fetch error: {str(e)}")


def _news_fallback(city: str, reason: str):
    """Graceful fallback when news API is unavailable."""
    return {
        "status": "DEGRADED",
        "city": city.upper(),
        "reason": reason,
        "advice": f"Live news feed unavailable. Please check official IMD or {city.upper()} Municipal Corporation updates directly."
    }


# ============================================================
# TOOL 3: Emergency Action Protocol (NEW)
# ============================================================
def get_emergency_protocol(city: str, situation: str = "general"):
    """
    Generate a prioritized emergency action checklist for a flood situation.
    Combines current risk data with the reported situation (e.g., "water at doorstep").

    Args:
      city: One of mumbai, pune, bengaluru, chennai
      situation: Free-text description (e.g., "water reaching doorstep", "stuck in basement")
    """
    try:
        city = city.lower().strip()
        if city not in CITIES:
            city = "mumbai"

        # Pull live risk
        risk_data = FloodAnalyticsTools.get_risk_data(city)
        telemetry = risk_data.get("telemetry", {})
        alert = risk_data.get("model_output", {}).get("alert_level", "UNKNOWN")
        risk_pct = risk_data.get("model_output", {}).get("risk_probability", 0)

        # Tiered action checklists
        immediate_actions = []
        short_term_actions = []
        reasoning_parts = []

        # Reasoning logic
        elev = telemetry.get("elevation_msl", 50)
        rain_72h = telemetry.get("rain_72h_mm", 0)
        forecast_24h = telemetry.get("forecast_24h_mm", 0)
        drain_dist = telemetry.get("drain_dist_m", 500)

        if elev < 20:
            reasoning_parts.append(
                f"Your area sits at only {elev}m above sea level — coastal/floodplain zone where runoff drains slowly."
            )
        if rain_72h > 80:
            reasoning_parts.append(
                f"{rain_72h}mm of rain has fallen in the last 72 hours, saturating soil and overloading drainage."
            )
        if forecast_24h > 50:
            reasoning_parts.append(
                f"An additional {forecast_24h}mm is forecast in the next 24 hours."
            )
        if drain_dist > 400:
            reasoning_parts.append(
                f"The nearest major storm drain is {drain_dist}m away — local runoff has nowhere fast to go."
            )

        # Actions based on alert level
        if alert == "HIGH" or "water" in situation.lower() or "doorstep" in situation.lower():
            immediate_actions = [
                "POWER: Cut electricity at the main breaker BEFORE water enters — touching wet outlets kills.",
                "GAS: Turn off the main gas valve. Submerged appliances can leak.",
                "VERTICAL EVAC: Move to the highest floor. Do NOT enter basements or underpasses.",
                "AVOID DRIVING: 6 inches of moving water can sweep away a person; 2 feet can move a car.",
                "CALL: NDRF helpline 011-26701700 / Local control room. Share your exact location.",
                "STAY CONNECTED: Charge phones now. Use SMS if calls fail (lower bandwidth).",
                "DOCUMENTS: Seal IDs, passports, medical records in waterproof bag — take with you.",
            ]
            short_term_actions = [
                "Stock 3 days of drinking water (4L per person per day).",
                "Identify two evacuation routes uphill from your location.",
                "Place sandbags or rolled wet towels at door thresholds (slows seepage).",
                "Boil all tap water for 5 minutes before drinking once flooding starts.",
            ]
        elif alert == "MODERATE":
            immediate_actions = [
                "Move vehicles to higher ground or covered parking now.",
                "Clear nearby storm drains of debris — leaves, plastic, garbage worsen flooding.",
                "Keep phones, power banks, and torches charged.",
                "Monitor IMD and your city's municipal Twitter feed every 2 hours.",
            ]
            short_term_actions = [
                "Prepare a go-bag: meds, IDs, water, snacks, change of clothes.",
                "Identify the nearest official shelter or safe building.",
                "Check insurance documents and photograph valuables for records.",
            ]
        else:
            immediate_actions = [
                "Current risk is LOW. Continue normal activity but stay weather-aware.",
                "Review your household flood plan and update emergency contacts.",
            ]
            short_term_actions = [
                "Inspect your home's drainage and seal any cracks before next monsoon.",
                "Sign up for IMD city alerts and AquaAlert notifications.",
            ]

        return {
            "status": "SUCCESS",
            "city": city.upper(),
            "alert_level": alert,
            "risk_probability": risk_pct,
            "user_situation": situation,
            "reasoning": " ".join(reasoning_parts) if reasoning_parts else "Conditions appear normal.",
            "immediate_actions": immediate_actions,
            "short_term_actions": short_term_actions,
            "emergency_contacts": {
                "NDRF": "011-26701700",
                "National Disaster": "108",
                "IMD weather": "1800-180-1717"
            }
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


# ============================================================
# TOOL 4: Urban Planning Advisor (NEW)
# ============================================================
def get_urban_planning_advice(city: str, area_description: Optional[str] = None):
    """
    Analyze the urban layout of a city zone and recommend infrastructure
    interventions (bioswales, sponge city features, decentralized drainage)
    based on elevation, drainage proximity, and rainfall load.

    Args:
      city: mumbai, pune, bengaluru, chennai
      area_description: Optional free-text description like "dense residential, near coast"
    """
    try:
        city = city.lower().strip()
        if city not in CITIES:
            city = "mumbai"

        cfg = CITIES[city]
        elev = cfg["elevation"]
        drain_dist = cfg["drain"]

        # Live rainfall
        risk_data = FloodAnalyticsTools.get_risk_data(city)
        telemetry = risk_data.get("telemetry", {})
        rain_72h = telemetry.get("rain_72h_mm", 0)

        # Analysis
        gaps = []
        if drain_dist > 400:
            gaps.append(
                f"DRAINAGE GAP — nearest major storm drain is {drain_dist}m from population centers. "
                f"This creates dangerous 'lag time' between peak rainfall and runoff arrival."
            )
        if elev < 30:
            gaps.append(
                f"LOW ELEVATION ({elev}m MSL) — gravity-fed drainage struggles, water pools."
            )
        if rain_72h > 100:
            gaps.append(
                f"CURRENT OVERLOAD — {rain_72h}mm in 72h is straining existing infrastructure."
            )

        # Recommendations
        recommendations = []

        # 1. Decentralized drainage (if drain gap is high)
        if drain_dist > 400:
            recommendations.append({
                "intervention": "Decentralized Drainage Network",
                "what": "Build smaller storm drains every 200-300m within population clusters, "
                        "connecting to the main drainage trunk.",
                "why": "Reduces lag time from 45+ minutes to under 15 minutes. Water clears before "
                       "ground saturation causes ponding.",
                "cost_tier": "MEDIUM",
                "timeline": "12-18 months for retrofitting one ward."
            })

        # 2. Bioswales (always relevant for urban areas)
        recommendations.append({
            "intervention": "Bioswales (vegetated channels)",
            "what": "Install linear, vegetated trenches along roadsides that absorb and filter "
                    "runoff. Typical width: 1-2m. Plants: cana, vetiver, native grasses.",
            "why": "Each km of bioswale handles ~50,000L of runoff per heavy event. Acts as a "
                   "natural sponge between street and storm drain.",
            "cost_tier": "LOW",
            "timeline": "3-6 months per kilometer."
        })

        # 3. Permeable pavement (for high-density)
        recommendations.append({
            "intervention": "Permeable Pavement",
            "what": "Replace conventional asphalt in parking lots, low-traffic streets, and "
                    "pedestrian zones with permeable concrete or porous asphalt.",
            "why": "Standard asphalt is impervious — every drop goes to drains. Permeable "
                   "pavement absorbs 70-80% of light rainfall directly into the soil.",
            "cost_tier": "MEDIUM",
            "timeline": "Phased: 5-10% of urban surface area per year."
        })

        # 4. Sponge city features (for low elevation)
        if elev < 50:
            recommendations.append({
                "intervention": "Sponge City Infrastructure",
                "what": "Rooftop rain gardens (mandatory for new construction), urban wetlands "
                        "in low-lying parks, retention ponds in green belts.",
                "why": "Mumbai's Powai/Mithi watershed and Chennai's Pallikaranai marsh are "
                       "natural sponges. Restoring + expanding them can absorb 30-40% of monsoon "
                       "rainfall before it reaches streets.",
                "cost_tier": "HIGH",
                "timeline": "3-5 year master plan, phased."
            })

        # 5. Sponge city blueprints (always)
        recommendations.append({
            "intervention": "Urban Tree Canopy Expansion",
            "what": "Plant native large-canopy trees (banyan, neem, gulmohar) along major roads "
                    "and in parks. Target: 30% tree cover in dense zones.",
            "why": "Tree canopy intercepts 15-25% of rainfall before it hits the ground. Roots "
                   "improve soil infiltration capacity by 40%.",
            "cost_tier": "LOW",
            "timeline": "Ongoing — 5,000 trees/year per ward is achievable."
        })

        return {
            "status": "SUCCESS",
            "city": city.upper(),
            "area_context": area_description or "general urban zone",
            "current_conditions": {
                "elevation_m": elev,
                "drain_distance_m": drain_dist,
                "recent_rainfall_mm": rain_72h
            },
            "identified_gaps": gaps,
            "recommendations": recommendations,
            "priority_order": (
                "1. Decentralized Drainage (if gap >400m), "
                "2. Bioswales (low-hanging fruit), "
                "3. Permeable Pavement (medium-term), "
                "4. Sponge City features (long-term resilience)."
            )
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


# Top-level exports for Gemini function calling
def get_risk_data(city: str, date: Optional[str] = None):
    return FloodAnalyticsTools.get_risk_data(city, date)


# ============================================================
# UPGRADED SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = f"""You are AquaAlert Dispatcher, an Agentic Urban Resilience & Flood Management Expert
for the AquaAlert flood intelligence platform. You serve both citizens and city planners.

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
TIMEZONE: India Standard Time (IST)
CITIES YOU COVER: Mumbai, Pune, Bengaluru, Chennai

═══════════════════════════════════════════════════════
YOUR FOUR TOOLS — call them, never hallucinate output:
═══════════════════════════════════════════════════════
1. get_risk_data(city, date)
   → Fetches live flood risk score, rainfall, elevation, drain distance.
   → Use this for ANY question about current risk or "is it safe".

2. fetch_flood_news(city, max_results=5)
   → Pulls the latest verified news articles about floods in that city.
   → Use this when the user asks "what's happening", "any news", "recent reports".

3. get_emergency_protocol(city, situation)
   → Returns a prioritized action checklist for the user's current danger.
   → Use this IMMEDIATELY when the user reports water at doorstep, being stuck,
     being in danger, or seeking evacuation steps.
   → Pass their exact wording as `situation`.

4. get_urban_planning_advice(city, area_description)
   → Returns infrastructure recommendations (bioswales, decentralized drainage,
     sponge city features, permeable pavement) based on current city conditions.
   → Use this when the user is a planner, architect, or asks about prevention,
     long-term solutions, or "how can we stop floods".

═══════════════════════════════════════════════════════
CORE PROTOCOLS:
═══════════════════════════════════════════════════════
A. EMERGENCY FIRST: If the user describes water entering their home, being stranded,
   or any immediate physical danger → CALL get_emergency_protocol FIRST, before
   anything else. Lives over information.

B. REASONING CHAIN: When discussing risk, follow this structure:
   "WHY this is happening" (cite telemetry: elevation, rainfall, drainage)
   →
   "WHAT to do NOW" (immediate actions from emergency_protocol)
   →
   "WHAT could prevent this in the future" (urban planning suggestions, if relevant).

C. NEWS INTEGRATION: When users ask about recent flood events, ALWAYS call
   fetch_flood_news for that city. Summarize 3-5 key headlines with source + date.

D. URBAN PLANNING DEPTH: When suggesting interventions, explain:
   - WHAT the intervention is (one sentence)
   - WHY it works for THIS city (cite their elevation/drain data)
   - HOW long and how much (timeline + cost tier)

E. DOMAIN GUARDRAIL: Only answer flood, rainfall, climate, urban resilience,
   and disaster response queries. For unrelated topics: politely redirect.

F. TECHNICAL DEPTH: When users ask about the ML model, explain in plain terms:
   - LSTM analyzes 72-hour rainfall patterns to learn storm buildup
   - XGBoost combines LSTM output with elevation + drainage features
   - ResNet50 reads SAR satellite imagery to detect floods after they occur
   - Final risk score = weighted ensemble with elevation-aware safety override

═══════════════════════════════════════════════════════
TONE & FORMATTING:
═══════════════════════════════════════════════════════
- Clinical and authoritative — you are an expert, not a chatbot.
- URGENT when alert level is HIGH; calm and educational when LOW.
- Use Markdown: ## headers for sections, **bold** for critical warnings,
  bullet lists for action items.
- Prioritize HUMAN LIFE over property in every recommendation.
- Cite specific numbers (rainfall mm, elevation m, drain distance m) — never vague."""


# ============================================================
# CHAT ENDPOINT
# ============================================================
@router.post("/chat")
def agentic_assistant(req: ChatRequest):
    try:
        # Fallback if LLM is offline
        if not IS_LLM_ACTIVE:
            msg = req.message.lower()
            city = req.city or "mumbai"
            for c in CITIES.keys():
                if c in msg:
                    city = c

            target_date = None
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})|(\d{4}-\d{2}-\d{2})', msg)
            if date_match:
                raw_date = date_match.group(0)
                if "/" in raw_date:
                    d, m, y = raw_date.split("/")
                    target_date = f"{y}-{m}-{d}"
                else:
                    target_date = raw_date

            if not any(k in msg for k in ["flood", "rain", "risk", "status", "hi", "hello", "news", "plan", "drain"]):
                return {"reply": "I am AquaAlert AI. (Guardrail Active: Analytical Mode Only)", "is_llm": False}

            # Route to the right offline tool
            if "news" in msg:
                data = fetch_flood_news(city)
                if data["status"] == "SUCCESS":
                    items = "\n".join([f"- {a['title']} ({a['source']})" for a in data["articles"][:3]])
                    reply = f"**AquaAlert News (Offline Mode)**\nLatest flood news in {city.upper()}:\n{items}"
                else:
                    reply = f"News feed unavailable. {data.get('advice', '')}"
                return {"reply": reply, "city": city, "is_llm": False}

            if any(k in msg for k in ["plan", "drain", "bioswale", "sponge", "infrastructure"]):
                data = get_urban_planning_advice(city)
                if data["status"] == "SUCCESS":
                    recs = "\n".join([f"- **{r['intervention']}**: {r['what']}" for r in data["recommendations"][:3]])
                    reply = f"**Urban Planning (Offline Mode)** — {city.upper()}\n{recs}"
                else:
                    reply = "Urban planning module unavailable."
                return {"reply": reply, "city": city, "is_llm": False}

            if any(k in msg for k in ["doorstep", "water", "stuck", "evacuate", "emergency", "help"]):
                data = get_emergency_protocol(city, req.message)
                if data["status"] == "SUCCESS":
                    actions = "\n".join([f"- {a}" for a in data["immediate_actions"][:5]])
                    reply = (
                        f"**EMERGENCY PROTOCOL — {city.upper()}**\n"
                        f"Alert Level: {data['alert_level']} ({data['risk_probability']}%)\n\n"
                        f"**Why:** {data['reasoning']}\n\n"
                        f"**Do NOW:**\n{actions}"
                    )
                else:
                    reply = "Emergency module unavailable."
                return {"reply": reply, "city": city, "is_llm": False}

            # Default — risk data
            data = FloodAnalyticsTools.get_risk_data(city, date=target_date)
            p = data.get("model_output", {})
            reply = (
                f"**AquaAlert AI (Analytical Mode)**\n"
                f"City: {city.upper()} | Risk: {p.get('risk_probability', 0)}% | Status: {p.get('alert_level', 'UNKNOWN')}\n"
                f"Recommendation: {p.get('recommendation', 'N/A')}"
            )
            return {"reply": reply, "city": city, "is_llm": False}

        # --- AGENTIC LLM MODE: All four tools available ---
        model = genai.GenerativeModel(
            model_name=TARGET_MODEL,
            tools=[
                get_risk_data,
                fetch_flood_news,
                get_emergency_protocol,
                get_urban_planning_advice
            ],
            system_instruction=SYSTEM_PROMPT
        )

        gemini_history = []
        for h in req.history:
            # Frontend sends {role, text} — Gemini needs {role, parts: [str]}
            role = "user" if h.get("role") == "user" else "model"
            text = h.get("text", "")
            if text.strip():
                gemini_history.append({"role": role, "parts": [text]})

        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
        response = chat.send_message(req.message)

        # Log tool calls for transparency
        tools_called = []
        for content in chat.history[-4:]:
            for part in content.parts:
                if hasattr(part, 'function_call') and part.function_call.name:
                    tools_called.append(part.function_call.name)
                    print(f">>> [Agent] TOOL CALL: {part.function_call.name}")

        detected_city = req.context_city
        for c in CITIES.keys():
            if c in req.message.lower():
                detected_city = c

        return {
            "reply": response.text,
            "city": detected_city,
            "is_llm": True,
            "tools_used": list(set(tools_called))
        }

    except Exception as e:
        print(f"ERROR [Agent Loop]: {str(e)}")
        return {"reply": f"AI Engine Logic Error: {str(e)}", "error": True, "is_llm": IS_LLM_ACTIVE}
