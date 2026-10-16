import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import datetime as dt

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# ── Category color map ────────────────────────────────────────────────────────
_CAT_COLOR = {
    "Critical": "#dc2626",
    "High":     "#d97706",
    "Moderate": "#ca8a04",
    "Low":      "#16a34a",
}
_RISK_STATE_COLOR = {
    "SAFE":     "#16a34a",
    "MONITOR":  "#ca8a04",
    "AT_RISK":  "#d97706",
    "EVACUATE": "#dc2626",
}


def generate_emergency_html(city_name: str, flood_data: dict,
                             safe_zones: list, evacuate_areas: list = None) -> str:
    """
    Generates a professional government-grade emergency operations bulletin.

    Sections:
      1. Header + severity banner
      2. Flood intelligence summary (4 stat cards)
      3. Emergency operational guidance (AI text)
      4. AREAS REQUIRING IMMEDIATE EVACUATION (new — from flood risk engine)
      5. Top 3 Safe Zones with full details (name, address, elevation,
         safety score, capacity, phone, risk state)
      6. SAR satellite verification
      7. Footer with authorities
    """
    prob         = flood_data.get("probability", 0)
    rain_72h     = flood_data.get("total_rain_72h", 0)
    forecast     = flood_data.get("forecast_24h", 0)
    trend        = flood_data.get("trend", "STABLE")
    risk_level   = flood_data.get("risk_level", "AWAITING")
    sar          = flood_data.get("sar_validation", "Pending Sync")
    timestamp    = datetime.now(tz=IST).strftime("%d %b %Y | %H:%M:%S IST")
    ref_no       = f"AA-EWS-{datetime.now().strftime('%Y%m%d%H%M')}"

    is_critical  = prob >= 70
    banner_color = "#dc2626" if is_critical else "#f59e0b"
    severity_txt = "CRITICAL — IMMEDIATE ACTION REQUIRED" if is_critical else "WARNING — ELEVATED FLOOD RISK"

    # ── AI guidance text ──────────────────────────────────────────────────
    if is_critical:
        guidance = (
            f"<strong>CRITICAL ALERT:</strong> Flood probability has reached <strong>{prob}%</strong> "
            f"in {city_name.title()}. Rainfall accumulation of <strong>{rain_72h}mm over 72 hours</strong> "
            f"has saturated drainage infrastructure. An additional <strong>{forecast}mm is forecast in the next 24 hours</strong>. "
            f"NDRF and local emergency units must be mobilised immediately. "
            f"All residents in low-lying and waterlogging-prone areas must evacuate to designated safe zones NOW."
        )
    else:
        guidance = (
            f"<strong>WARNING:</strong> Flood probability is at <strong>{prob}%</strong> "
            f"in {city_name.title()}. Rainfall accumulation of <strong>{rain_72h}mm over 72 hours</strong> "
            f"is placing stress on drainage systems. A further <strong>{forecast}mm is forecast in the next 24 hours</strong>. "
            f"Municipal disaster teams should pre-position resources and monitor drainage choke points. "
            f"Residents in flood-prone wards should prepare for potential evacuation."
        )

    # ── Evacuation areas section ──────────────────────────────────────────
    evac_html = ""
    if evacuate_areas:
        rows = ""
        for i, area in enumerate(evacuate_areas[:8]):
            cat   = area.get("category", "Moderate")
            col   = _CAT_COLOR.get(cat, "#ca8a04")
            score = area.get("risk_score", 0)
            elev  = area.get("elevation_m", 0)
            wlog  = area.get("waterlog", 0)
            bg    = "#fff5f5" if cat == "Critical" else "#fffbeb" if cat in ("High", "Moderate") else "#f0fdf4"
            rows += f"""
            <tr style="background:{bg}; border-bottom:1px solid #e2e8f0;">
              <td style="padding:10px 14px; font-weight:700; color:#1e293b; font-size:13px;">
                {'&#9888;' if cat in ('Critical','High') else '&#9679;'} {area['name']}
              </td>
              <td style="padding:10px 14px; text-align:center;">
                <span style="background:{col}20; color:{col}; font-weight:800;
                  font-size:11px; padding:3px 10px; border-radius:12px;
                  border:1px solid {col}40;">{cat.upper()}</span>
              </td>
              <td style="padding:10px 14px; text-align:center; font-weight:700;
                color:{col}; font-size:13px;">{score}%</td>
              <td style="padding:10px 14px; text-align:center; color:#64748b; font-size:12px;">{elev}m MSL</td>
              <td style="padding:10px 14px; text-align:center; color:#64748b; font-size:12px;">{wlog} events</td>
            </tr>"""

        evac_html = f"""
        <div style="margin-bottom:28px;">
          <div style="font-size:13px; font-weight:800; color:#64748b; text-transform:uppercase;
            letter-spacing:1px; margin-bottom:12px; padding-bottom:6px;
            border-bottom:2px solid #dc2626;">
            &#9888; Areas Requiring Immediate Evacuation
          </div>
          <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:8px;
            padding:12px 14px; margin-bottom:12px; font-size:13px; color:#991b1b;">
            <strong>URGENT:</strong> The following areas have been identified by the AquaAlert
            AI engine as high-risk zones based on elevation, drainage capacity, waterlogging
            history, and current flood probability. Residents must evacuate immediately.
          </div>
          <table style="width:100%; border-collapse:collapse; border-radius:8px;
            overflow:hidden; border:1px solid #e2e8f0;">
            <thead>
              <tr style="background:#1e293b; color:white;">
                <th style="padding:10px 14px; text-align:left; font-size:11px;
                  font-weight:700; letter-spacing:0.5px;">AREA NAME</th>
                <th style="padding:10px 14px; text-align:center; font-size:11px;
                  font-weight:700; letter-spacing:0.5px;">RISK LEVEL</th>
                <th style="padding:10px 14px; text-align:center; font-size:11px;
                  font-weight:700; letter-spacing:0.5px;">RISK SCORE</th>
                <th style="padding:10px 14px; text-align:center; font-size:11px;
                  font-weight:700; letter-spacing:0.5px;">ELEVATION</th>
                <th style="padding:10px 14px; text-align:center; font-size:11px;
                  font-weight:700; letter-spacing:0.5px;">WATERLOG HISTORY</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # ── Top 3 safe zones section ──────────────────────────────────────────
    zones_html = ""
    for zone in safe_zones[:3]:
        rank       = zone.get("recommendation_rank", 1)
        name       = zone.get("name", "Unknown")
        address    = zone.get("address", "—")
        category   = zone.get("category", "shelter").title()
        risk_state = zone.get("risk_state", "SAFE")
        rs_color   = _RISK_STATE_COLOR.get(risk_state, "#16a34a")
        safety     = zone.get("safety_score", 0)
        elevation  = zone.get("elevation_m", 0)
        capacity   = zone.get("capacity")
        phone      = zone.get("phone", "—")
        dist_km    = zone.get("min_flood_dist_km", "—")
        confidence = zone.get("confidence", f"{safety}%")

        cat_emoji  = "🏥" if "hospital" in category.lower() else "🏫" if "school" in category.lower() else "⛺"

        # Safety score bar (inline SVG-style using div)
        bar_width  = min(int(safety), 100)
        bar_color  = "#16a34a" if safety >= 70 else "#ca8a04" if safety >= 40 else "#dc2626"

        capacity_row = ""
        if capacity:
            capacity_row = f"""
            <tr>
              <td style="padding:4px 0; color:#94a3b8; font-size:12px; width:130px;">Capacity</td>
              <td style="padding:4px 0; color:#1e293b; font-size:12px; font-weight:600;">
                {capacity:,} persons
              </td>
            </tr>"""

        phone_row = ""
        if phone and phone != "—":
            phone_row = f"""
            <tr>
              <td style="padding:4px 0; color:#94a3b8; font-size:12px;">Contact</td>
              <td style="padding:4px 0; color:#0369a1; font-size:12px; font-weight:600;">
                {phone}
              </td>
            </tr>"""

        zones_html += f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
          margin-bottom:14px; overflow:hidden;">
          <!-- Zone header -->
          <div style="background:#1e293b; padding:12px 16px;
            display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="background:rgba(56,189,248,0.2); color:#38bdf8;
                font-weight:900; font-size:16px; width:28px; height:28px;
                border-radius:50%; display:inline-flex; align-items:center;
                justify-content:center;">#{rank}</span>
              <div>
                <div style="color:white; font-weight:800; font-size:15px;">
                  {cat_emoji} {name}
                </div>
                <div style="color:#94a3b8; font-size:12px; margin-top:2px;">
                  {category} &nbsp;|&nbsp; {address}
                </div>
              </div>
            </div>
            <span style="background:{rs_color}25; color:{rs_color};
              border:1px solid {rs_color}60; font-weight:800; font-size:11px;
              padding:4px 12px; border-radius:20px; letter-spacing:0.5px;">
              {risk_state}
            </span>
          </div>
          <!-- Zone body -->
          <div style="padding:14px 16px;">
            <!-- AI Safety Score bar -->
            <div style="margin-bottom:12px;">
              <div style="display:flex; justify-content:space-between;
                margin-bottom:5px;">
                <span style="font-size:11px; font-weight:700; color:#64748b;
                  text-transform:uppercase; letter-spacing:0.5px;">
                  AI Safety Score
                </span>
                <span style="font-size:13px; font-weight:900; color:{bar_color};">
                  {safety}/100 &nbsp;({confidence} confidence)
                </span>
              </div>
              <div style="background:#e2e8f0; border-radius:4px; height:8px; overflow:hidden;">
                <div style="background:linear-gradient(90deg,{bar_color}99,{bar_color});
                  width:{bar_width}%; height:100%; border-radius:4px;"></div>
              </div>
            </div>
            <!-- Details table -->
            <table style="width:100%; border-collapse:collapse;">
              <tr>
                <td style="padding:4px 0; color:#94a3b8; font-size:12px; width:130px;">Elevation</td>
                <td style="padding:4px 0; color:#1e293b; font-size:12px; font-weight:600;">
                  {elevation}m MSL
                </td>
                <td style="padding:4px 0; color:#94a3b8; font-size:12px; width:130px;">Flood Zone Dist.</td>
                <td style="padding:4px 0; color:#1e293b; font-size:12px; font-weight:600;">
                  {dist_km} km away
                </td>
              </tr>
              {capacity_row}
              {phone_row}
            </table>
          </div>
        </div>"""

    # ── Full HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AquaAlert Emergency Bulletin — {city_name.upper()}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
  font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;color:#334155;">

<div style="max-width:660px;margin:24px auto;border-radius:10px;
  overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">

  <!-- ── HEADER ── -->
  <div style="background:#0f172a;padding:24px 30px;text-align:center;">
    <div style="font-size:26px;font-weight:900;letter-spacing:-1px;color:white;">
      AQUA<span style="color:#38bdf8;">ALERT</span>
    </div>
    <div style="font-size:11px;color:#64748b;margin-top:4px;letter-spacing:2px;
      text-transform:uppercase;">
      Urban Flood Emergency Intelligence Platform
    </div>
  </div>

  <!-- ── SEVERITY BANNER ── -->
  <div style="background:{banner_color};padding:14px 30px;text-align:center;">
    <div style="color:white;font-weight:900;font-size:17px;letter-spacing:1px;">
      {severity_txt}
    </div>
    <div style="color:rgba(255,255,255,0.85);font-size:12px;margin-top:4px;">
      {timestamp} &nbsp;|&nbsp; Ref: {ref_no}
    </div>
  </div>

  <!-- ── CONTENT ── -->
  <div style="background:white;padding:28px 30px;">

    <!-- City + risk level -->
    <div style="display:flex;justify-content:space-between;
      align-items:flex-start;margin-bottom:24px;padding-bottom:20px;
      border-bottom:1px solid #f1f5f9;">
      <div>
        <div style="font-size:30px;font-weight:900;color:#0f172a;
          letter-spacing:-1px;">{city_name.upper()}</div>
        <div style="font-size:13px;color:#64748b;margin-top:3px;">
          Disaster Management Operations Bulletin
        </div>
      </div>
      <div style="text-align:right;">
        <div style="background:{banner_color}15;border:1px solid {banner_color}40;
          border-radius:6px;padding:8px 14px;">
          <div style="font-size:11px;color:#64748b;font-weight:700;
            text-transform:uppercase;letter-spacing:0.5px;">AI Risk Level</div>
          <div style="font-size:14px;font-weight:900;color:{banner_color};
            margin-top:2px;">{risk_level}</div>
        </div>
      </div>
    </div>

    <!-- ── FLOOD INTELLIGENCE SUMMARY ── -->
    <div style="font-size:13px;font-weight:800;color:#64748b;text-transform:uppercase;
      letter-spacing:1px;margin-bottom:14px;padding-bottom:6px;
      border-bottom:1px solid #f1f5f9;">
      Flood Intelligence Summary
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;
      gap:12px;margin-bottom:26px;">
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
        padding:14px;text-align:center;">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;
          text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
          Flood Probability
        </div>
        <div style="font-size:26px;font-weight:900;color:{banner_color};">{prob}%</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
        padding:14px;text-align:center;">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;
          text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
          72h Rainfall
        </div>
        <div style="font-size:26px;font-weight:900;color:#1e293b;">{rain_72h}mm</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
        padding:14px;text-align:center;">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;
          text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
          24h Forecast
        </div>
        <div style="font-size:26px;font-weight:900;color:#1e293b;">{forecast}mm</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
        padding:14px;text-align:center;">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;
          text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
          Trend
        </div>
        <div style="font-size:16px;font-weight:900;color:#1e293b;margin-top:4px;">
          {trend}
        </div>
      </div>
    </div>

    <!-- ── EMERGENCY GUIDANCE ── -->
    <div style="font-size:13px;font-weight:800;color:#64748b;text-transform:uppercase;
      letter-spacing:1px;margin-bottom:14px;padding-bottom:6px;
      border-bottom:1px solid #f1f5f9;">
      Emergency Operational Guidance
    </div>
    <div style="background:#fff7ed;border:1px solid #fed7aa;border-left:4px solid {banner_color};
      border-radius:8px;padding:16px 18px;margin-bottom:26px;
      font-size:13px;line-height:1.7;color:#7c2d12;">
      {guidance}
    </div>

    <!-- ── EVACUATION AREAS ── -->
    {evac_html}

    <!-- ── TOP 3 SAFE ZONES ── -->
    <div style="font-size:13px;font-weight:800;color:#64748b;text-transform:uppercase;
      letter-spacing:1px;margin-bottom:14px;padding-bottom:6px;
      border-bottom:2px solid #16a34a;">
      &#10003; Top 3 Recommended Safe Zones — Evacuation Ready
    </div>
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
      padding:12px 14px;margin-bottom:16px;font-size:13px;color:#166534;">
      The following locations have been ranked by the AquaAlert AI Safety Scoring engine
      based on elevation advantage, distance from flood zones, current flood probability,
      and 72-hour rainfall accumulation. Proceed to the highest-ranked available shelter.
    </div>
    {zones_html}

    <!-- ── SAR VERIFICATION ── -->
    <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;
      padding:14px 16px;margin-bottom:20px;font-size:13px;">
      <span style="font-weight:800;color:#0369a1;">SAR Satellite Verification:</span>
      <span style="color:#334155;margin-left:6px;">{sar}</span>
    </div>

    <!-- ── EMERGENCY CONTACTS ── -->
    <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
      padding:14px 16px;font-size:13px;">
      <div style="font-weight:800;color:#991b1b;margin-bottom:8px;">
        Emergency Contacts
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;color:#7f1d1d;">
        <div>&#128222; NDRF Helpline: <strong>011-26701700</strong></div>
        <div>&#128222; National Emergency: <strong>108</strong></div>
        <div>&#128222; Disaster Mgmt: <strong>1078</strong></div>
        <div>&#128222; Police Control: <strong>100</strong></div>
      </div>
    </div>

  </div><!-- end content -->

  <!-- ── FOOTER ── -->
  <div style="background:#f8fafc;padding:20px 30px;text-align:center;
    border-top:1px solid #e2e8f0;">
    <div style="font-weight:700;color:#475569;font-size:12px;margin-bottom:6px;">
      AUTHORITIES NOTIFIED: Municipal Commissioner &nbsp;|&nbsp;
      NDRF Base &nbsp;|&nbsp; Regional EOC
    </div>
    <div style="color:#94a3b8;font-size:11px;line-height:1.6;">
      This is an automated emergency intelligence dispatch from the AquaAlert System.<br>
      Powered by LSTM + XGBoost Fusion Pipeline &nbsp;|&nbsp; Sen1Floods11 SAR Vision
    </div>
    <div style="color:#cbd5e1;font-size:10px;margin-top:8px;">
      &copy; 2026 AquaAlert Operations Intelligence Engine &nbsp;|&nbsp;
      National Disaster Response Framework
    </div>
  </div>

</div>
</body>
</html>"""
    return html


def send_emergency_email(city_name: str, flood_data: dict,
                          safe_zones: list, evacuate_areas: list = None) -> bool:
    """
    Dispatch the emergency HTML email via Gmail SMTP SSL.
    Runs as a FastAPI BackgroundTask — does not block the API response.
    """
    sender_email   = os.getenv("SMTP_EMAIL", "")
    sender_password = os.getenv("SMTP_PASSWORD", "")
    recipients_raw  = os.getenv("ALERT_RECIPIENTS", "")
    recipient_list  = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not sender_password:
        print("[escalation] SMTP_PASSWORD not set. Skipping email dispatch.")
        return False
    if not recipient_list:
        print("[escalation] ALERT_RECIPIENTS not set. Skipping email dispatch.")
        return False

    prob  = flood_data.get("probability", 0)
    level = "CRITICAL" if prob >= 70 else "WARNING"
    subject = (
        f"[AQUAALERT {level}] EMERGENCY FLOOD ESCALATION: "
        f"{city_name.upper()} — {prob}% RISK | "
        f"{datetime.now(tz=IST).strftime('%d %b %Y %H:%M IST')}"
    )

    try:
        html_content = generate_emergency_html(
            city_name, flood_data, safe_zones, evacuate_areas or []
        )
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"AquaAlert Emergency Operations <{sender_email}>"
        msg["To"]      = ", ".join(recipient_list)
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"[escalation] Email dispatched for {city_name.upper()} "
              f"({prob}%) to {len(recipient_list)} recipients")
        return True
    except Exception as e:
        print(f"[escalation] Email failed for {city_name}: {e}")
        return False
