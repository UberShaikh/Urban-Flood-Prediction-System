import { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  MapPin, RefreshCw, Users, Phone, Navigation, Search,
  Shield, Brain, AlertTriangle, TrendingUp, Mountain, Activity
} from 'lucide-react';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';

const API = 'http://localhost:8001/api/v1';

const CITY_COORDS = {
  mumbai: { lat: 19.076, lng: 72.8777, name: 'Mumbai' },
  bengaluru: { lat: 12.9716, lng: 77.5946, name: 'Bengaluru' },
  chennai: { lat: 13.0827, lng: 80.2707, name: 'Chennai' },
  pune: { lat: 18.5204, lng: 73.8567, name: 'Pune' },
};

const CAT = {
  hospital: { color: '#059669', fill: '#10b981', label: 'Hospital', emoji: '🏥' },
  school: { color: '#1d4ed8', fill: '#3b82f6', label: 'School', emoji: '🏫' },
  shelter: { color: '#b45309', fill: '#f59e0b', label: 'Shelter', emoji: '⛺' },
};

const RISK_META = {
  SAFE: { color: '#16a34a', bg: 'rgba(22,163,74,0.12)', border: 'rgba(22,163,74,0.35)', label: 'SAFE', icon: '✓' },
  MONITOR: { color: '#ca8a04', bg: 'rgba(202,138,4,0.12)', border: 'rgba(202,138,4,0.35)', label: 'MONITOR', icon: '◎' },
  AT_RISK: { color: '#d97706', bg: 'rgba(217,119,6,0.12)', border: 'rgba(217,119,6,0.35)', label: 'AT RISK', icon: '⚠' },
  EVACUATE: { color: '#cc2222', bg: 'rgba(204,34,34,0.12)', border: 'rgba(204,34,34,0.35)', label: 'EVACUATE', icon: '🚨' },
};

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371, dLat = (lat2 - lat1) * Math.PI / 180, dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return (R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))).toFixed(1);
}

function MapRecenter({ lat, lng }) {
  const map = useMap();
  useEffect(() => { map.flyTo([lat, lng], 12, { duration: 1 }); }, [lat, lng, map]);
  return null;
}

function RiskMarker({ zone, isSelected, onClick }) {
  const c = CAT[zone.category] || CAT.hospital;
  const rm = RISK_META[zone.risk_state] || RISK_META.SAFE;
  // Color: SAFE uses category color, others use risk color
  const col = zone.risk_state === 'SAFE' ? c.fill : rm.color;
  const size = isSelected ? 18 : zone.recommendation_rank === 1 ? 15 : 12;

  const icon = L.divIcon({
    className: '',
    html: `
      <div style="
        display:flex; flex-direction:column; align-items:center;
        cursor:pointer;
      ">
        <!-- Dot with emoji -->
        <div style="
          width:${size * 2}px; height:${size * 2}px;
          border-radius:50%;
          background:${col};
          border:${isSelected ? '3px' : '2px'} solid #fff;
          box-shadow:0 0 ${isSelected ? 12 : 6}px ${col}88;
          display:flex; align-items:center; justify-content:center;
          font-size:${size - 2}px; line-height:1;
        ">${c.emoji}</div>
        <!-- Name label -->
        <div style="
          margin-top:3px;
          background:rgba(8,9,12,0.85);
          border:1px solid ${col};
          border-radius:4px;
          padding:2px 5px;
          font-size:9px;
          font-weight:800;
          color:${col};
          white-space:nowrap;
          max-width:110px;
          overflow:hidden;
          text-overflow:ellipsis;
          font-family:'Segoe UI',sans-serif;
          letter-spacing:0.2px;
          pointer-events:none;
        ">${zone.name}</div>
      </div>
    `,
    iconSize: [120, 46],
    iconAnchor: [60, size],   // anchor at centre of dot
    popupAnchor: [0, -(size + 4)],
  });

  return (
    <Marker
      position={[zone.lat, zone.lon]}
      icon={icon}
      eventHandlers={{ click: onClick }}
      zIndexOffset={isSelected ? 1000 : zone.recommendation_rank === 1 ? 500 : 0}
    >
      <Tooltip direction="top" offset={[0, -(size + 6)]} opacity={1}>
        <div style={{ minWidth: 160, fontFamily: 'Segoe UI, sans-serif' }}>
          <div style={{ fontWeight: 800, fontSize: 12, color: '#fff', marginBottom: 3 }}>{zone.name}</div>
          <div style={{ display: 'flex', gap: 5, marginBottom: 3, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 9, fontWeight: 700, color: c.fill,
              background: `${c.fill}20`, border: `1px solid ${c.fill}40`,
              borderRadius: 3, padding: '1px 5px'
            }}>{c.emoji} {c.label.toUpperCase()}</span>
            <span style={{
              fontSize: 9, fontWeight: 700, color: rm.color,
              background: rm.bg, border: `1px solid ${rm.color}40`,
              borderRadius: 3, padding: '1px 5px'
            }}>{rm.icon} {rm.label}</span>
          </div>
          {zone.elevation_m && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2 }}>
              <b style={{ color: '#38bdf8' }}>Elevation:</b> {zone.elevation_m}m MSL
            </div>
          )}
          {zone.safety_score !== undefined && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2 }}>
              <b style={{ color: '#10b981' }}>AI Safety Score:</b> {zone.safety_score}/100
            </div>
          )}
          {zone.min_flood_dist_km !== undefined && (
            <div style={{ fontSize: 10, color: '#94a3b8' }}>
              <b style={{ color: '#f59e0b' }}>Flood zone:</b> {zone.min_flood_dist_km} km away
            </div>
          )}
          {zone.risk_desc && (
            <div style={{
              marginTop: 5, fontSize: 9, color: rm.color,
              background: rm.bg, borderRadius: 3, padding: '2px 5px',
              border: `1px solid ${rm.color}30`
            }}>
              {rm.icon} {zone.risk_desc}
            </div>
          )}
        </div>
      </Tooltip>
    </Marker>
  );
}

export default function SafeZonesTab({ targetCity, setTargetCity, simDate }) {
  const [zones, setZones] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState(null);
  const [showRecs, setShowRecs] = useState(true);

  const city = targetCity || 'mumbai';
  const coords = CITY_COORDS[city] || CITY_COORDS.mumbai;

  const fetchZones = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await axios.get(`${API}/safe-zones/${city}`, {
        params: simDate ? { sim_date: simDate } : {},
        timeout: 90000   // 90s — batch elevation fetch can take ~15s for many zones
      });
      setZones(r.data);
    } catch (e) {
      console.error('[SafeZones] fetch failed:', e.message);
      setError('Backend offline — showing curated fallback data');
      setZones(FALLBACK[city] || FALLBACK.mumbai);
    }
    setLoading(false);
  }, [city, simDate]);

  useEffect(() => { fetchZones(); }, [fetchZones]);

  const allZones = zones ? [
    ...(zones.hospitals || []),
    ...(zones.schools || []),
    ...(zones.shelters || []),
  ] : [];

  const filtered = allZones
    .filter(z => filter === 'all' || z.category === filter)
    .filter(z => riskFilter === 'all' || z.risk_state === riskFilter)
    .filter(z => !search || z.name.toLowerCase().includes(search.toLowerCase()));

  const meta = zones?.meta || {};
  const floodProb = zones?.flood_probability ?? 0;
  const recs = zones?.top_recommendations || [];

  const riskBand = floodProb >= 70 ? 'CRITICAL' : floodProb >= 45 ? 'HIGH' : floodProb >= 20 ? 'MODERATE' : 'LOW';
  const riskBandColor = floodProb >= 70 ? '#cc2222' : floodProb >= 45 ? '#d97706' : floodProb >= 20 ? '#ca8a04' : '#16a34a';

  return (
    <div className="sz-page animate-in">

      {/* ── Header Intelligence Bar ── */}
      <div className="sz-intel-bar">
        <div className="sz-intel-city">
          <Navigation size={11} color="#506a88" />
          <select className="sz-city-select" value={city} onChange={e => setTargetCity(e.target.value)}>
            {Object.entries(CITY_COORDS).map(([k, v]) => (
              <option key={k} value={k}>{v.name} REGION</option>
            ))}
          </select>
        </div>

        <div className="sz-intel-flood">
          <Activity size={11} color={riskBandColor} />
          <span className="sz-intel-label">FLOOD RISK</span>
          <span className="sz-intel-val" style={{ color: riskBandColor }}>{floodProb.toFixed(1)}%</span>
          <span className="sz-intel-band" style={{ color: riskBandColor, borderColor: `${riskBandColor}40`, background: `${riskBandColor}15` }}>
            {riskBand}
          </span>
        </div>

        <div className="sz-intel-stats">
          {[
            { label: 'SAFE', count: meta.safe_count || 0, color: '#16a34a' },
            { label: 'MONITOR', count: meta.monitor_count || 0, color: '#ca8a04' },
            { label: 'AT RISK', count: meta.at_risk_count || 0, color: '#d97706' },
            { label: 'EVACUATE', count: meta.evacuate_count || 0, color: '#cc2222' },
          ].map(s => (
            <div key={s.label} className="sz-intel-stat" style={{ '--sc': s.color }}>
              <span className="sz-is-num" style={{ color: s.color }}>{s.count}</span>
              <span className="sz-is-lbl">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="sz-intel-actions">
          {error && <span className="sz-error-badge">⚠ {error}</span>}
          <button className="sz-refresh" onClick={fetchZones} disabled={loading}>
            <RefreshCw size={13} className={loading ? 'spin-slow' : ''} />
            <span>{loading ? 'SYNCING...' : 'REFRESH'}</span>
          </button>
        </div>
      </div>

      {/* ── AI Recommendation Cards ── */}
      {recs.length > 0 && showRecs && (
        <div className="sz-recs-strip">
          <div className="sz-recs-header">
            <Brain size={11} color="#818cf8" />
            <span>AI EVACUATION RECOMMENDATIONS</span>
            <span className="sz-recs-sub">Ranked by composite safety score</span>
            <button className="sz-recs-close" onClick={() => setShowRecs(false)}>✕</button>
          </div>
          <div className="sz-recs-cards">
            {recs.map((z, i) => {
              const c = CAT[z.category] || CAT.shelter;
              const rm = RISK_META[z.risk_state] || RISK_META.SAFE;
              return (
                <div key={z.id || i} className="sz-rec-card" style={{ '--rc': c.fill }}
                  onClick={() => setSelected(selected?.id === z.id ? null : z)}>
                  <div className="sz-rec-rank">#{i + 1}</div>
                  <div className="sz-rec-body">
                    <div className="sz-rec-name">{z.name}</div>
                    <div className="sz-rec-meta">
                      <span style={{ color: c.fill }}>{c.emoji} {c.label}</span>
                      {z.elevation_m && <span className="sz-rec-elev">↑ {z.elevation_m}m</span>}
                      <span className="sz-rec-dist">{haversine(coords.lat, coords.lng, z.lat, z.lon)} km</span>
                    </div>
                  </div>
                  <div className="sz-rec-score">
                    <div className="sz-score-ring" style={{ '--sp': z.safety_score || 0, '--sc': rm.color }}>
                      <span style={{ color: rm.color }}>{z.safety_score}</span>
                    </div>
                    <span className="sz-rec-conf">{z.confidence || `${z.safety_score}%`}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Main Layout ── */}
      <div className="sz-main">

        {/* Map Panel */}
        <div className="sz-map-panel">
          <div className="sz-map-header">
            <span className="sz-panel-title"><MapPin size={11} /> EVACUATION ZONE MAP</span>
            <span className="sz-panel-sub">{coords.name} · {filtered.length} locations visible</span>
          </div>
          <div className="sz-map-body">
            <MapContainer center={[coords.lat, coords.lng]} zoom={12}
              style={{ width: '100%', height: '100%' }}
              zoomControl={false} attributionControl={false}>
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
              <MapRecenter lat={coords.lat} lng={coords.lng} />
              {filtered.map((z, i) => (
                <RiskMarker key={z.id || i} zone={z}
                  isSelected={selected?.id === z.id}
                  onClick={() => setSelected(selected?.id === z.id ? null : z)} />
              ))}
            </MapContainer>

            {/* Map Legend */}
            <div className="sz-map-legend">
              <div className="sz-legend-title">RISK STATES</div>
              {Object.entries(RISK_META).map(([k, v]) => (
                <div key={k} className="sz-legend-row">
                  <span className="sz-legend-dot" style={{ background: v.color }} />
                  <span>{v.label}</span>
                </div>
              ))}
              <div className="sz-legend-sep" />
              <div className="sz-legend-title">CATEGORY</div>
              {Object.entries(CAT).map(([k, c]) => (
                <div key={k} className="sz-legend-row">
                  <span className="sz-legend-dot" style={{ background: c.fill }} />
                  <span>{c.label}</span>
                </div>
              ))}
            </div>

            {/* Flood Probability Overlay */}
            {floodProb > 0 && (
              <div className="sz-map-flood-badge" style={{ borderColor: riskBandColor, color: riskBandColor }}>
                <AlertTriangle size={10} />
                <span>FLOOD {floodProb.toFixed(0)}%</span>
              </div>
            )}
          </div>
        </div>

        {/* List Panel */}
        <div className="sz-list-panel">
          <div className="sz-list-header">
            <span className="sz-panel-title"><Shield size={11} /> SHELTER DIRECTORY</span>
            <div className="sz-search-wrap">
              <Search size={10} />
              <input className="sz-search" value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search shelters..." />
            </div>
          </div>

          {/* Category Filter Pills */}
          <div className="sz-filter-row">
            {['all', 'hospital', 'school', 'shelter'].map(f => (
              <button key={f}
                className={`sz-pill${filter === f ? ' active' : ''}`}
                style={filter === f && f !== 'all' ? { background: `${CAT[f]?.fill}20`, borderColor: CAT[f]?.fill, color: CAT[f]?.fill } : {}}
                onClick={() => setFilter(f)}>
                {f === 'all' ? '⊕ All' : `${CAT[f].emoji} ${CAT[f].label}s`}
                <span className="sz-pill-n">
                  {f === 'all' ? allZones.length : allZones.filter(z => z.category === f).length}
                </span>
              </button>
            ))}
          </div>

          {/* Risk Filter Pills */}
          <div className="sz-filter-row sz-risk-pills">
            <span className="sz-filter-label">RISK:</span>
            {['all', 'SAFE', 'MONITOR', 'AT_RISK', 'EVACUATE'].map(rs => {
              const rm = rs !== 'all' ? RISK_META[rs] : null;
              return (
                <button key={rs}
                  className={`sz-pill sz-rpill${riskFilter === rs ? ' active' : ''}`}
                  style={riskFilter === rs && rs !== 'all' ? { borderColor: rm.color, color: rm.color, background: rm.bg } : {}}
                  onClick={() => setRiskFilter(rs)}>
                  {rs === 'all' ? 'All States' : `${rm.icon} ${rm.label}`}
                  <span className="sz-pill-n">
                    {rs === 'all' ? allZones.length : allZones.filter(z => z.risk_state === rs).length}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Zone List */}
          <div className="sz-zone-list">
            {loading && !zones && (
              <div className="sz-loading-state">
                <div className="scan-bar"><div className="scan-fill" /></div>
                <span>FETCHING SAFE ZONES...</span>
              </div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="sz-empty-state">
                <MapPin size={28} />
                <span>No zones found</span>
                <small>{search ? `No results for "${search}"` : 'Try changing filters or city'}</small>
              </div>
            )}

            {filtered.map((z, i) => {
              const c = CAT[z.category] || CAT.hospital;
              const rm = RISK_META[z.risk_state] || RISK_META.SAFE;
              const dist = haversine(coords.lat, coords.lng, z.lat, z.lon);
              const isSelected = selected?.id === z.id;
              const occupancyPct = z.capacity ? Math.min(Math.round(
                floodProb * 0.6 +
                (z.elevation_m ? Math.max(0, 20 - z.elevation_m * 0.02) : 5) +
                (z.min_flood_dist_km ? Math.max(0, 10 - z.min_flood_dist_km * 2) : 5)
              ), 95) : null;

              return (
                <div key={z.id || i}
                  className={`sz-zone-card${isSelected ? ' selected' : ''}${z.recommendation_rank === 1 ? ' top-rec' : ''}`}
                  style={{ '--card-accent': c.fill, '--risk-color': rm.color }}
                  onClick={() => setSelected(isSelected ? null : z)}>

                  {z.risk_state === 'EVACUATE' && <div className="sz-evacuate-glow" />}
                  {z.recommendation_rank === 1 && <div className="sz-rec-crown">★ TOP RECOMMENDATION</div>}

                  <div className="sz-zone-top">
                    <div className="sz-zone-info">
                      <span className="sz-zone-name">{z.name}</span>
                      <div className="sz-zone-badges">
                        <span className="sz-zone-type" style={{ color: c.fill }}>{c.emoji} {c.label.toUpperCase()}</span>
                        <span className="sz-risk-badge" style={{ color: rm.color, background: rm.bg, borderColor: rm.border }}>
                          {rm.icon} {rm.label}
                        </span>
                      </div>
                    </div>
                    <div className="sz-zone-right">
                      <div className="sz-zone-dist">
                        <span style={{ color: c.fill }}>{dist}</span>
                        <small>km</small>
                      </div>
                      {z.elevation_m && (
                        <div className="sz-elev-badge">
                          <Mountain size={8} />
                          <span>{z.elevation_m}m</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {z.safety_score !== undefined && (
                    <div className="sz-score-bar-wrap">
                      <div className="sz-score-bar-track">
                        <div className="sz-score-bar-fill"
                          style={{ width: `${z.safety_score}%`, background: `linear-gradient(90deg, ${rm.color}, ${c.fill})` }} />
                      </div>
                      <span className="sz-score-label" style={{ color: rm.color }}>AI {z.safety_score}</span>
                    </div>
                  )}

                  {z.capacity && occupancyPct !== null && (
                    <div className="sz-occupancy-wrap">
                      <div className="sz-occ-label">
                        <Users size={8} />
                        <span>Est. Occupancy</span>
                        <span style={{ color: occupancyPct > 80 ? '#cc2222' : '#ca8a04' }}>{occupancyPct}%</span>
                      </div>
                      <div className="sz-occ-track">
                        <div className="sz-occ-fill" style={{
                          width: `${occupancyPct}%`,
                          background: occupancyPct > 80 ? '#cc2222' : occupancyPct > 60 ? '#d97706' : '#16a34a'
                        }} />
                      </div>
                    </div>
                  )}

                  {isSelected && (
                    <div className="sz-zone-detail">
                      {z.address && z.address !== '—' &&
                        <div className="sz-detail-item"><MapPin size={10} /><span>{z.address}</span></div>}
                      {z.capacity &&
                        <div className="sz-detail-item"><Users size={10} /><span>Capacity: {z.capacity.toLocaleString()} persons</span></div>}
                      {z.phone && z.phone !== '—' &&
                        <div className="sz-detail-item"><Phone size={10} /><span>{z.phone}</span></div>}
                      <div className="sz-detail-item">
                        <Navigation size={10} />
                        <span>{z.lat?.toFixed(4)}°N {z.lon?.toFixed(4)}°E</span>
                      </div>
                      {z.min_flood_dist_km !== undefined &&
                        <div className="sz-detail-item"><AlertTriangle size={10} /><span>Flood zone: {z.min_flood_dist_km} km away</span></div>}
                      {z.risk_desc &&
                        <div className="sz-detail-risk" style={{ color: rm.color, borderColor: `${rm.color}30`, background: rm.bg }}>
                          {rm.icon} {z.risk_desc}
                        </div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {meta.timestamp && (
            <div className="sz-list-footer">
              <TrendingUp size={9} /> Last updated: {meta.timestamp} · {meta.total_zones || 0} zones indexed
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Fallback when backend is fully offline ── */
const FALLBACK = {
  mumbai: {
    flood_probability: 0,
    rainfall_72h: 0,
    hospitals: [
      { id: 1001, name: 'KEM Hospital', lat: 19.0012, lon: 72.8416, category: 'hospital', capacity: 1800, phone: '022-2410-7000', address: 'Parel', risk_state: 'SAFE', safety_score: 82, elevation_m: 14, min_flood_dist_km: 3.1 },
      { id: 1002, name: 'Sion Hospital', lat: 19.0437, lon: 72.8614, category: 'hospital', capacity: 1500, phone: '022-2407-6381', address: 'Sion', risk_state: 'SAFE', safety_score: 78, elevation_m: 18, min_flood_dist_km: 2.4 },
    ],
    schools: [
      { id: 1004, name: 'Municipal School Dharavi', lat: 19.0437, lon: 72.8553, category: 'school', capacity: 800, phone: '—', address: 'Dharavi', risk_state: 'MONITOR', safety_score: 55, elevation_m: 8, min_flood_dist_km: 0.9 },
    ],
    shelters: [
      { id: 1006, name: 'Dharavi Flood Relief Camp', lat: 19.0437, lon: 72.8553, category: 'shelter', capacity: 2500, phone: '1077', address: 'Dharavi', risk_state: 'MONITOR', safety_score: 58, elevation_m: 7, min_flood_dist_km: 0.8 },
      { id: 1007, name: 'Govandi Sports Complex', lat: 19.0500, lon: 72.9126, category: 'shelter', capacity: 3000, phone: '1077', address: 'Govandi', risk_state: 'SAFE', safety_score: 75, elevation_m: 22, min_flood_dist_km: 4.2 },
    ],
    top_recommendations: [],
    meta: { total_zones: 5, safe_count: 3, monitor_count: 2, at_risk_count: 0, evacuate_count: 0, timestamp: 'Fallback data' },
  },
  bengaluru: {
    flood_probability: 0, rainfall_72h: 0,
    hospitals: [{ id: 2001, name: 'Victoria Hospital', lat: 12.9660, lon: 77.5714, category: 'hospital', capacity: 1800, phone: '080-2670-1150', address: 'Fort Rd', risk_state: 'SAFE', safety_score: 88, elevation_m: 920, min_flood_dist_km: 5 }],
    schools: [{ id: 2003, name: 'Cubbon Park Shelter School', lat: 12.9763, lon: 77.5929, category: 'school', capacity: 600, phone: '—', address: 'Cubbon Park', risk_state: 'SAFE', safety_score: 84, elevation_m: 910, min_flood_dist_km: 4.1 }],
    shelters: [{ id: 2004, name: 'BBMP Shelter Koramangala', lat: 12.9279, lon: 77.6271, category: 'shelter', capacity: 1500, phone: '1533', address: 'Koramangala', risk_state: 'SAFE', safety_score: 80, elevation_m: 900, min_flood_dist_km: 3.5 }],
    top_recommendations: [], meta: { total_zones: 3, safe_count: 3, monitor_count: 0, at_risk_count: 0, evacuate_count: 0, timestamp: 'Fallback data' },
  },
  chennai: {
    flood_probability: 0, rainfall_72h: 0,
    hospitals: [{ id: 3001, name: 'Government General Hospital', lat: 13.0800, lon: 80.2700, category: 'hospital', capacity: 2700, phone: '044-2530-5000', address: 'Park Town', risk_state: 'SAFE', safety_score: 72, elevation_m: 8, min_flood_dist_km: 2.2 }],
    schools: [{ id: 3003, name: 'Govt High School Egmore', lat: 13.0789, lon: 80.2619, category: 'school', capacity: 500, phone: '—', address: 'Egmore', risk_state: 'MONITOR', safety_score: 60, elevation_m: 6, min_flood_dist_km: 1.1 }],
    shelters: [{ id: 3004, name: 'Marina Beach Relief Shelter', lat: 13.0521, lon: 80.2825, category: 'shelter', capacity: 5000, phone: '1913', address: 'Marina Beach', risk_state: 'MONITOR', safety_score: 55, elevation_m: 4, min_flood_dist_km: 0.5 }],
    top_recommendations: [], meta: { total_zones: 3, safe_count: 1, monitor_count: 2, at_risk_count: 0, evacuate_count: 0, timestamp: 'Fallback data' },
  },
  pune: {
    flood_probability: 0, rainfall_72h: 0,
    hospitals: [{ id: 4001, name: 'Sassoon General Hospital', lat: 18.5200, lon: 73.8744, category: 'hospital', capacity: 1400, phone: '020-2612-9800', address: 'Sassoon Rd', risk_state: 'SAFE', safety_score: 85, elevation_m: 565, min_flood_dist_km: 4.5 }],
    schools: [{ id: 4002, name: 'BMC School Hadapsar', lat: 18.5089, lon: 73.9260, category: 'school', capacity: 600, phone: '—', address: 'Hadapsar', risk_state: 'SAFE', safety_score: 78, elevation_m: 555, min_flood_dist_km: 3.8 }],
    shelters: [{ id: 4003, name: 'Nehru Stadium Flood Camp', lat: 18.5308, lon: 73.8685, category: 'shelter', capacity: 3000, phone: '1800-233-4567', address: 'Lashkar', risk_state: 'SAFE', safety_score: 82, elevation_m: 560, min_flood_dist_km: 4.0 }],
    top_recommendations: [], meta: { total_zones: 3, safe_count: 3, monitor_count: 0, at_risk_count: 0, evacuate_count: 0, timestamp: 'Fallback data' },
  },
};
