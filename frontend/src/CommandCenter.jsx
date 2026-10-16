import React, { useState, useRef, useCallback, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, useMap, Tooltip, GeoJSON, Marker } from 'react-leaflet';
import L from 'leaflet';
import {
  AlertTriangle, Eye, EyeOff, Activity, RefreshCw,
  Wind, Thermometer, CloudRain, Droplets, Mountain, Navigation
} from 'lucide-react';
import 'leaflet/dist/leaflet.css';

/* ─── Static data ─────────────────────────────────────────────── */
const CITIES = {
  mumbai: { name: 'Mumbai', short: 'MMR', lat: 19.076, lng: 72.8777 },
  bengaluru: { name: 'Bengaluru', short: 'BLR', lat: 12.9716, lng: 77.5946 },
  chennai: { name: 'Chennai', short: 'CHN', lat: 13.0827, lng: 80.2707 },
  pune: { name: 'Pune', short: 'PNQ', lat: 18.5204, lng: 73.8567 },
};

const FLOOD_ZONES = {
  mumbai: [[19.015, 72.855], [19.063, 72.838], [19.18, 72.97]],
  bengaluru: [[12.935, 77.55], [12.998, 77.62], [12.975, 77.49]],
  chennai: [[13.063, 80.25], [13.05, 80.27], [13.12, 80.21]],
  pune: [[18.51, 73.86], [18.56, 73.83], [18.498, 73.87]],
};

const DRAIN_PATHS = [
  [[19.076, 72.8777], [18.8, 73.2], [18.5204, 73.8567]],
  [[13.0827, 80.2707], [13.0, 79.5], [12.9716, 77.5946]],
];

const DEMO = {
  mumbai: { total_72h_rain: 187, total_24h_forecast: 34, elevation_m: 11, drain_distance_m: 520, humidity: 89, wind: 28.5, temp: 27.2 },
  bengaluru: { total_72h_rain: 78, total_24h_forecast: 12, elevation_m: 920, drain_distance_m: 280, humidity: 72, wind: 15.8, temp: 24.6 },
  chennai: { total_72h_rain: 143, total_24h_forecast: 22, elevation_m: 6, drain_distance_m: 410, humidity: 85, wind: 22.3, temp: 29.1 },
  pune: { total_72h_rain: 95, total_24h_forecast: 16, elevation_m: 560, drain_distance_m: 340, humidity: 76, wind: 18.4, temp: 26.3 },
};

const API_BASE = 'http://localhost:8001/api/v1';

// Safe zones now fetched from backend — no duplication

const FLOOD_HISTORY = [
  { year: '2018', events: 3 }, { year: '2019', events: 5 }, { year: '2020', events: 2 },
  { year: '2021', events: 7 }, { year: '2022', events: 4 }, { year: '2023', events: 9 }, { year: '2024', events: 6 },
];

const HOURLY_RISK = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i}:00`,
  risk: i >= 2 && i <= 6 ? 75 : i >= 14 && i <= 18 ? 60 : i >= 22 ? 85 : 30
}));

const URBAN_INSIGHTS = {
  mumbai: ['Dharavi Basin: CRITICAL — drainage blocked', 'Kurla floodplain: encroachment detected', 'Mithi river buffer: 340m violation'],
  bengaluru: ['Bellandur Lake: HIGH — inflow exceeded', 'Whitefield: rapid expansion, drainage lag', 'Varthur Kere: illegal encroachment'],
  chennai: ['Adyar estuary: CRITICAL — storm surge', 'Velachery lake bed: illegal fill detected', 'Pallikaranai marsh: degraded buffer'],
  pune: ['Mula-Mutha riverbed: HIGH risk zone', 'Hadapsar: water accumulation detected', 'Khadakwasla: downstream surge alert'],
};

const FALLBACK_PROB = { mumbai: 72, bengaluru: 38, chennai: 55, pune: 28 };

const riskColor = p => p > 75 ? '#cc4444' : p > 50 ? '#a05018' : p > 25 ? '#7a6a14' : '#2a6a3a';
const riskLabel = p => p > 75 ? 'CRITICAL' : p > 50 ? 'HIGH' : p > 25 ? 'MODERATE' : 'LOW';

const BASEMAPS = {
  street: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  satellite: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  normal: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
};

/* ─── Map helpers ─────────────────────────────────────────────── */
const Recenter = ({ lat, lng }) => {
  const m = useMap();
  React.useEffect(() => {
    // Small delay to ensure DOM is ready after layout shift
    const timer = setTimeout(() => {
      m.invalidateSize();
    }, 100);
    m.flyTo([lat, lng], 12.5, { duration: 1.5 });
    return () => clearTimeout(timer);
  }, [lat, lng, m]);
  return null;
};

const RecenterToArea = ({ lat, lng }) => {
  const m = useMap();
  React.useEffect(() => {
    if (lat && lng) {
      m.flyTo([lat, lng], 14, { duration: 1.2 });
    }
  }, [lat, lng, m]);
  return null;
};

const PulseRing = ({ center, color, radius }) => {
  const [op, setOp] = useState(0.5);
  React.useEffect(() => {
    const iv = setInterval(() => setOp(o => o <= 0.05 ? 0.5 : o - 0.03), 80);
    return () => clearInterval(iv);
  }, []);
  return <Circle center={center} radius={radius}
    pathOptions={{ color, fillColor: color, fillOpacity: op * 0.12, weight: 1.2, opacity: op }} />;
};

/* ─── Panel header — matches screenshot exactly ───────────────── */
const PanelHeader = ({ dot, dotColor = '#cc4444', title, right }) => (
  <div className="cc-panel-header">
    {dot && <span className="cc-panel-dot" style={{ background: dotColor }} />}
    <span className="cc-panel-title">{title}</span>
    {right && <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>{right}</span>}
  </div>
);

/* ─── Main Component ──────────────────────────────────────────── */
export default function CommandCenter({
  liveData, prediction, alertsData, targetCity, setTargetCity,
  loading, time, visionResult, visionPreview, simDate
}) {
  const [layers, setLayers] = useState({ hotspots: true, density: true, drainage: true, wards: true, safe: true });
  const [baseMap, setBaseMap] = useState('street');
  const [sliderPos, setSliderPos] = useState(50);
  const [safeZones, setSafeZones] = useState([]);
  const [areas, setAreas] = useState([]);
  const [wardData, setWardData] = useState(null);
  const [drainageData, setDrainageData] = useState(null);
  const [selectedArea, setSelectedArea] = useState(null);
  const [areaLoading, setAreaLoading] = useState(false);
  const [thresholdInfo, setThresholdInfo] = useState(null);
  const sliderRef = useRef(null);

  // Fetch area data for geospatial intelligence
  useEffect(() => {
    if (!targetCity) return;
    const url = `${API_BASE}/city-areas/${targetCity}?t=${Date.now()}${simDate ? `&sim_date=${simDate}` : ''}`;
    fetch(url)
      .then(r => r.json())
      .then(resp => {
        // New API returns { areas: [...], threshold_info: {...}, summary: {...} }
        const data = resp.areas || resp; // backward compat if plain array

        // Store threshold info for display
        if (resp.threshold_info) setThresholdInfo(resp.threshold_info);

        // Areas are already ranked by risk_score from backend
        // Top 5 by risk_score = hotspots; top 5 by density for density layer
        const sortedDensity = [...data].sort((a, b) => (b.Urban_Density_sqkm || 0) - (a.Urban_Density_sqkm || 0));
        const sortedHotspots = [...data].sort((a, b) => (b.risk_score || b.Water_Logging_Zones || 0) - (a.risk_score || a.Water_Logging_Zones || 0));

        setAreas(data.map(a => ({
          ...a,
          isTopDensity: sortedDensity.slice(0, 5).some(s => s.Area === a.Area),
          densityRank: sortedDensity.slice(0, 5).findIndex(s => s.Area === a.Area),
          isTopHotspot: sortedHotspots.slice(0, 5).some(s => s.Area === a.Area),
          hotspotRank: sortedHotspots.slice(0, 5).findIndex(s => s.Area === a.Area),
        })));
        setSelectedArea(null);
      })
      .catch(err => console.error("Failed to fetch areas:", err));

    // Fetch GeoJSON for wards
    let fileName = targetCity.toUpperCase();
    if (fileName === 'PUNE') fileName = 'PUNE (1)';
    const geoUrl = `${API_BASE}/data/${fileName}.geojson?t=${Date.now()}`;
    fetch(geoUrl)
      .then(r => r.json())
      .then(data => {
        if (data && data.type === 'FeatureCollection') {
          setWardData(data);
        } else {
          setWardData(null);
        }
      })
      .catch(err => {
        console.error("Failed to fetch GeoJSON:", err);
        setWardData(null);
      });

    // Fetch Drainage Data (Unified endpoint for GeoJSON/KML)
    const drainUrl = `${API_BASE}/drainage/${targetCity}?t=${Date.now()}`;
    fetch(drainUrl)
      .then(r => r.json())
      .then(data => {
        if (data && data.type === 'FeatureCollection' && Array.isArray(data.features)) {
          // Filter out malformed features to prevent Leaflet geometryToLayer errors
          const validFeatures = data.features.filter(f => f && f.geometry && f.geometry.type);
          setDrainageData({ ...data, features: validFeatures });
        } else {
          setDrainageData(null);
        }
      })
      .catch(err => {
        console.error("Failed to fetch drainage:", err);
        setDrainageData(null);
      });
  }, [targetCity, simDate]);

  const handleAreaChange = (areaName) => {
    if (!areaName) {
      setSelectedArea(null);
      return;
    }
    setAreaLoading(true);
    const url = `${API_BASE}/predict-area?city=${targetCity}&area_name=${encodeURIComponent(areaName)}&t=${Date.now()}${simDate ? `&sim_date=${simDate}` : ''}`;
    fetch(url)
      .then(r => r.json())
      .then(res => {
        const baseArea = areas.find(a => a.Area === areaName);
        // Update threshold info from fresh response
        if (res.threshold_info) setThresholdInfo(res.threshold_info);
        setSelectedArea({
          ...baseArea,
          calculated_risk: res.prediction.risk_score,
          risk_category: res.prediction.category,
          category_color: res.prediction.category_color,
          explanations: res.prediction.explanations,
          component_scores: res.prediction.component_scores,
          threshold_used_m: res.prediction.threshold_used_m,
          elevation_deficit: res.prediction.elevation_deficit_m,
          weighted_contributions: res.prediction.weighted_contributions,
        });
      })
      .catch(err => console.error("Area prediction failed:", err))
      .finally(() => setAreaLoading(false));
  };

  // Fetch safe zones from shared backend API
  useEffect(() => {
    if (!targetCity) return;
    fetch(`${API_BASE}/safe-zones/${targetCity}`, { signal: AbortSignal.timeout(20000) })
      .then(r => r.json())
      .then(data => {
        const all = [
          ...(data.hospitals || []),
          ...(data.schools || []),
          ...(data.shelters || []),
        ].map(z => ({ lat: z.lat, lng: z.lon, name: z.name, type: z.category, risk_state: z.risk_state }));
        setSafeZones(all);
      })
      .catch(() => {
        // Graceful fallback — keep last known zones or empty
      });
  }, [targetCity]);

  const live = liveData || DEMO[targetCity] || DEMO.mumbai;
  const prob = prediction?.flood_probability ?? prediction?.lstm_flood_probability ?? 0;
  const rc = riskColor(prob);
  const city = CITIES[targetCity] || CITIES.mumbai;
  const insights = URBAN_INSIGHTS[targetCity] || URBAN_INSIGHTS.mumbai;
  const critAlerts = alertsData?.alerts?.filter(
    a => a.risk_level?.includes('CRITICAL') || a.risk_level?.includes('HIGH')
  ) || [];

  const toggleLayer = k => setLayers(l => ({ ...l, [k]: !l[k] }));

  const handleSliderDrag = useCallback(e => {
    if (!sliderRef.current) return;
    const rect = sliderRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width * 100;
    setSliderPos(Math.max(5, Math.min(95, x)));
  }, []);

  const timeStr = time
    ? time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    : '--:--:--';

  const weatherChips = [
    { icon: CloudRain, label: 'RAINFALL/HR', value: (live.total_24h_forecast / 24).toFixed(1), unit: 'mm' },
    { icon: Droplets, label: 'HUMIDITY', value: live.humidity ?? '—', unit: '%' },
    { icon: Wind, label: 'WIND SPEED', value: live.wind ?? '—', unit: 'km/h' },
    { icon: Thermometer, label: 'TEMPERATURE', value: live.temp ?? '—', unit: '°C' },
    { icon: Activity, label: '72H RAINFALL', value: live.total_72h_rain ?? '—', unit: 'mm' },
    { icon: Mountain, label: 'ELEVATION', value: live.elevation_m ?? '—', unit: 'm' },
  ];

  return (
    <div className="cc-root">
      {/* ══ HEADER ══ */}
      <div className="cc-header" style={{
        height: 60, background: '#08090c', borderBottom: '1px solid #1a1c23',
        display: 'flex', alignItems: 'center', padding: '0 24px', gap: 20
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 6, background: 'rgba(56,189,248,0.1)',
            border: '1px solid rgba(56,189,248,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <AlertTriangle size={18} color="#38bdf8" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 900, color: '#fff', letterSpacing: 1 }}>AQUA<span style={{ color: '#38bdf8' }}>ALERT</span></div>
            <div style={{ fontSize: 8, fontWeight: 700, color: '#4a5568', letterSpacing: 1 }}>FLOOD RISK INTELLIGENCE PLATFORM</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginLeft: 40 }}>
          <div className="cc-header-select-wrap" style={{ position: 'relative' }}>
            <select
              style={{
                background: '#0d0f14', border: '1px solid #2d3748', borderRadius: 6,
                padding: '6px 32px 6px 12px', color: '#38bdf8', fontSize: 11, fontWeight: 700,
                appearance: 'none', cursor: 'pointer'
              }}
              value={targetCity}
              onChange={e => setTargetCity(e.target.value)}
            >
              {Object.entries(CITIES).map(([k, v]) => (
                <option key={k} value={k}>{v.name} · {v.short} · {v.lat.toFixed(2)}°N {v.lng.toFixed(2)}°E</option>
              ))}
            </select>
            <Navigation size={10} color="#38bdf8" style={{ position: 'absolute', left: -20, top: '50%', transform: 'translateY(-50%)' }} />
          </div>

          <div style={{
            fontSize: 9, fontWeight: 800, color: '#10b981', background: 'rgba(16,185,129,0.05)',
            border: '1px solid rgba(16,185,129,0.15)', padding: '4px 10px', borderRadius: 4
          }}>
            SDG 11 · 13
          </div>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 30 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 8, fontWeight: 800, color: '#4a5568', letterSpacing: 1 }}>UTC+5:30</div>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#718096', fontFamily: 'JetBrains Mono' }}>{timeStr} <span style={{ fontSize: 10 }}>IST</span></div>
          </div>
          <button className="cc-mini-btn" style={{ padding: '6px 12px', fontSize: 9, background: '#1a1c23' }}>
            <RefreshCw size={10} style={{ marginRight: 6 }} /> REFRESH
          </button>
        </div>
      </div>

      {/* ══ BODY ══ */}
      <div className="cc-body" style={{ height: '100%', display: 'flex', flexDirection: 'row', overflow: 'hidden' }}>

        {/* ════ LEFT COLUMN ════ */}
        <div className="cc-left" style={{ flex: 3, display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* MAP CARD */}
          <div className="cc-panel cc-map-card" style={{ height: 800 }}>
            <PanelHeader
              dot dotColor="#cc4444"
              title={`LIVE SMART CITY MAP · ${city.name.toUpperCase()}`}
              right={
                <>
                  <span className="cc-live-badge">LIVE</span>
                  <span className="cc-zones-label">0 ZONES MONITORED</span>
                </>
              }
            />
            <div style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>

              {/* Layer panel */}
              <div className="cc-layers">
                <div className="cc-layers-title">
                  <span className="cc-layers-plus">+</span> MAP LAYERS
                </div>
                {[
                  { id: 'hotspots', label: 'Flood Hotspots', color: '#cc4444' },
                  { id: 'density', label: 'Urban Density', color: '#9333ea' },
                  { id: 'drainage', label: 'Drainage Network', color: '#0ea5e9' },
                  // { id: 'wards', label: 'Admin Wards', color: '#fff' },
                  { id: 'safe', label: 'Safe Zones', color: '#10b981' },
                ].map(l => (
                  <button key={l.id} className={`cc-layer-btn${layers[l.id] ? ' on' : ''}`} onClick={() => toggleLayer(l.id)}>
                    <span className="cc-layer-sq" style={{ background: layers[l.id] ? l.color : '#1e2230' }} />
                    {layers[l.id]
                      ? <Eye size={8} color={l.color} />
                      : <EyeOff size={8} color="#7a8898" />}
                    <span>{l.label}</span>
                  </button>
                ))}
                <div className="cc-layers-sep" />
                <div className="cc-layers-title">MAP PERSPECTIVE</div>
                <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                  {[
                    { id: 'normal', label: 'Street', color: '#38bdf8' },
                    { id: 'satellite', label: 'Satellite', color: '#10b981' },
                    { id: 'street', label: 'Normal', color: '#f59e0b' }
                  ].map(b => (
                    <button key={b.id}
                      className={`cc-layer-btn ${baseMap === b.id ? 'on' : ''}`}
                      style={{ flex: 1, padding: '4px 0', justifyContent: 'center' }}
                      onClick={() => setBaseMap(b.id)}>
                      {b.label}
                    </button>
                  ))}
                </div>

              </div>

              <MapContainer center={[city.lat, city.lng]} zoom={12}
                style={{ position: 'absolute', inset: 0, height: '100%', width: '100%' }}
                zoomControl={false} attributionControl={false}>
                <TileLayer url={BASEMAPS[baseMap]} />
                <Recenter lat={city.lat} lng={city.lng} />
                {selectedArea && <RecenterToArea lat={selectedArea.Lat} lng={selectedArea.Lon} />}

                {/* Administrative Wards GeoJSON Layer */}
                {layers.wards && wardData && wardData.features && (
                  <GeoJSON
                    key={`${targetCity}-${wardData.features.length}`}
                    data={wardData}
                    style={{
                      color: '#fff',
                      weight: 1.5,
                      fillColor: '#fff',
                      fillOpacity: 0.02
                    }}
                    onEachFeature={(feature, layer) => {
                      const name = feature.properties?.Name || feature.properties?.name || "WARD";
                      layer.bindTooltip(`<div style="font-weight:800; font-size:10px;">${name}</div>`, {
                        sticky: true,
                        direction: 'top'
                      });
                    }}
                  />
                )}

                {/* Detailed Drainage Network Layer */}
                {layers.drainage && drainageData && drainageData.features && (
                  <GeoJSON
                    key={`drainage-${targetCity}-${drainageData.features.length}`}
                    data={drainageData}
                    style={{
                      color: '#0ea5e9',
                      weight: 2.5,
                      opacity: 1,
                      fillColor: '#0ea5e9',
                      fillOpacity: 0.15
                    }}
                    onEachFeature={(feature, layer) => {
                      const label = feature.properties?.Name || feature.properties?.name || "CATCHMENT";
                      layer.bindTooltip(`<div style="color:#0ea5e9; font-weight:800;">💧 ${label}</div>`, { sticky: true });
                    }}
                  />
                )}

                {Object.entries(CITIES)
                  .filter(([key]) => key === targetCity)
                  .map(([key, c]) => {
                    const p = prob;
                    const col = riskColor(p);
                    return (
                      <React.Fragment key={key}>
                        <CircleMarker center={[c.lat, c.lng]} radius={12}
                          pathOptions={{ color: '#fff', fillColor: col, fillOpacity: 1, weight: 2.5 }}>
                          <Tooltip direction="top" offset={[0, -12]}>
                            <div style={{ fontWeight: 800, fontSize: 11, color: '#1a202c' }}>{c.name} (CITY CENTER)</div>
                            <div style={{ fontSize: 10, color: col, fontWeight: 800 }}>{p.toFixed(0)}% — {riskLabel(p)}</div>
                          </Tooltip>
                        </CircleMarker>
                      </React.Fragment>
                    );
                  })}

                {/* Show top 5 high density areas as dots */}
                {layers.density && areas.filter(a => a.isTopDensity).map((a, i) => {
                  const colors = ['#9333ea', '#7c3aed', '#6d28d9', '#5b21b6', '#4c1d95'];
                  const color = colors[a.densityRank] || '#8b5cf6';
                  return (
                    <CircleMarker
                      key={`density-${a.Area}`}
                      center={[a.Lat, a.Lon]}
                      radius={8}
                      pathOptions={{ color: '#fff', fillColor: color, fillOpacity: 1, weight: 2 }}
                      eventHandlers={{ click: () => handleAreaChange(a.Area) }}
                    >
                      <Tooltip direction="bottom" offset={[0, 10]}>
                        <div style={{ fontWeight: 800, color: color }}>RANK #{a.densityRank + 1} DENSITY</div>
                        <div style={{ fontSize: 9, fontWeight: 700 }}>{a.Area}</div>
                        <div style={{ fontSize: 8, color: '#64748b' }}>{a.Urban_Density_sqkm?.toLocaleString()} / km²</div>
                      </Tooltip>
                    </CircleMarker>
                  );
                })}

                {/* Show top 5 flood hotspots as red dots */}
                {layers.hotspots && areas.filter(a => a.isTopHotspot).map((a, i) => (
                  <CircleMarker
                    key={`hotspot-${a.Area}`}
                    center={[a.Lat, a.Lon]}
                    radius={9}
                    pathOptions={{ color: '#fff', fillColor: '#cc4444', fillOpacity: 1, weight: 2.5 }}
                    eventHandlers={{ click: () => handleAreaChange(a.Area) }}
                  >
                    <Tooltip direction="top" offset={[0, -10]}>
                      <div style={{ fontWeight: 900, color: '#cc4444', fontSize: 11 }}>CRITICAL HOTSPOT · RANK #{a.hotspotRank + 1}</div>
                      <div style={{ fontWeight: 800, fontSize: 12, color: '#1a202c', marginBottom: 4 }}>{a.Area}</div>
                      <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ fontSize: 9, color: '#4a5568' }}>• <strong style={{ color: '#cc4444' }}>{a.Water_Logging_Zones}</strong> recorded logging events</div>
                        <div style={{ fontSize: 9, color: '#4a5568' }}>• Elevation: <strong>{a.Elevation_m}m</strong> MSL</div>
                        <div style={{ fontSize: 9, color: '#4a5568' }}>• Drain Dist: <strong>{a.Drain_Distance_m}m</strong></div>
                        {a.Near_River === 1 && <div style={{ fontSize: 9, color: '#2a6a8a', fontWeight: 700 }}>• RIVER BASIN PROXIMITY</div>}
                      </div>
                      <div style={{ marginTop: 6, fontSize: 8, color: '#718096', fontStyle: 'italic' }}>High priority for emergency deployment</div>
                    </Tooltip>
                  </CircleMarker>
                ))}

                {/* Show area on map ONLY when selected - As requested by user */}
                {selectedArea && (
                  <Marker
                    position={[selectedArea.Lat, selectedArea.Lon]}
                    icon={L.divIcon({
                      className: 'cc-custom-marker',
                      html: `
                        <div class="cc-target-wrap">
                          <div class="cc-target-label">
                            📍 ${selectedArea.Area}
                          </div>
                          <div class="cc-target-pulse"></div>
                          <div class="cc-target-pin"></div>
                        </div>
                      `,
                      iconSize: [0, 0],
                      iconAnchor: [0, 0]
                    })}
                  />
                )}

                {layers.safe && safeZones.map((z, i) => {
                  const riskColor = z.risk_state === 'EVACUATE' ? '#cc2222' : z.risk_state === 'AT_RISK' ? '#d97706' : z.risk_state === 'MONITOR' ? '#ca8a04' : '#10b981';
                  return (
                    <CircleMarker key={i} center={[z.lat, z.lng]} radius={7}
                      pathOptions={{ color: riskColor, fillColor: riskColor, fillOpacity: 0.85, weight: 1.5 }}>
                      <Tooltip direction="top" offset={[0, -8]}>
                        <div style={{ fontWeight: 700, fontSize: 10 }}>{z.type === 'hospital' ? '🏥' : z.type === 'school' ? '🏫' : '⛺'} {z.name}</div>
                        <div style={{ fontSize: 9, color: riskColor }}>{(z.risk_state || 'SAFE').replace('_', ' ')} ZONE</div>
                      </Tooltip>
                    </CircleMarker>
                  );
                })}
              </MapContainer>
            </div>
          </div>
        </div>

        {/* ════ RIGHT COLUMN ════ */}
        <div className="cc-right" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>

          {/* CITY GEOSPATIAL INTELLIGENCE - New Card requested by user */}
          <div className="cc-panel cc-right-card">
            <PanelHeader
              title="CITY GEOSPATIAL INTELLIGENCE"
              right={
                areaLoading ? (
                  <span className="cc-live-badge" style={{ background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.3)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <RefreshCw size={8} className="animate-spin" /> PREDICTING...
                  </span>
                ) : (
                  <button className="cc-mini-btn" style={{ background: 'rgba(74, 158, 255, 0.1)', color: '#4a9eff', border: '1px solid rgba(74, 158, 255, 0.2)' }}>
                    DATA HUB
                  </button>
                )
              }
            />
            <div className="cc-geo-body" style={{ padding: '12px 16px' }}>
              <div className="cc-area-selector" style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 9, color: 'var(--muted2)', fontWeight: 700, letterSpacing: 1, marginBottom: 4 }}>SELECT AREA REGION</div>
                <select
                  className="cc-city-select"
                  style={{ width: '100%', background: '#111418', border: '1px solid #262a34', padding: '8px 12px', borderRadius: 6, color: '#fff', fontSize: '13px', outline: 'none' }}
                  value={selectedArea?.Area || ''}
                  onChange={e => handleAreaChange(e.target.value)}
                >
                  <option value="">Select an area...</option>
                  {areas.map(a => (
                    <option key={a.Area} value={a.Area}>{a.Area}</option>
                  ))}
                </select>
              </div>

              {/* ── Threshold Elevation Banner ── */}
              {thresholdInfo && (
                <div style={{ background: 'rgba(56,189,248,0.05)', border: '1px solid rgba(56,189,248,0.2)', borderRadius: 6, padding: '8px 12px', marginBottom: 12 }}>
                  <div style={{ fontSize: 9, color: '#38bdf8', fontWeight: 800, letterSpacing: 1, marginBottom: 4 }}>FLOOD THRESHOLD ELEVATION</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 22, fontWeight: 900, color: '#38bdf8' }}>{thresholdInfo.threshold_elevation_m}m</span>
                    <span style={{ fontSize: 9, color: 'var(--muted2)' }}>MSL · Areas below this elevation are at risk</span>
                  </div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 6 }}>
                    <span style={{ fontSize: 9, color: 'var(--muted2)' }}>Base: <b style={{ color: '#7a8898' }}>{thresholdInfo.base_threshold_m}m</b></span>
                    <span style={{ fontSize: 9, color: 'var(--muted2)' }}>Rain+: <b style={{ color: '#7a8898' }}>{thresholdInfo.rain_modifier_m}m</b></span>
                    <span style={{ fontSize: 9, color: 'var(--muted2)' }}>Flood prob: <b style={{ color: prob > 50 ? '#cc4444' : '#10b981' }}>{thresholdInfo.flood_probability}%</b></span>
                  </div>
                </div>
              )}

              <div className="cc-geo-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12, opacity: areaLoading ? 0.5 : 1, transition: 'opacity 0.2s' }}>
                <div className="cc-geo-metric">
                  <div style={{ fontSize: 9, color: 'var(--muted2)', fontWeight: 700 }}>ELEVATION (MSL)</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: selectedArea?.elevation_deficit > 0 ? '#cc4444' : '#4a9eff' }}>
                    {selectedArea ? selectedArea.Elevation_m : (live.elevation_m || '--')} <span style={{ fontSize: 12 }}>m</span>
                  </div>
                  {selectedArea?.elevation_deficit > 0 && (
                    <div style={{ fontSize: 8, color: '#cc4444', marginTop: 2 }}>↓ {selectedArea.elevation_deficit}m below threshold</div>
                  )}
                </div>
                <div className="cc-geo-metric">
                  <div style={{ fontSize: 9, color: 'var(--muted2)', fontWeight: 700 }}>RISK SCORE</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: selectedArea?.category_color || (selectedArea?.calculated_risk > 70 ? '#cc4444' : selectedArea?.calculated_risk > 40 ? '#d97706' : '#10b981') }}>
                    {selectedArea ? `${selectedArea.calculated_risk}%` : '---'}
                  </div>
                  {selectedArea?.risk_category && (
                    <div style={{ fontSize: 8, color: selectedArea.category_color, marginTop: 2, fontWeight: 700 }}>{selectedArea.risk_category.toUpperCase()}</div>
                  )}
                </div>
                <div className="cc-geo-metric">
                  <div style={{ fontSize: 9, color: 'var(--muted2)', fontWeight: 700 }}>DRAIN DISTANCE</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#10b981' }}>
                    {selectedArea ? selectedArea.Drain_Distance_m : (live.drain_distance_m || '--')} <span style={{ fontSize: 12 }}>m</span>
                  </div>
                </div>
                <div className="cc-geo-metric">
                  <div style={{ fontSize: 9, color: 'var(--muted2)', fontWeight: 700 }}>WATERLOG EVENTS</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#cc4444' }}>
                    {selectedArea ? selectedArea.Water_Logging_Zones : '—'} <span style={{ fontSize: 12 }}>zones</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── AREA RISK RANKING ── */}
          <div className="cc-panel cc-right-card">
            <PanelHeader
              dot dotColor="#cc4444"
              title="AREA FLOOD RISK RANKING"
              right={
                <span style={{
                  fontSize: 9, fontWeight: 800, color: '#cc4444',
                  background: 'rgba(204,68,68,0.1)', border: '1px solid rgba(204,68,68,0.25)',
                  padding: '2px 8px', borderRadius: 4
                }}>
                  {areas.filter(a => (a.risk_score || 0) > 0).length} ACTIVE
                </span>
              }
            />
            <div style={{ padding: '0 0 4px 0' }}>
              {/* Column headers */}
              <div style={{
                display: 'grid', gridTemplateColumns: '22px 1fr 48px 36px',
                gap: 6, padding: '4px 14px 6px',
                borderBottom: '1px solid rgba(255,255,255,0.04)'
              }}>
                {['#', 'AREA', 'SCORE', 'CAT'].map(h => (
                  <span key={h} style={{ fontSize: 8, fontWeight: 800, color: 'var(--muted2)', letterSpacing: 1 }}>{h}</span>
                ))}
              </div>

              {/* Scrollable list */}
              <div style={{
                maxHeight: 320,
                overflowY: 'auto',
                overflowX: 'hidden',
                scrollbarWidth: 'thin',
                scrollbarColor: '#2a2d38 transparent',
              }}>
                {areas.length === 0 ? (
                  <div style={{ padding: '20px 14px', textAlign: 'center', fontSize: 10, color: 'var(--muted2)' }}>
                    {loading ? 'Loading areas...' : 'No data — select a city'}
                  </div>
                ) : (
                  // Show all areas sorted by risk_score desc (already sorted from backend)
                  // Filter out zero-score areas when flood prob is 0
                  [...areas]
                    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
                    .map((area, idx) => {
                      const score = area.risk_score || 0;
                      const cat = area.category || area.risk_category || 'Low';
                      const color = cat === 'Critical' ? '#cc2222'
                        : cat === 'High' ? '#d97706'
                          : cat === 'Moderate' ? '#ca8a04'
                            : '#16a34a';
                      const isSelected = selectedArea?.Area === area.Area;

                      return (
                        <div
                          key={area.Area}
                          onClick={() => handleAreaChange(area.Area)}
                          style={{
                            display: 'grid',
                            gridTemplateColumns: '22px 1fr 48px 36px',
                            gap: 6,
                            padding: '7px 14px',
                            cursor: 'pointer',
                            borderBottom: '1px solid rgba(255,255,255,0.03)',
                            background: isSelected
                              ? 'rgba(74,158,255,0.08)'
                              : idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                            borderLeft: isSelected ? '2px solid #4a9eff' : '2px solid transparent',
                            transition: 'background 0.15s',
                          }}
                        >
                          {/* Rank */}
                          <span style={{
                            fontSize: 9, fontWeight: 800,
                            color: idx < 3 ? color : 'var(--muted2)',
                            alignSelf: 'center'
                          }}>
                            {idx + 1}
                          </span>

                          {/* Area name + score bar */}
                          <div style={{ minWidth: 0 }}>
                            <div style={{
                              fontSize: 10, fontWeight: 700, color: '#e2e8f0',
                              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                              marginBottom: 3
                            }}>
                              {area.Area}
                            </div>
                            {/* Score bar */}
                            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                              <div style={{
                                height: '100%',
                                width: `${score}%`,
                                background: `linear-gradient(90deg, ${color}80, ${color})`,
                                borderRadius: 2,
                                transition: 'width 0.4s ease'
                              }} />
                            </div>
                            {/* Sub-stats */}
                            <div style={{ display: 'flex', gap: 8, marginTop: 3 }}>
                              <span style={{ fontSize: 8, color: 'var(--muted2)' }}>
                                {area.Elevation_m}m MSL
                              </span>
                              {area.elevation_deficit_m > 0 && (
                                <span style={{ fontSize: 8, color: '#cc4444', fontWeight: 700 }}>
                                  -{area.elevation_deficit_m}m
                                </span>
                              )}
                              {area.Water_Logging_Zones > 0 && (
                                <span style={{ fontSize: 8, color: '#7a8898' }}>
                                  {area.Water_Logging_Zones} wlog
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Score value */}
                          <span style={{
                            fontSize: 11, fontWeight: 900, color,
                            alignSelf: 'center', textAlign: 'right',
                            fontFamily: 'JetBrains Mono, monospace'
                          }}>
                            {score.toFixed(1)}%
                          </span>

                          {/* Category badge */}
                          <span style={{
                            fontSize: 7, fontWeight: 800,
                            color, background: `${color}18`,
                            border: `1px solid ${color}40`,
                            borderRadius: 3, padding: '2px 4px',
                            alignSelf: 'center', textAlign: 'center',
                            letterSpacing: 0.5,
                            whiteSpace: 'nowrap'
                          }}>
                            {cat.toUpperCase().slice(0, 4)}
                          </span>
                        </div>
                      );
                    })
                )}
              </div>

              {/* Footer summary */}
              {areas.length > 0 && (
                <div style={{
                  display: 'flex', gap: 12, padding: '8px 14px',
                  borderTop: '1px solid rgba(255,255,255,0.05)',
                  background: 'rgba(0,0,0,0.2)'
                }}>
                  {[
                    { label: 'CRIT', color: '#cc2222', count: areas.filter(a => a.category === 'Critical').length },
                    { label: 'HIGH', color: '#d97706', count: areas.filter(a => a.category === 'High').length },
                    { label: 'MOD', color: '#ca8a04', count: areas.filter(a => a.category === 'Moderate').length },
                    { label: 'LOW', color: '#16a34a', count: areas.filter(a => a.category === 'Low' || !a.category).length },
                  ].map(s => (
                    <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: s.color, flexShrink: 0 }} />
                      <span style={{ fontSize: 8, color: 'var(--muted2)', fontWeight: 700 }}>{s.label}</span>
                      <span style={{ fontSize: 9, fontWeight: 900, color: s.color }}>{s.count}</span>
                    </div>
                  ))}
                  <span style={{ marginLeft: 'auto', fontSize: 8, color: 'var(--muted2)' }}>
                    {areas.length} total areas
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* WEATHER · RISK */}
          <div className="cc-panel cc-right-card">
            <PanelHeader
              title="WEATHER · RISK"
              right={
                <span className="cc-risk-level-badge" style={{ color: rc, borderColor: `${rc}50`, background: `${rc}15` }}>
                  {loading ? 'LOADING...' : riskLabel(prob)}
                </span>
              }
            />
            {loading
              ? <div className="cc-loading-text">Loading...</div>
              : <>
                <div className="cc-weather-grid">
                  {weatherChips.map(w => (
                    <div key={w.label} className="cc-weather-chip">
                      <w.icon size={10} color="#7a8898" />
                      <span className="cc-wc-val">{w.value}<span className="cc-wc-unit">{w.unit}</span></span>
                      <span className="cc-wc-label">{w.label}</span>
                    </div>
                  ))}
                </div>
              </>
            }
          </div>
        </div>
      </div>
    </div>
  );
}
