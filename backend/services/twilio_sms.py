"""
twilio_sms.py — AquaAlert Twilio WhatsApp Escalation Service

Sends a structured WhatsApp alert including:
  - Severity header + flood metrics
  - Areas requiring immediate evacuation (top at-risk areas)
  - Top 3 safe zones with name, address, safety score, phone
  - Emergency contact numbers

Trigger:  flood_probability >= 30%  (same as email)
Called:   alerts.py as a FastAPI BackgroundTask (parallel to email)
Keys:     TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM_NUMBER, WHATSAPP_RECIPIENTS
          All in backend/.env — add your keys there before use.

WhatsApp sender must be:
  - Twilio Sandbox:  whatsapp:+14155238886
  - Approved number: whatsapp:+<your_approved_number>
"""

import os
from datetime import datetime
import datetime as dt
from dotenv import load_dotenv

load_dotenv()

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# ── Credentials ───────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
WHATSAPP_FROM_NUMBER = os.getenv("WHATSAPP_FROM_NUMBER", "")   # e.g. +14155238886
WHATSAPP_RECIPIENTS  = [
    n.strip()
    for n in os.getenv("WHATSAPP_RECIPIENTS", "").split(",")
    if n.strip()
]

_twilio_client = None


def _get_twilio_client():
    """Lazy-load and cache the Twilio REST client."""
    global _twilio_client
    if _twilio_client is not None:
        return _twilio_client

    placeholders = {"your_twilio_account_sid_here", "", "+1XXXXXXXXXX",
                    "your_twilio_auth_token_here"}

    if TWILIO_ACCOUNT_SID in placeholders:
        print("[twilio_wa] TWILIO_ACCOUNT_SID not configured.")
        return None
    if TWILIO_AUTH_TOKEN in placeholders:
        print("[twilio_wa] TWILIO_AUTH_TOKEN not configured.")
        return None
    if WHATSAPP_FROM_NUMBER in placeholders:
        print("[twilio_wa] WHATSAPP_FROM_NUMBER not configured.")
        return None
    if not WHATSAPP_RECIPIENTS:
        print("[twilio_wa] WHATSAPP_RECIPIENTS not configured.")
        return None

    try:
        from twilio.rest import Client
        _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print(f"[twilio_wa] Client ready. From: whatsapp:{WHATSAPP_FROM_NUMBER} | "
              f"Recipients: {len(WHATSAPP_RECIPIENTS)}")
        return _twilio_client
    except ImportError as e:
        print(f"[twilio_wa] twilio import failed: {e}. Run: pip install twilio")
        return None
    except Exception as e:
        print(f"[twilio_wa] Client init failed: {e}")
        return None


# ── Message builder ───────────────────────────────────────────────────────────

def _build_whatsapp_message(city_name: str, flood_data: dict,
                             safe_zones: list, evacuate_areas: list = None) -> str:
    """
    Build a WhatsApp-formatted flood alert message.

    Uses WhatsApp markdown:
      *text*  = bold
      _text_  = italic
      emojis  = visual severity cues

    Structure:
      [1] Header + metrics
      [2] Evacuation areas (top 5)
      [3] Safe zones (top 3)
      [4] Emergency contacts
    """
    prob      = flood_data.get("probability", 0)
    rain_72h  = flood_data.get("total_rain_72h", 0)
    forecast  = flood_data.get("forecast_24h", 0)
    action    = flood_data.get("action", "Monitor conditions")
    timestamp = datetime.now(tz=IST).strftime("%d %b %H:%M IST")

    is_critical = prob >= 70
    level_emoji = "🔴" if is_critical else "🟡"
    level_text  = "CRITICAL" if is_critical else "WARNING"

    # ── Section 1: Header + metrics ───────────────────────────────────────
    sec1 = (
        f"{level_emoji} *[AQUAALERT {level_text}]*\n"
        f"*{city_name.upper()} FLOOD ALERT*\n"
        f"🕐 {timestamp}\n\n"
        f"📊 *Risk:* {prob}%\n"
        f"🌧️ *Rain (72h):* {rain_72h}mm\n"
        f"⛈️ *Forecast (24h):* {forecast}mm\n"
        f"⚡ *Action:* {action[:100]}"
    )

    # ── Section 2: Evacuation areas ───────────────────────────────────────
    sec2 = ""
    if evacuate_areas:
        lines = ["🚨 *EVACUATE IMMEDIATELY:*"]
        for a in evacuate_areas[:5]:
            cat   = a.get("category", "Moderate")
            score = a.get("risk_score", 0)
            emoji = "🔴" if cat == "Critical" else "🟠" if cat == "High" else "🟡"
            lines.append(f"{emoji} {a['name']} — {cat} ({score}%)")
        sec2 = "\n".join(lines)

    # ── Section 3: Safe zones ─────────────────────────────────────────────
    zone_lines = ["🏥 *TOP SAFE ZONES:*"]
    for i, zone in enumerate(safe_zones[:3]):
        rank    = zone.get("recommendation_rank", i + 1)
        name    = zone.get("name", "Unknown")[:35]
        address = zone.get("address", "—")[:40]
        score   = zone.get("safety_score", 0)
        phone   = zone.get("phone", "")
        elev    = zone.get("elevation_m", 0)
        state   = zone.get("risk_state", "SAFE")

        zone_lines.append(f"\n*#{rank} {name}*")
        zone_lines.append(f"📍 {address}")
        zone_lines.append(f"✅ Safety: {score}/100 | Elev: {elev}m | {state}")
        if phone and phone not in ("—", ""):
            zone_lines.append(f"📞 {phone}")

    sec3 = "\n".join(zone_lines)

    # ── Section 4: Emergency contacts ────────────────────────────────────
    sec4 = (
        "🆘 *EMERGENCY CONTACTS:*\n"
        "📞 NDRF: 011-26701700\n"
        "📞 National Emergency: 108\n"
        "📞 Disaster Mgmt: 1078 | Police: 100"
    )

    parts = [sec1]
    if sec2:
        parts.append(sec2)
    parts.append(sec3)
    parts.append(sec4)

    message = "\n\n".join(parts)

    # WhatsApp supports up to 4096 chars
    if len(message) > 4096:
        message = message[:4093] + "..."

    return message


# ── Main dispatch ─────────────────────────────────────────────────────────────

def send_emergency_sms(city_name: str, flood_data: dict,
                        safe_zones: list, evacuate_areas: list = None) -> bool:
    """
    Send the emergency WhatsApp alert to all configured recipients via Twilio.
    Runs as a FastAPI BackgroundTask — does not block the API response.
    Function name kept as send_emergency_sms for backward compatibility with alerts.py.
    """
    client = _get_twilio_client()
    if client is None:
        return False

    message_body = _build_whatsapp_message(
        city_name, flood_data, safe_zones, evacuate_areas or []
    )
    prob  = flood_data.get("probability", 0)
    level = "CRITICAL" if prob >= 70 else "WARNING"

    from_wa = f"whatsapp:{WHATSAPP_FROM_NUMBER}"

    print(f"[twilio_wa] Dispatching {level} WhatsApp alert for {city_name.upper()} "
          f"({prob}%) | {len(message_body)} chars | "
          f"{len(WHATSAPP_RECIPIENTS)} recipients")

    success = 0
    for recipient in WHATSAPP_RECIPIENTS:
        to_wa = f"whatsapp:{recipient}"
        try:
            msg = client.messages.create(
                body  = message_body,
                from_ = from_wa,
                to    = to_wa,
            )
            print(f"[twilio_wa] Sent to {to_wa} | SID: {msg.sid} | Status: {msg.status}")
            success += 1
        except Exception as e:
            print(f"[twilio_wa] Failed for {to_wa}: {e}")

    print(f"[twilio_wa] {success}/{len(WHATSAPP_RECIPIENTS)} WhatsApp alerts sent for "
          f"{city_name.upper()}")
    return success > 0


# ── Status check ──────────────────────────────────────────────────────────────

def get_twilio_status() -> dict:
    placeholders = {"your_twilio_account_sid_here", "", "+1XXXXXXXXXX",
                    "your_twilio_auth_token_here"}
    sid_ok   = TWILIO_ACCOUNT_SID   not in placeholders
    tok_ok   = TWILIO_AUTH_TOKEN    not in placeholders
    from_ok  = WHATSAPP_FROM_NUMBER not in placeholders
    recip_ok = len(WHATSAPP_RECIPIENTS) > 0
    active   = sid_ok and tok_ok and from_ok and recip_ok
    return {
        "whatsapp_service":  "twilio",
        "configured":        active,
        "account_sid_set":   sid_ok,
        "auth_token_set":    tok_ok,
        "from_number":       f"whatsapp:{WHATSAPP_FROM_NUMBER}" if from_ok else "NOT SET",
        "recipient_count":   len(WHATSAPP_RECIPIENTS),
        "status":            "ACTIVE" if active else "INACTIVE — add keys to .env",
    }
