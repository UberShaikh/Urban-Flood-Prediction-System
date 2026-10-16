import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, Polyline, useMap, Tooltip } from 'react-leaflet';
import {
  ShieldAlert, CloudRain, Droplets, Mountain, Activity, Radio,
  TrendingUp, AlertTriangle, CheckCircle, Layers, Eye, EyeOff,
  Satellite, Map as MapIcon, X, Navigation
} from 'lucide-react';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';

const API = 'http://localhost:8001/api/v1';

const CITIES = {
  mumbai: { name: 'Mumbai', lat: 19.076, lng: 72.8777, desc: 'Coastal metropolitan, high flood risk zone', population: '20.7M', area: 603 },
  bengaluru: { name: 'Bengaluru', lat: 12.9716, lng: 77.5946, desc: 'Urban plateau, moderate drainage capacity', population: '13.2M', area: 741 },
  chennai: { name: 'Chennai', lat: 13.0827, lng: 80.2707, desc: 'Coastal floodplain, cyclone-prone region', population: '10.9M', area: 426 },
  pune: { name: 'Pune', lat: 18.5204, lng: 73.8567, desc: 'Western Ghats foothills, river basin zone', population: '7.4M', area: 516 },
};

const DRAINAGE_PATHS = [
  [[19.076, 72.8777], [18.8, 73.2], [18.5204, 73.8567]],
  [[13.0827, 80.2707], [13.0, 79.5], [12.9716, 77.5946]],
];

const FLOOD_ZONES = {
  mumbai: [[19.015, 72.855], [19.063, 72.838], [19.18, 72.97]],
  bengaluru: [[12.935, 77.55], [12.998, 77.62], [12.975, 77.49]],
  chennai: [[13.063, 80.25], [13.05, 80.27], [13.12, 80.21]],
  pune: [[18.51, 73.86], [18.56, 73.83], [18.498, 73.87]],
};

const MAP_TILES = {
  dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
};

const riskColor = p => p > 75 ? '#ef4444' : p > 50 ? '#f97316' : p > 25 ? '#f59e0b' : '#10b981';
const riskLabel = p => p > 75 ? 'CRITICAL' : p > 50 ? 'HIGH RISK' : p > 25 ? 'MODERATE' : 'LOW RISK';

const PulseRing = ({ center, color, radius }) => {
  const [opacity, setOpacity] = useState(0.5);
  useEffect(() => {
    const iv = setInterval(() => setOpacity(o => o <= 0.05 ? 0.5 : o - 0.025), 80);
    return () => clearInterval(iv);
  }, []);
  return <Circle center={center} radius={radius} pathOptions={{ color, fillColor: color, fillOpacity: opacity * 0.2, weight: 1.5, opacity }} />;
};

const MapRecenter = ({ lat, lng }) => {
  const map = useMap();
  useEffect(() => { map.flyTo([lat, lng], 7, { duration: 1.5 }); }, [lat, lng, map]);
  return null;
};

export default function FloodMap({ targetCity, setTargetCity, commandMode = false }) {
  const [cityData, setCityData] = useState(() =>
    Object.fromEntries(Object.entries(CITIES).map(([k, v]) => [k, { ...v, live: null, prediction: null, prob: 0, loading: true }]))
  );
  const [loading, setLoading] = useState(true);
  const [activeLayers, setActiveLayers] = useState({ flood: true, urban: true, rainfall: true, drainage: true });
  const [mapStyle, setMapStyle] = useState('dark');
  const [selectedCity, setSelectedCity] = useState(null);

  const fetchAllCities = useCallback(async () => {
    setLoading(true);
    const results = await Promise.all(
      Object.entries(CITIES).map(async ([key, info]) => {
        try {
          const liveRes = await axios.get(`${API}/live/${key}`);
          const predRes = await axios.post(`${API}/predict`, {
            rainfall_72h: liveRes.data.rainfall_72h,
            forecast_24h: liveRes.data.total_24h_forecast,
            elevation_m: liveRes.data.elevation_m,
            drain_distance_m: liveRes.data.drain_distance_m,
          });
          return [key, { ...info, live: liveRes.data, prediction: predRes.data, prob: predRes.data.flood_probability ?? predRes.data.lstm_flood_probability ?? 0, loading: false }];
        } catch {
          return [key, { ...info, live: null, prediction: null, prob: 0, error: true, loading: false }];
        }
      })
    );
    setCityData(Object.fromEntries(results));
    setLoading(false);
  }, []);

  useEffect(() => { fetchAllCities(); }, [fetchAllCities]);

  const center = CITIES[targetCity] || CITIES.mumbai;
  const selected = selectedCity ? cityData[selectedCity] : null;
  const toggleLayer = l => setActiveLayers(prev => ({ ...prev, [l]: !prev[l] }));

  const mapH = commandMode ? 'calc(100vh - 72px - 52px)' : '480px';

  return (
    <div className={`flood-map-container${commandMode ? ' command-mode' : ''}`}
      style={commandMode ? { height: 'calc(100vh - 72px - 52px)', display: 'flex', flexDirection: 'column' } : {}}>

      {/* Non-command mode: hero header */}
      {!commandMode && (
        <div className="hero-banner hero-map animate-in">
          <div className="hero-content" style={{ flexDirection: 'row', alignItems: 'center' }}>
            <div className="hero-left">
              <div className="hero-greeting"><Activity size={20} /><span>Interactive Command Map</span></div>
              <div className="hero-city">Geospatial Risk Intelligence</div>
              <div className="hero-meta">
                <span>4 monitored regions</span><span className="hero-dot">•</span>
                <span>Multi-layer overlays</span><span className="hero-dot">•</span>
                <span>OpenStreetMap + AI data</span>
              </div>
            </div>
            <button className="infer-btn" onClick={fetchAllCities} disabled={loading}
              style={{ background: 'rgba(255,255,255,0.2)', border: '1px solid rgba(255,255,255,0.3)', color: '#fff', boxShadow: 'none', marginLeft: 'auto' }}>
              {loading ? <span className="spinner" /> : <Radio size={14} />} Refresh Data
            </button>
          </div>
        </div>
      )}

      <div className="map-layout" style={commandMode ? { flex: 1, height: '100%', overflow: 'hidden' } : {}}>
        {/* Main Map */}
        <div className="map-wrapper" style={{ borderRadius: commandMode ? 0 : 12, height: commandMode ? '100%' : undefined }}>
          {loading && (
            <div className="map-loading">
              <div className="scan-bar" style={{ width: 200 }}><div className="scan-fill" /></div>
              <span>Loading regional intelligence...</span>
            </div>
          )}

          <MapContainer center={[center.lat, center.lng]} zoom={6}
            style={{ height: commandMode ? '100%' : '480px', width: '100%', borderRadius: commandMode ? 0 : 12 }}
            zoomControl={false} attributionControl={false}>

            <TileLayer url={MAP_TILES[mapStyle]} attribution="© OpenStreetMap" />
            <MapRecenter lat={center.lat} lng={center.lng} />

            {/* Drainage network */}
            {activeLayers.drainage && DRAINAGE_PATHS.map((path, i) => (
              <Polyline key={i} positions={path}
                pathOptions={{ color: '#38bdf8', weight: 2, opacity: 0.45, dashArray: '8 6' }} />
            ))}

            {Object.entries(cityData).map(([key, city]) => {
              const prob = city.prob || 0;
              const color = riskColor(prob);
              const isActive = key === targetCity;
              return (
                <React.Fragment key={key}>
                  {/* Flood risk zone */}
                  {activeLayers.flood && (
                    <Circle center={[city.lat, city.lng]}
                      radius={prob > 60 ? 38000 : prob > 30 ? 26000 : 16000}
                      pathOptions={{ color, fillColor: color, fillOpacity: 0.13, weight: isActive ? 2.5 : 1.5, dashArray: isActive ? null : '6 4' }} />
                  )}

                  {/* Urban expansion overlay */}
                  {activeLayers.urban && (
                    <Circle center={[city.lat, city.lng]}
                      radius={(city.area || 500) * 45}
                      pathOptions={{ color: '#a78bfa', fillColor: '#a78bfa', fillOpacity: 0.05, weight: 1, dashArray: '4 8' }} />
                  )}

                  {/* Rainfall intensity */}
                  {activeLayers.rainfall && city.live && (
                    <Circle center={[city.lat, city.lng]}
                      radius={Math.max(8000, (city.live.total_72h_rain / 300) * 42000)}
                      pathOptions={{ color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: 0.07, weight: 0.8, dashArray: '2 6' }} />
                  )}

                  {/* Water accumulation sub-zones */}
                  {activeLayers.flood && FLOOD_ZONES[key]?.map((pos, i) => (
                    <Circle key={i} center={pos} radius={3500}
                      pathOptions={{ color, fillColor: color, fillOpacity: 0.28, weight: 0.5 }} />
                  ))}

                  {/* Pulse ring for elevated risk */}
                  {prob > 25 && <PulseRing center={[city.lat, city.lng]} color={color} radius={prob > 60 ? 58000 : 42000} />}

                  {/* City marker */}
                  <CircleMarker center={[city.lat, city.lng]} radius={isActive ? 13 : 9}
                    pathOptions={{ color: '#fff', fillColor: color, fillOpacity: 1, weight: isActive ? 3 : 2 }}
                    eventHandlers={{ click: () => { setTargetCity(key); setSelectedCity(key); } }}>
                    <Tooltip direction="top" offset={[0, -12]} permanent={isActive}>
                      <div style={{ fontWeight: 700, fontSize: 12 }}>{city.name}</div>
                      <div style={{ fontSize: 11, color, fontWeight: 800 }}>{riskLabel(prob)}</div>
                      <div style={{ fontSize: 10, opacity: 0.7 }}>{prob.toFixed(0)}% risk</div>
                    </Tooltip>
                  </CircleMarker>
                </React.Fragment>
              );
            })}
          </MapContainer>

          {/* Floating Layer Controls */}
          <div className="map-layer-controls">
            <div className="mlc-title"><Layers size={11} /> Map Layers</div>
            {[
              { id: 'flood', label: 'Flood Risk', color: '#ef4444' },
              { id: 'urban', label: 'Urban Expansion', color: '#a78bfa' },
              { id: 'rainfall', label: 'Rainfall Zones', color: '#38bdf8' },
              { id: 'drainage', label: 'Drainage Network', color: '#38bdf8' },
            ].map(l => (
              <button key={l.id} className={`mlc-btn${activeLayers[l.id] ? ' active' : ''}`}
                style={{ '--lc': l.color }} onClick={() => toggleLayer(l.id)}>
                <span className="mlc-dot" style={{ background: activeLayers[l.id] ? l.color : 'var(--muted)' }} />
                {l.label}
                {activeLayers[l.id] ? <Eye size={10} /> : <EyeOff size={10} />}
              </button>
            ))}
            <div className="mlc-sep" />
            <div className="mlc-title"><MapIcon size={11} /> Base Map</div>
            {[['dark', 'Dark'], ['light', 'Light'], ['satellite', 'Satellite']].map(([id, label]) => (
              <button key={id} className={`mlc-btn${mapStyle === id ? ' active-map' : ''}`} onClick={() => setMapStyle(id)}>
                <Satellite size={10} /> {label}
              </button>
            ))}
            <div className="mlc-sep" />
            <button className="mlc-btn" onClick={fetchAllCities} disabled={loading}>
              {loading ? <span className="spinner-sm" /> : <Radio size={10} />} Refresh
            </button>
          </div>

          {/* Floating Legend */}
          <div className="map-float-legend">
            <div className="mfl-title">Risk Legend</div>
            {[
              { label: 'Critical (>75%)', color: '#ef4444' },
              { label: 'High (50–75%)', color: '#f97316' },
              { label: 'Moderate (25–50%)', color: '#f59e0b' },
              { label: 'Low (<25%)', color: '#10b981' },
            ].map(l => (
              <div key={l.label} className="mfl-item">
                <span className="mfl-dot" style={{ background: l.color, boxShadow: `0 0 6px ${l.color}60` }} />
                {l.label}
              </div>
            ))}
            <div className="mfl-sep" />
            <div className="mfl-item"><span className="mfl-line" />Drainage Network</div>
            <div className="mfl-item"><span className="mfl-dot" style={{ background: '#a78bfa', opacity: 0.7 }} />Urban Boundary</div>
            <div className="mfl-item"><span className="mfl-dot" style={{ background: '#38bdf8', opacity: 0.7 }} />Rainfall Zone</div>
          </div>

          {/* City Info Flyout */}
          {selectedCity && selected && (
            <div className="map-city-panel animate-in">
              <div className="mcp-header" style={{ borderLeftColor: riskColor(selected.prob || 0) }}>
                <div>
                  <div className="mcp-city">{selected.name}</div>
                  <div className="mcp-pop">{selected.population} population · {selected.area} km²</div>
                </div>
                <div className="mcp-badge" style={{ color: riskColor(selected.prob || 0), background: `${riskColor(selected.prob || 0)}18`, border: `1px solid ${riskColor(selected.prob || 0)}40` }}>
                  {riskLabel(selected.prob || 0)}
                </div>
                <button className="mcp-close" onClick={() => setSelectedCity(null)}><X size={14} /></button>
              </div>
              <div className="mcp-prob-row">
                <div className="mcp-prob-bar-bg">
                  <div className="mcp-prob-bar-fill" style={{ width: `${selected.prob || 0}%`, background: riskColor(selected.prob || 0) }} />
                </div>
                <span className="mcp-prob-val" style={{ color: riskColor(selected.prob || 0) }}>{(selected.prob || 0).toFixed(1)}%</span>
              </div>
              {selected.live ? (
                <div className="mcp-stats">
                  <div className="mcp-stat"><CloudRain size={12} /><span>{selected.live.total_72h_rain} mm / 72h</span></div>
                  <div className="mcp-stat"><TrendingUp size={12} /><span>{selected.live.total_24h_forecast} mm forecast</span></div>
                  <div className="mcp-stat"><Mountain size={12} /><span>{selected.live.elevation_m} m elevation</span></div>
                  <div className="mcp-stat"><Droplets size={12} /><span>{selected.live.drain_distance_m} m to drain</span></div>
                </div>
              ) : (
                <div className="mcp-offline">⚠ Live feed unavailable — API offline</div>
              )}
              {selected.prediction?.recommended_action && (
                <div className="mcp-action" style={{ borderColor: `${riskColor(selected.prob || 0)}40` }}>
                  <AlertTriangle size={11} color={riskColor(selected.prob || 0)} />
                  <span>{selected.prediction.recommended_action}</span>
                </div>
              )}
              <div className="mcp-desc">{selected.desc}</div>
            </div>
          )}
        </div>

        {/* Side panel (non-command mode) */}
        {!commandMode && (
          <div className="map-side-panel">
            <div className="msp-title">Regional Overview</div>
            {Object.entries(cityData).map(([key, city]) => {
              const prob = city.prob || 0;
              const color = riskColor(prob);
              const isActive = key === targetCity;
              return (
                <div key={key} className={`msp-card${isActive ? ' active' : ''}`}
                  onClick={() => { setTargetCity(key); setSelectedCity(key); }}
                  style={{ '--accent': color }}>
                  <div className="msp-card-header">
                    <div className="msp-dot" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
                    <span className="msp-city-name">{city.name}</span>
                    <span className="msp-risk-badge" style={{ color, background: `${color}15`, borderColor: `${color}30` }}>
                      {riskLabel(prob)}
                    </span>
                  </div>
                  <div className="msp-prob-row">
                    <div className="msp-prob-bar-bg">
                      <div className="msp-prob-bar-fill" style={{ width: `${prob}%`, background: color }} />
                    </div>
                    <span className="msp-prob-value" style={{ color }}>{prob.toFixed(1)}%</span>
                  </div>
                  {city.live && (
                    <div className="msp-stats">
                      <div className="msp-stat"><CloudRain size={11} /><span>{city.live.total_72h_rain}mm</span></div>
                      <div className="msp-stat"><TrendingUp size={11} /><span>{city.live.total_24h_forecast}mm</span></div>
                      <div className="msp-stat"><Mountain size={11} /><span>{city.live.elevation_m}m</span></div>
                    </div>
                  )}
                  {city.error && <div className="msp-desc" style={{ color: 'var(--amber)' }}>Live feed unavailable.</div>}
                  <div className="msp-desc">{city.desc}</div>
                </div>
              );
            })}
            <div className="map-legend">
              <div className="map-legend-title">Risk Legend</div>
              {[['#ef4444', 'Critical (>75%)'], ['#f97316', 'High (50–75%)'], ['#f59e0b', 'Moderate (25–50%)'], ['#10b981', 'Low (<25%)']].map(([c, l]) => (
                <div key={l} className="map-legend-item"><div className="ml-dot" style={{ background: c }} />{l}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
