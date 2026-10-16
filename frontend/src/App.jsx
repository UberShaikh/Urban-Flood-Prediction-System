import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity, CloudRain, Droplets, Mountain, Navigation, ShieldAlert,
  Image as ImageIcon, UploadCloud, Bot, Satellite, AlertTriangle,
  CheckCircle, Radio, Layers, Zap, BarChart2, BookOpen, X,
  ChevronLeft, ChevronRight, Moon, Sun as SunIcon, Brain,
  Map, TrendingUp, Bell, Database, Eye, Search,
  Building2, Truck, Wind, Thermometer, Mail, Users, Home,
  Calendar, RefreshCw
} from 'lucide-react';
import axios from 'axios';
import FloodMap from './FloodMap.jsx';
import SimulatorTab from './SimulatorTab.jsx';
import CommandCenter from './CommandCenter.jsx';
import LiveFeedTab from './LiveFeedTab.jsx';
import SafeZonesTab from './SafeZonesTab.jsx';
import ChatbotPanel from './ChatbotPanel.jsx';
import KnowledgeBase from './KnowledgeBase.jsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts';



/* ── Floating Particles ── */
const FloatingParticles = () => {
  const particles = Array.from({ length: 10 }, (_, i) => ({
    id: i,
    size: Math.random() * 3 + 1.5,
    left: Math.random() * 100,
    delay: Math.random() * 20,
    duration: Math.random() * 25 + 20,
  }));

  return (
    <div className="particles-container">
      {particles.map(p => (
        <div
          key={p.id}
          className="particle"
          style={{
            width: p.size,
            height: p.size,
            left: `${p.left}%`,
            animationDuration: `${p.duration}s`,
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </div>
  );
};

/* ── Splash Screen ── */
const SplashScreen = () => (
  <div className="splash-screen">
    <div className="splash-content">
      <div className="splash-logo">
        <div className="splash-icon">
          <ShieldAlert size={32} />
        </div>
        <div className="splash-title">Aqua<span>Alert</span></div>
        <div className="splash-sub">FLOOD RISK INTELLIGENCE PLATFORM</div>
      </div>
      <div className="splash-progress">
        <div className="splash-progress-bar" />
      </div>
      <div className="splash-status">Connecting to regional sensors...</div>
    </div>
  </div>
);

/* ── System Status Bar ── */
const SystemStatusBar = ({ apiPhase, liveData, prediction }) => (
  <div className="system-status-bar">
    <div className="ssb-item">
      <span className={`ssb-dot ${apiPhase === 'ONLINE' ? 'green' : apiPhase === 'OFFLINE' ? 'red' : 'amber'}`} />
      <span className="ssb-label">API</span>
      <span className="ssb-value">{apiPhase}</span>
    </div>
    <div className="ssb-divider" />
    <div className="ssb-item">
      <Database size={11} />
      <span className="ssb-label">Model</span>
      <span className="ssb-value">XGBoost Fusion v2</span>
    </div>
    <div className="ssb-divider" />
    <div className="ssb-item">
      <Radio size={11} />
      <span className="ssb-label">Last Sync</span>
      <span className="ssb-value">{liveData?.timestamp || '—'}</span>
    </div>
    <div className="ssb-divider" />
    <div className="ssb-item">
      <Activity size={11} />
      <span className="ssb-label">Data Points</span>
      <span className="ssb-value">{liveData?.timeline?.length ? `${liveData.timeline.length * 6} processed` : '—'}</span>
    </div>
  </div>
);

const API = 'http://localhost:8001/api/v1';

// Fetches dynamic real timeline curve from the backend instead of dummy Math.sin simulation

const statusColor = s => {
  if (!s) return '#64748b';
  const u = s.toUpperCase();
  if (u === 'ONLINE' || u === 'SAFE' || u.includes('LOW')) return '#10b981';
  if (u.includes('MODERATE') || u.includes('MEDIUM') || u === 'SYNCHRONIZING') return '#f59e0b';
  if (u === 'OFFLINE' || u.includes('DANGER') || u.includes('HIGH') || u.includes('CRITICAL')) return '#ef4444';
  return '#f59e0b';
};


/* ── Sub-components ── */

const Slider = ({ icon: Icon, color, label, unit, min, max, step, value, onChange }) => {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  const pct = ((local - min) / (max - min)) * 100;
  return (
    <div className="slider-row">
      <div className="slider-meta">
        <span className="slider-label"><Icon size={13} color={color} />{label}</span>
        <span className="slider-val" style={{ color }}>{local}<span className="slider-unit">{unit}</span></span>
      </div>
      <div className="slider-track">
        <div className="slider-fill" style={{ width: `${pct}%`, background: color }} />
        <div className="slider-thumb" style={{ left: `${pct}%`, color }} />
        <input type="range" min={min} max={max} step={step} value={local}
          onChange={e => setLocal(parseFloat(e.target.value))}
          onMouseUp={() => onChange(local)} onTouchEnd={() => onChange(local)} />
      </div>
    </div>
  );
};

const Chip = ({ label, value, color = '#38bdf8' }) => (
  <div className="chip">
    <span className="chip-label">{label}</span>
    <span className="chip-value" style={{ color }}>{value}</span>
  </div>
);

const SectionHeader = ({ icon: Icon, color, title, badge }) => (
  <div className="section-header">
    <div className="section-icon" style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
      <Icon size={15} color={color} />
    </div>
    <span className="section-title">{title}</span>
    {badge && (
      <span className="section-badge" style={{ color, borderColor: `${color}40`, background: `${color}10` }}>
        {badge}
      </span>
    )}
  </div>
);

const StatCard = ({ icon: Icon, color, label, value, sub, trend, trendDir, loading }) => (
  <div className="stat-card" style={{ '--accent-color': color, '--icon-bg': `${color}12`, '--icon-border': `${color}25` }}>
    {loading ? (
      <div className="stat-skeleton">
        <div className="skel skel-icon" />
        <div className="skel skel-val" />
        <div className="skel skel-label" />
      </div>
    ) : (
      <>
        <div className="stat-card-top">
          <div className="stat-card-icon"><Icon size={16} color={color} /></div>
          {trend && <span className={`stat-card-trend ${trendDir}`}>{trend}</span>}
        </div>
        <div>
          <div className="stat-card-value">{value}</div>
          <div className="stat-card-label">{label}</div>
          {sub && <div className="stat-card-sub">{sub}</div>}
        </div>
      </>
    )}
  </div>
);

const ShapChart = ({ values, floodColor }) => {
  if (!values?.length) return null;
  return (
    <div className="shap-section">
      <div className="shap-title"><Brain size={11} />Feature Impact Analysis</div>
      {values.slice(0, 6).map(s => (
        <div key={s.feature} className="shap-row">
          <span className="shap-label">{s.feature}</span>
          <div className="shap-bar-wrap">
            <div className="shap-bar" style={{ width: `${s.pct}%`, background: s.direction === 'positive' ? floodColor : '#475569' }} />
          </div>
          <span className="shap-pct">{s.pct}%</span>
        </div>
      ))}
    </div>
  );
};

const XaiInsights = ({ liveData, prediction }) => {
  if (!liveData || !prediction) return null;
  let insights = [];

  // Cluster interpretation based on Notebook 5a metrics
  const isLowElev = liveData.elevation_m <= 30;
  const isFarDrain = liveData.drain_distance_m >= 400;

  if (isLowElev && isFarDrain) {
    insights.push(`Topographical Clustering: CRITICAL RISK ZONE. The baseline low elevation (${liveData.elevation_m}m) combined with distant drainage geometry (${liveData.drain_distance_m}m) naturally traps water locally, statistically matching high-risk historic spatial clusters.`);
  } else if (isLowElev) {
    insights.push(`Topographical Clustering: MODERATE RISK ZONE. Coastal/Basin elevation (${liveData.elevation_m}m) creates a natural choke point, but nearby drainage provides architectural mitigation.`);
  } else {
    insights.push(`Topographical Clustering: LOW RISK ZONE. High elevation (${liveData.elevation_m}m) naturally diverts water, offsetting significant hazard clustering.`);
  }

  // Live API Forecasting insights
  if (liveData.total_24h_forecast > 30) {
    insights.push(`Meteorological Projection: An incoming storm surge (${liveData.total_24h_forecast}mm) expected within 24h will significantly degrade soil saturation capacity and elevate urban pooling.`);
  } else if (liveData.total_72h_rain > 100) {
    insights.push(`Hydrological Load: The urban basin is currently heavily saturated from intense 72h historical rainfall (${liveData.total_72h_rain}mm), making it highly sensitive to overflow.`);
  }

  // Model Explainability (Feature Impact)
  if (prediction.shap_values && prediction.shap_values.length > 0) {
    const topFactor = prediction.shap_values[0].feature;
    insights.push(`Predictive Fusion Analysis: The active algorithmic assessment isolates [${topFactor}] as the primary mathematical driver dictating the current system alarm level.`);
  }

  return (
    <div style={{ marginTop: 24, padding: 14, background: 'var(--surface2)', borderRadius: 10, border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, color: 'var(--blue)', fontSize: '.75rem', fontWeight: 600, textTransform: 'uppercase' }}>
        <Brain size={13} />
        Explainable AI Data Synthesis
      </div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: '.73rem', color: 'var(--text2)', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {insights.map((ins, i) => (
          <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--blue)', marginTop: 8, flexShrink: 0 }} />
            <span>{ins}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const NavItem = ({ icon: Icon, label, id, active, badge, badgeColor, onClick }) => (
  <button className={`nav-item ${active ? 'active' : ''}`} onClick={() => onClick(id)}>
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Icon size={15} className={id === 'alerts' && badgeColor === 'red' ? 'pulse-red' : ''} style={{ borderRadius: '50%' }} />
      {id === 'alerts' && badgeColor === 'red' && (
        <span style={{ position: 'absolute', top: -2, right: -2, width: 6, height: 6, background: 'var(--red)', borderRadius: '50%', boxShadow: '0 0 6px var(--red)' }} />
      )}
    </div>
    {label}
    {badge && <span className={`nav-item-badge ${badgeColor || ''} ${badgeColor === 'red' ? 'pulse-red' : ''}`}>{badge}</span>}
  </button>
);

/* ── API Offline Banner ── */
const OfflineBanner = ({ onRetry }) => (
  <div className="offline-banner">
    <div className="offline-icon"><AlertTriangle size={28} /></div>
    <div className="offline-text">
      <div className="offline-title">Backend Offline</div>
      <div className="offline-sub">Cannot reach the prediction API. Start the backend server to enable live data.</div>
    </div>
    <button className="infer-btn" onClick={onRetry} style={{ flexShrink: 0 }}>
      <Radio size={14} /> Retry Connection
    </button>
  </div>
);

/* ── Custom Recharts Tooltip ── */
const RainTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 8, padding: '8px 12px', fontSize: '.7rem' }}>
      <div style={{ color: 'var(--muted2)', marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#38bdf8', fontWeight: 700, fontFamily: 'JetBrains Mono' }}>{payload[0].value} mm/h</div>
    </div>
  );
};

/* ══════════════════════════════════════════
   MAIN APP
══════════════════════════════════════════ */
export default function App() {
  const [theme, setTheme] = useState('light');
  const [tab, setTab] = useState('command');
  const [plots, setPlots] = useState([]);
  const [lightbox, setLightbox] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [visionFile, setVisionFile] = useState(null);
  const [visionResult, setVisionResult] = useState(null);
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionPreview, setVisionPreview] = useState(null);
  const [targetCity, setTargetCity] = useState('mumbai');
  const [toasts, setToasts] = useState([]);
  const [time, setTime] = useState(new Date());
  const [rainfallSeries, setRainfallSeries] = useState([]);
  const [liveData, setLiveData] = useState(null);
  const [aiMetrics, setAiMetrics] = useState(null);
  const [alertsData, setAlertsData] = useState(null);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [archiveData, setArchiveData] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveDates, setArchiveDates] = useState({ start: '2023-07-01', end: '2023-07-07' });

  const [simDate, setSimDate] = useState(null);

  const addToast = useCallback((msg, type = 'info') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5000);
  }, []);

  const fetchArchive = useCallback(() => {
    setArchiveLoading(true);
    axios.get(`${API}/archive/${targetCity}`, { params: archiveDates })
      .then(r => {
        setArchiveData(r.data);
        setArchiveLoading(false);
      })
      .catch(() => {
        addToast("Failed to fetch historical archive", "error");
        setArchiveLoading(false);
      });
  }, [targetCity, archiveDates, addToast]);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);
  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => { axios.get(`${API}/plots`).then(r => setPlots(r.data)).catch(() => { }); }, []);
  useEffect(() => { axios.get(`${API}/metrics`).then(r => setAiMetrics(r.data)).catch(() => { }); }, []);

  useEffect(() => {
    if (!lightbox) return;
    const h = e => {
      if (e.key === 'ArrowRight') setLightbox(l => ({ ...l, index: Math.min(l.index + 1, l.list.length - 1) }));
      if (e.key === 'ArrowLeft') setLightbox(l => ({ ...l, index: Math.max(l.index - 1, 0) }));
      if (e.key === 'Escape') setLightbox(null);
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [lightbox]);

  useEffect(() => {
    // Fetch live data directly from the Open-Meteo integration endpoint
    setLoading(true);
    axios.get(`${API}/live/${targetCity}`, { params: simDate ? { sim_date: simDate } : {} })
      .then(r => {
        setLiveData(r.data);
        setRainfallSeries(r.data.timeline);

        // Push the strictly historical 72h tail block into the predictive risk fusion pipeline
        return axios.post(`${API}/predict`, {
          rainfall_72h: r.data.rainfall_72h,
          forecast_24h: r.data.total_24h_forecast,
          elevation_m: r.data.elevation_m,
          drain_distance_m: r.data.drain_distance_m
        });
      })
      .then(r => {
        setPrediction(r.data);
        setLoading(false);
      })
      .catch(e => {
        addToast("Failed to load live data/prediction for " + targetCity, "error");
        setPrediction({ prediction_status: 'API OFFLINE', flood_probability: 0, lstm_flood_probability: 0 });
        setLoading(false);
      });
  }, [targetCity, simDate, addToast]);

  const fetchAlerts = useCallback(() => {
    setAlertsLoading(true);
    axios.get(`${API}/alerts`, { params: simDate ? { sim_date: simDate } : {} })
      .then(r => {
        setAlertsData(r.data);
        setAlertsLoading(false);
      })
      .catch(() => {
        addToast("Failed to fetch system alerts", "error");
        setAlertsLoading(false);
      });
  }, [addToast, simDate]);

  const resetToLive = useCallback(() => {
    setSimDate(null);
    setPrediction(null);
    setLiveData(null);
    setAlertsData(null);
    setRainfallSeries([]);
    addToast("Restoring live regional sensors...", "info");
  }, [addToast]);

  useEffect(() => {
    fetchAlerts();
  }, [simDate, fetchAlerts]);

  const runVision = async () => {
    if (!visionFile) return;
    setVisionLoading(true);
    setVisionResult(null);
    try {
      const b64 = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(',')[1]);
        r.onerror = rej;
        r.readAsDataURL(visionFile);
      });
      // Set preview immediately so image shows during loading
      if (!visionPreview) setVisionPreview(URL.createObjectURL(visionFile));
      const r = await axios.post(`${API}/vision`, { image_base64: b64, city: targetCity });
      setVisionResult(r.data);
    } catch (e) {
      setVisionResult({ status: 'ERROR', message: e?.response?.data?.detail || e?.message || 'Inference failed' });
    }
    setVisionLoading(false);
  };

  const syncAndFetchSAR = async () => {
    setVisionLoading(true); setVisionResult(null); setVisionPreview(null);
    try {
      addToast('Dispatching Earth Engine synchronization request...', 'info');
      const rSync = await axios.post(`${API}/trigger-gee`);
      addToast(`GEE Sync: ${rSync.data.message}`, 'success');

      const r = await axios.get(`${API}/sar-feed/${targetCity}`);
      if (r.data.status === 'SUCCESS') {
        const b64 = r.data.image_base64;
        setVisionPreview(`data:image/png;base64,${b64}`);
        const rVision = await axios.post(`${API}/vision`, { image_base64: b64, city: targetCity });
        setVisionResult(rVision.data);
      }
    } catch (e) {
      addToast(`Sync/Feed Error: ${e?.response?.data?.message || e.message}`, 'error');
    }
    setVisionLoading(false);
  };

  const apiPhase = loading ? 'SYNCHRONIZING' : prediction?.prediction_status === 'API OFFLINE' ? 'OFFLINE' : 'ONLINE';
  const apiColor = statusColor(apiPhase);
  const floodColor = statusColor(prediction?.prediction_status ?? prediction?.final_alert_level);
  const floodProb = prediction?.flood_probability ?? prediction?.lstm_flood_probability ?? 0;
  const circumference = 2 * Math.PI * 54; // r=54
  const dashArray = `${(floodProb / 100) * circumference} ${circumference}`;
  const groups = [...new Set(plots.map(p => p.group))];
  const alertLevel = prediction?.prediction_status ?? prediction?.final_alert_level ?? 'AWAITING';

  return (
    <div className="app">

      {/* Floating Particles Background */}
      <FloatingParticles />

      {/* Splash Screen */}
      {loading && !prediction && !liveData && <SplashScreen />}

      {/* Toasts */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span className="toast-icon">{t.type === 'error' ? <AlertTriangle size={14} /> : t.type === 'success' ? <CheckCircle size={14} /> : <Radio size={14} />}</span>
            <span className="toast-msg">{t.msg}</span>
            <div className="toast-progress" />
          </div>
        ))}
      </div>


      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="logo-mark" style={{ background: 'transparent', boxShadow: 'none', border: 'none' }}>
            <img src="/Cresting turquoise wave design.png" alt="Logo" style={{ width: '100%', height: '100%', objectFit: 'contain', filter: 'brightness(1.1) saturate(1.2)' }} />
          </div>
          <div>
            <div className="logo-title">Aqua<span>Alert</span></div>
            <div className="logo-sub">Flood Risk Monitoring</div>
          </div>
          <div className="topbar-divider" />
          <div className={`status-pill ${apiPhase === 'ONLINE' ? 'online' : apiPhase === 'OFFLINE' ? 'offline' : 'syncing'}`}>
            <span className={`pulse-dot ${apiPhase === 'ONLINE' ? 'green' : apiPhase === 'OFFLINE' ? 'red' : 'amber'}`} />
            API {apiPhase}
          </div>
        </div>

        <div className="topbar-center">
          <div className={`sim-picker ${simDate ? 'is-simulating' : ''}`}>
            <div className="sim-info">
              <input
                type="date"
                value={simDate || ''}
                onChange={e => {
                  setSimDate(e.target.value);
                  addToast(`Replaying historical telemetry: ${e.target.value}`, 'info');
                }}
              />
            </div>
            {simDate && (
              <button className="sim-reset-btn" onClick={resetToLive} title="Reset to Live Mode">
                <RefreshCw size={11} />
              </button>
            )}
          </div>
        </div>
        <div className="topbar-right">
          <button className="theme-toggle" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} title="Toggle theme">
            {theme === 'dark' ? <SunIcon size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </header>

      {/* Header Nav */}
      <nav className="header-nav">
        <NavItem icon={Map} label="Command Center" id="command" active={tab === 'command'} onClick={setTab} />
        <NavItem icon={Activity} label="Dashboard" id="dashboard" active={tab === 'dashboard'} onClick={setTab} badge={alertLevel !== 'AWAITING' ? alertLevel.split(' ')[0] : null} badgeColor={floodProb > 60 ? 'red' : floodProb > 30 ? '' : 'green'} />
        <NavItem icon={Radio} label="Live Feed" id="live_feed" active={tab === 'live_feed'} onClick={setTab} badge="NEW" badgeColor="blue" />
        <NavItem icon={ShieldAlert} label="Safe Zones" id="safe_zones" active={tab === 'safe_zones'} onClick={setTab} />
        <NavItem icon={Satellite} label="SAR Vision" id="vision" active={tab === 'vision'} onClick={setTab} />
        <NavItem icon={Bell} label="Alerts" id="alerts" active={tab === 'alerts'} onClick={setTab}
          badge={alertsData?.summary?.critical > 0 ? 'CRITICAL' : (alertsData?.summary?.warning > 0 ? 'WARNING' : null)}
          badgeColor={alertsData?.summary?.critical > 0 ? 'red' : (alertsData?.summary?.warning > 0 ? 'amber' : '')} />
        <NavItem icon={Brain} label="GAN Sim" id="simulator" active={tab === 'simulator'} onClick={setTab} />
        <div className="nav-spacer" />
        <div className="nav-divider" />
        <NavItem icon={BookOpen} label="Knowledge Base" id="knowledge" active={tab === 'knowledge'} onClick={setTab} />
      </nav>

      {/* Alert Ticker */}
      {alertsData?.alerts?.some(a => a.risk_level?.includes('CRITICAL') || a.risk_level?.includes('HIGH')) && (
        <div className="alert-ticker">
          <span className="at-label">⚠ LIVE ALERTS</span>
          <div className="at-track">
            <div className="at-content">
              {alertsData.alerts.filter(a => a.risk_level?.includes('CRITICAL') || a.risk_level?.includes('HIGH')).map((a, i) => (
                <span key={i} className="at-item"><span className="at-city">{a.city}</span>: {a.risk_level} — {a.action}<span className="at-sep"> • </span></span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Body */}
      <div className={`layout${tab === 'command' ? ' command-layout' : ''}`}>

        {/* Main Content */}
        <main className={`content${tab === 'command' ? ' command-content' : ''}`}>

          {/* ══ COMMAND CENTER ══ */}
          {tab === 'command' && (
            <CommandCenter
              liveData={liveData}
              prediction={prediction}
              alertsData={alertsData}
              targetCity={targetCity}
              setTargetCity={setTargetCity}
              rainfallSeries={rainfallSeries}
              loading={loading}
              time={time}
              simDate={simDate}
              visionResult={visionResult}
              visionPreview={visionPreview}
            />
          )}

          {/* ══ LIVE FEED ══ */}
          {tab === 'live_feed' && (
            <LiveFeedTab targetCity={targetCity} simDate={simDate} />
          )}

          {/* ══ SAFE ZONES ══ */}
          {tab === 'safe_zones' && (
            <SafeZonesTab
              targetCity={targetCity}
              setTargetCity={setTargetCity}
              prediction={prediction}
              alertsData={alertsData}
              liveData={liveData}
              simDate={simDate}
            />
          )}

          {/* ══ DASHBOARD ══ */}
          {/* Simulation Banner */}
          {simDate && (
            <div style={{ background: '#0e1013', color: '#7a8898', padding: '10px 20px', borderRadius: 6, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '.72rem', fontWeight: 600, border: '1px solid rgba(55,62,75,0.8)', letterSpacing: '1px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Activity size={14} className="spin-slow" color="#506a88" />
                <span>HISTORICAL REPLAY ACTIVE: <span style={{ color: '#506a88' }}>{simDate}</span> · SIMULATION MODE</span>
              </div>
              <button onClick={resetToLive} style={{ background: 'rgba(38,42,52,0.6)', color: '#7a8898', border: '1px solid rgba(55,62,75,0.8)', padding: '5px 14px', borderRadius: 5, cursor: 'pointer', fontSize: '.65rem', fontWeight: 700, letterSpacing: '1px' }}>RESTORE LIVE</button>
            </div>
          )}

          {tab === 'dashboard' && <>
            {/* Offline Banner */}
            {apiPhase === 'OFFLINE' && <OfflineBanner onRetry={() => { setPrediction(null); setLiveData(null); }} />}

            {/* Top Row: Stats + Hero */}
            <div className="dashboard-top animate-in">
              {/* Stat Cards 2x2 */}
              <div className="stat-grid-2x2">
                <StatCard icon={ShieldAlert} color={floodColor} loading={loading}
                  label="Flood Probability" value={`${floodProb.toFixed(1)}%`}
                  sub="AI predictive score" trend={floodProb > 60 ? 'Critical risk' : floodProb > 30 ? 'Moderate' : 'Low risk'}
                  trendDir={floodProb > 60 ? 'up' : floodProb > 30 ? 'neutral' : 'down'} />
                <StatCard icon={CloudRain} color="#3b82f6" loading={loading}
                  label="72h Rainfall" value={liveData ? `${liveData.total_72h_rain} mm` : '—'}
                  sub="Actual region accumulation" trend={liveData && liveData.total_72h_rain > 150 ? 'Heavy' : 'Nominal'} trendDir={liveData && liveData.total_72h_rain > 150 ? 'up' : 'neutral'} />
                <StatCard icon={Droplets} color="#059669" loading={loading}
                  label="Drain Distance" value={liveData ? `${liveData.drain_distance_m} m` : '—'}
                  sub="Nearest major outlet" />
                <StatCard icon={Mountain} color="#7c3aed" loading={loading}
                  label="Elevation MSL" value={liveData ? `${liveData.elevation_m} m` : '—'}
                  sub="Mean sea level offset" />
              </div>

              {/* Hero Banner (Square) */}
              <div className="hero-banner">
                <div className="hero-content">
                  <div className="hero-left">
                    <div className="hero-greeting">
                      <ShieldAlert size={20} />
                      <span>Flood Risk Dashboard</span>
                    </div>
                    <div className="hero-city">{targetCity.charAt(0).toUpperCase() + targetCity.slice(1)}, India</div>
                    <div className="hero-meta">
                      <span>Real-time monitoring</span>
                      <span className="hero-dot">•</span>
                      <span>AI fusion algorithms</span>
                    </div>
                    <div className="hero-date">{new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</div>
                  </div>
                  <div className="hero-risk-badge" style={{ background: '#111418', borderColor: 'rgba(55,62,75,0.8)' }}>
                    <div className="hero-risk-value" style={{ color: floodProb > 60 ? '#8b2020' : floodProb > 30 ? '#7a6a14' : '#2a6a3a' }}>{loading ? '—' : `${floodProb.toFixed(0)}%`}</div>
                    <div className="hero-risk-label" style={{ color: '#7a8898' }}>FLOOD RISK</div>
                  </div>
                </div>
              </div>
            </div>

            {/* System Status Bar */}
            <SystemStatusBar apiPhase={apiPhase} liveData={liveData} prediction={prediction} />

            {/* Rainfall Timeline */}
            <div className="chart-card card-accent-blue">
              <SectionHeader icon={TrendingUp} color="#38bdf8" title="Global Precipitation Telemetry (Open-Meteo Feed)" badge="LIVE" />
              <div className="chart-body">
                <ResponsiveContainer width="100%" height={160}>
                  <AreaChart data={rainfallSeries} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="rainGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="time" tick={{ fontSize: 9 }} interval={11} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip content={<RainTooltip />} />
                    <Area type="monotone" dataKey="mm" stroke="#3b82f6" strokeWidth={2} fill="url(#rainGrad)" dot={false} activeDot={{ r: 4, fill: '#3b82f6' }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Controls + Risk Assessment */}
            <div className="row-2col animate-in" style={{ animationDelay: '0.2s' }}>
              {/* Input Controls */}
              <div className="card card-accent-green">
                <SectionHeader icon={Activity} color="#10b981" title="Live Telemetry Setup" badge="CONNECTED" />
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <div style={{ fontSize: '.65rem', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}><Map size={12} style={{ marginRight: 4, transform: 'translateY(2px)' }} />Target Sensor Block</div>
                    <select className="city-select" value={targetCity} onChange={e => setTargetCity(e.target.value)} style={{ padding: '8px 12px', fontSize: '.8rem', width: '100%' }}>
                      <option value="mumbai">Mumbai Region</option>
                      <option value="bengaluru">Bengaluru Urban</option>
                      <option value="chennai">Chennai Floodplains</option>
                      <option value="pune">Pune District</option>
                    </select>
                  </div>

                  <div style={{ background: 'var(--surface2)', padding: 14, borderRadius: 5, border: '1px solid var(--border2)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: '.65rem', color: 'var(--muted)', letterSpacing: '.5px' }}>Connection:</span>
                      <span style={{ fontSize: '.65rem', color: 'var(--green)', fontWeight: 600 }}>● SECURE HTTPS</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: '.65rem', color: 'var(--muted)', letterSpacing: '.5px' }}>Source Stream:</span>
                      <span style={{ fontSize: '.65rem', color: 'var(--blue)', fontWeight: 600 }}>Open-Meteo Grid</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '.65rem', color: 'var(--muted)', letterSpacing: '.5px' }}>Last Ping:</span>
                      <span style={{ fontSize: '.65rem', color: 'var(--text2)', fontWeight: 500, fontFamily: 'JetBrains Mono' }}>{liveData ? liveData.timestamp : 'SYNCING...'}</span>
                    </div>
                  </div>

                  <div style={{ background: 'var(--surface2)', padding: 14, borderRadius: 5, border: '1px solid var(--border2)' }}>
                    <span style={{ fontSize: '.65rem', fontWeight: 700, color: 'var(--blue)', display: 'block', marginBottom: 4, letterSpacing: '1px', textTransform: 'uppercase' }}>Upcoming Forecast (24h)</span>
                    <span style={{ fontSize: '1rem', fontFamily: 'JetBrains Mono', fontWeight: 700, color: 'var(--text)' }}>
                      {liveData ? `${liveData.total_24h_forecast} mm` : '—'}
                    </span>
                    <span style={{ fontSize: '.6rem', color: 'var(--muted)', display: 'block', marginTop: 2 }}>Projected inbound rainfall</span>
                  </div>

                  <div className="panel-section" style={{ marginTop: 6, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                    <div style={{ fontSize: '.65rem', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 12 }}>System Mode: {simDate ? 'Simulation Replay' : 'Real-time Live'}</div>
                    <div style={{ fontSize: '.7rem', color: 'var(--text3)', lineHeight: 1.4 }}>
                      {simDate
                        ? `Viewing historical telemetry for ${simDate}. Rain and risk patterns reflect recorded data for this period.`
                        : 'Currently streaming live feeds from regional sensors and Open-Meteo satellite grid.'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Flood Risk Assessment */}
              <div className="card card-accent-orange flood-card animate-in" style={{ animationDelay: '0.1s' }}>
                <div className="water-overlay" style={{
                  height: `${floodProb}%`,
                  background: 'linear-gradient(180deg, rgba(14, 165, 233, 0.1) 0%, rgba(14, 165, 233, 0.25) 100%)',
                  borderTopColor: 'rgba(14, 165, 233, 0.3)'
                }}>
                  <div className="water-wave" style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 20' preserveAspectRatio='none'%3E%3Cpath d='M0,10 C150,20 200,0 400,10 C600,20 650,0 800,10 L800,20 L0,20 Z' fill='rgba(14, 165, 233, 0.15)'/%3E%3C/svg%3E")`
                  }} />
                </div>
                <SectionHeader icon={ShieldAlert} color={floodColor} title="Flood Risk Assessment" badge="MODEL OUTPUT" />
                <div className="flood-body">
                  <div className="flood-ring-wrap">
                    <svg viewBox="0 0 120 120" className="ring-svg">
                      <circle cx="60" cy="60" r="54" className="ring-track" />
                      <circle cx="60" cy="60" r="54" className="ring-glow" style={{ stroke: floodColor, strokeDasharray: dashArray }} />
                      <circle cx="60" cy="60" r="54" className="ring-progress" style={{ stroke: floodColor, strokeDasharray: dashArray }} />
                    </svg>
                    <div className="ring-center">
                      <span className="ring-pct" style={{ color: floodColor }}>{loading ? '—' : `${prediction?.flood_probability || 0}%`}</span>
                      <span className="ring-label">Risk Probability</span>
                    </div>
                  </div>

                  <div className="flood-status-badge" style={{ color: floodColor, borderColor: `${floodColor}40`, background: `${floodColor}10` }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: floodColor, flexShrink: 0, boxShadow: `0 0 8px ${floodColor}` }} />
                    {loading ? 'COMPUTING...' : alertLevel}
                  </div>

                  {prediction?.recommended_action && (
                    <div className="action-banner" style={{ borderColor: `${floodColor}40`, background: `${floodColor}08` }}>
                      <AlertTriangle size={14} color={floodColor} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span style={{ color: 'var(--text2)', fontSize: '.73rem' }}>{prediction.recommended_action}</span>
                    </div>
                  )}

                  <ShapChart values={prediction?.shap_values} floodColor={floodColor} />
                  <XaiInsights liveData={liveData} prediction={prediction} />

                  <div className="flood-chips" style={{ marginTop: 18 }}>
                    <Chip label="Elev." value={liveData ? `${liveData.elevation_m}m` : '—'} color="#a78bfa" />
                    <Chip label="Drain" value={liveData ? `${(liveData.drain_distance_m / 1000).toFixed(1)}km` : '—'} color="#34d399" />
                    <Chip label="Rain(72h)" value={liveData ? `${liveData.total_72h_rain}mm` : '—'} color="#38bdf8" />
                  </div>
                </div>
              </div>
            </div>
          </>}

          {/* ══ SAR VISION ══ */}
          {tab === 'vision' && <>
            <div className="hero-banner hero-purple animate-in">
              <div className="hero-content">
                <div className="hero-left">
                  <div className="hero-greeting"><Satellite size={20} /><span>SAR Imagery Analysis</span></div>
                  <div className="hero-city">Computer Vision Module</div>
                  <div className="hero-meta">
                    <span>Deep learning segmentation</span>
                    <span className="hero-dot">•</span>
                    <span>GEE satellite feed</span>
                    <span className="hero-dot">•</span>
                    <span>ResNet50 architecture</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="vision-stats-row">
              {[
                { icon: Satellite, color: '#818cf8', label: 'Model', value: 'ResNet50 v1' },
                { icon: Layers, color: '#38bdf8', label: 'Input Size', value: '128x128 px' },
                { icon: Eye, color: '#10b981', label: 'Mode', value: 'SAR Segmentation' },
                { icon: Zap, color: '#f59e0b', label: 'GEE Sync', value: visionLoading ? 'Running...' : 'Ready' },
              ].map(s => (
                <div key={s.label} className="vision-stat-chip">
                  <div className="vsc-icon" style={{ background: `${s.color}15`, border: `1px solid ${s.color}30` }}>
                    <s.icon size={14} color={s.color} />
                  </div>
                  <div>
                    <div className="vsc-label">{s.label}</div>
                    <div className="vsc-value" style={{ color: s.color }}>{s.value}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="card card-accent-blue">
              <SectionHeader icon={Satellite} color="#38bdf8" title="SAR Imagery Analysis" badge="IMAGE ANALYTICS" />
              <div className="vision-grid">
                <div className="vision-upload">
                  <div className="vision-panel-label">Input Source</div>
                  <label htmlFor="vf" className={`dropzone ${visionFile ? 'active' : ''}`}>
                    <UploadCloud size={26} color={visionFile ? '#38bdf8' : 'var(--muted)'} />
                    <span className="dz-title">{visionFile ? visionFile.name : 'Upload SAR image or satellite scan'}</span>
                    <span className="dz-sub">PNG · JPG · TIFF · GeoTIFF</span>
                    <input id="vf" type="file" accept="image/*" style={{ display: 'none' }}
                      onChange={e => {
                        const f = e.target.files?.[0] || null;
                        setVisionFile(f);
                        if (f) setVisionPreview(URL.createObjectURL(f));
                        else setVisionPreview(null);
                      }} />
                  </label>
                  <button className="infer-btn" disabled={visionLoading || !visionFile} onClick={runVision}>
                    {visionLoading ? <><span className="spinner" />Analyzing...</> : <><Bot size={14} />Analyze Image</>}
                  </button>
                  <div className="or-divider"><span>or fetch live satellite feed</span></div>
                  <div className="vision-panel-label">Target Region</div>
                  <select className="city-select" value={targetCity} onChange={e => setTargetCity(e.target.value)}>
                    <option value="mumbai">Mumbai Region</option>
                    <option value="bengaluru">Bengaluru</option>
                    <option value="chennai">Chennai</option>
                    <option value="pune">Pune District</option>
                  </select>
                  <button className="infer-btn purple" disabled={visionLoading} onClick={syncAndFetchSAR} style={{ width: '100%' }}>
                    {visionLoading ? <><span className="spinner" />Syncing GEE...</> : <><Zap size={14} />Live Sync &amp; Analyze SAR</>}
                  </button>
                  {visionFile && !visionLoading && (
                    <button className="clear-btn" onClick={() => { setVisionFile(null); setVisionResult(null); setVisionPreview(null); }}>
                      Clear Selection
                    </button>
                  )}
                </div>

                <div className="vision-result">
                  {/* Always show preview image if available */}
                  {visionPreview && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: '.65rem', color: 'var(--muted)', fontWeight: 700, letterSpacing: 1, marginBottom: 6 }}>INPUT IMAGE</div>
                      <img src={visionPreview} alt="SAR input"
                        style={{
                          width: '100%', maxHeight: 200, objectFit: 'contain', borderRadius: 6,
                          border: '1px solid var(--border2)', background: '#0a0c0f'
                        }} />
                    </div>
                  )}

                  {!visionResult && !visionLoading && !visionPreview && (
                    <div className="vr-empty">
                      <Layers size={34} style={{ color: 'var(--muted)' }} />
                      <span>No scan available</span>
                      <span className="vr-hint">Upload SAR imagery or use Live Sync to fetch satellite data.</span>
                    </div>
                  )}

                  {visionLoading && (
                    <div className="vr-loading">
                      <div className="scan-bar"><div className="scan-fill" /></div>
                      <Radio size={18} color="#38bdf8" />
                      <span>PROCESSING IMAGE ANALYSIS...</span>
                    </div>
                  )}

                  {visionResult && !visionLoading && (() => {
                    const err = visionResult.status === 'ERROR';
                    const flooded = visionResult.flood_state === 'FLOODED';
                    const score = visionResult.flood_percentage ?? 0;
                    const ac = err ? '#ef4444' : flooded ? '#ef4444' : '#10b981';
                    const Ic = err || flooded ? AlertTriangle : CheckCircle;
                    return (
                      <div className="vr-result" style={{ '--ac': ac }}>
                        <div className="vr-top">
                          <div className="vr-dot" style={{ background: ac, boxShadow: `0 0 8px ${ac}` }} />
                          <span className="vr-state" style={{ color: ac }}>{err ? 'ERROR' : visionResult.flood_state}</span>
                          {!err && <span className="vr-mode">{visionResult.model_type || visionResult.mode}</span>}
                          <Ic size={17} color={ac} style={{ marginLeft: 'auto' }} />
                        </div>

                        {err && (
                          <p className="vr-msg" style={{ color: '#ef4444', marginTop: 8 }}>{visionResult.message}</p>
                        )}

                        {!err && <>
                          <div className="vr-score-row">
                            <span className="vr-score-label">Flood Saturation Score</span>
                            <span className="vr-score-val" style={{ color: ac }}>{score}%</span>
                          </div>
                          <div className="vr-bar"><div className="vr-bar-fill" style={{ width: `${score}%`, background: `linear-gradient(90deg,${ac}80,${ac})` }} /></div>
                          <div className="vr-metrics">
                            <div className="vr-metric"><span className="vr-metric-label">Zone Risk</span><span className="vr-metric-val" style={{ color: ac }}>{score > 60 ? 'HIGH' : score > 15 ? 'MODERATE' : 'LOW'}</span></div>
                            <div className="vr-metric"><span className="vr-metric-label">Engine</span><span className="vr-metric-val">{visionResult.model_type || 'Vision v1'}</span></div>
                            <div className="vr-metric"><span className="vr-metric-label">Resolution</span><span className="vr-metric-val">128×128 (30m)</span></div>
                          </div>

                          {visionResult.pixel_stats && (
                            <div className="vr-metrics">
                              {[
                                { label: 'Dark Pixels', value: `${visionResult.pixel_stats.dark_pixel_ratio}%`, color: '#64748b' },
                                { label: 'Brightness', value: visionResult.pixel_stats.brightness, color: '#fbbf24' },
                                { label: 'Texture Var', value: visionResult.pixel_stats.texture_variance, color: '#a78bfa' },
                              ].map(c => (
                                <div key={c.label} className="vr-metric">
                                  <span className="vr-metric-label">{c.label}</span>
                                  <span className="vr-metric-val" style={{ color: c.color }}>{c.value}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          <p className="vr-msg">
                            {flooded
                              ? `⚠ Anomaly detected. Significant inundation backscatter at ${score}% threshold saturation.`
                              : `✓ Feed nominal. Radar returns identify ${score}% stable topology matching pre-flood parameters.`}
                          </p>

                          {/* GradCAM / Saliency heatmap */}
                          {visionResult.gradcam && (
                            <div style={{ marginTop: 12 }}>
                              <div style={{ fontSize: '.65rem', color: 'var(--muted)', fontWeight: 700, letterSpacing: 1, marginBottom: 6 }}>SALIENCY HEATMAP OVERLAY</div>
                              <div className="gradcam-wrap" style={{ position: 'relative', borderRadius: 6, overflow: 'hidden', background: '#0a0c0f' }}>
                                {visionPreview && (
                                  <img className="gradcam-base" src={visionPreview} alt="original"
                                    style={{ width: '100%', display: 'block', maxHeight: 220, objectFit: 'contain' }} />
                                )}
                                <img
                                  src={`data:image/png;base64,${visionResult.gradcam}`}
                                  alt="heatmap"
                                  style={{
                                    position: visionPreview ? 'absolute' : 'relative',
                                    inset: 0, width: '100%', height: '100%',
                                    objectFit: 'contain',
                                    mixBlendMode: 'hard-light',
                                    opacity: 0.85,
                                  }}
                                />
                              </div>
                              <div className="gradcam-label" style={{ fontSize: '.62rem', color: 'var(--muted2)', marginTop: 4, textAlign: 'center' }}>
                                Red = flood signature · Blue = stable terrain
                              </div>
                            </div>
                          )}

                          {/* XAI Insight */}
                          {visionResult.xai_insight && (
                            <div className="xai-panel" style={{ borderLeftColor: ac, marginTop: 12 }}>
                              <div className="xai-header" style={{ color: ac }}><Brain size={12} />XAI Diagnostic Insights</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {visionResult.xai_insight.replace(/\\n/g, '\n').split('\n').filter(l => l.trim()).map((line, i) => {
                                  const text = line.replace(/^[-•]\s*/, '').replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--text)">$1</strong>');
                                  return (
                                    <div key={i} style={{ fontSize: '.73rem', lineHeight: 1.65, color: 'var(--text2)' }}
                                      dangerouslySetInnerHTML={{ __html: text }} />
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </>}
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
          </>}


          {/* ══ KNOWLEDGE BASE ══ */}
          {tab === 'knowledge' && (
            <KnowledgeBase />
          )}

          {/* ══ ALERTS SYSTEM ══ */}
          {tab === 'alerts' && (
            <div className="alerts-page">
              {/* Hero */}
              <div className="hero-banner hero-amber animate-in">
                <div className="hero-content" style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <div className="hero-left">
                    <div className="hero-greeting"><span>Active Alerts &amp; Dispatches</span></div>
                    <div className="hero-city">Cross-Region Monitoring</div>
                    <div className="hero-meta">
                      <span>Automated alarm aggregation</span>
                      <span className="hero-dot">•</span>
                      <span>{alertsData?.summary ? `${alertsData.summary.critical + alertsData.summary.warning} active alerts` : 'Loading...'}</span>
                    </div>
                  </div>
                  <button className="infer-btn" onClick={fetchAlerts} disabled={alertsLoading} style={{ background: 'rgba(38,42,52,0.6)', border: '1px solid rgba(55,62,75,0.8)', color: '#7a8898', boxShadow: 'none', marginLeft: 'auto' }}>
                    {alertsLoading ? <span className="spinner" /> : null} Refresh All
                  </button>
                </div>
              </div>

              {/* Summary Cards */}
              <div className="alerts-summary">
                {alertsData ? (
                  <>
                    <div className="summary-item summary-critical">
                      <div>
                        <div className="summary-count" style={{ color: 'var(--red)' }}>{alertsData.summary.critical}</div>
                        <div className="summary-label">Critical Alerts</div>
                      </div>
                    </div>
                    <div className="summary-item summary-warning">
                      <div>
                        <div className="summary-count" style={{ color: 'var(--amber)' }}>{alertsData.summary.warning}</div>
                        <div className="summary-label">Active Warnings</div>
                      </div>
                    </div>
                    <div className="summary-item summary-safe">
                      <div>
                        <div className="summary-count" style={{ color: 'var(--green)' }}>{alertsData.summary.clear}</div>
                        <div className="summary-label">Safe Regions</div>
                      </div>
                    </div>
                  </>
                ) : (
                  [0, 1, 2].map(i => (
                    <div key={i} className="summary-item">
                      <div className="stat-skeleton" style={{ width: '100%' }}>
                        <div className="skel skel-val" />
                        <div className="skel skel-label" />
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Loading */}
              {alertsLoading && (
                <div className="alerts-loading">
                  <div className="scan-bar" style={{ width: 200 }}><div className="scan-fill" /></div>
                  <span>POLLING REGIONAL SENSORS...</span>
                </div>
              )}

              {/* Offline state — show skeleton alert cards */}
              {!alertsLoading && !alertsData && (
                <>
                  <div className="offline-banner">
                    <div className="offline-text">
                      <div className="offline-title">Alerts Unavailable</div>
                      <div className="offline-sub">Cannot reach the backend API. Start the server to load regional alert data.</div>
                    </div>
                    <button className="infer-btn" onClick={fetchAlerts} style={{ flexShrink: 0 }}>
                      Retry
                    </button>
                  </div>
                  <div className="alerts-list">
                    {['MUMBAI', 'CHENNAI', 'BENGALURU', 'PUNE'].map((city, i) => (
                      <div key={city} className="alert-card-new ac-warning">
                        <div className="acn-accent" style={{ background: 'var(--border2)' }} />
                        <div className="acn-body">
                          <div className="acn-header">
                            <span className="acn-city" style={{ color: 'var(--text3)' }}>{city} REGION</span>
                            <span className="acn-level" style={{ color: 'var(--muted2)', background: 'var(--surface2)', borderColor: 'var(--border)' }}>AWAITING DATA</span>
                          </div>
                          <div className="acn-meta">
                            <span><CloudRain size={11} />— mm / 72h</span>
                            <span><TrendingUp size={11} />— mm forecast</span>
                            <span style={{ color: 'var(--muted)' }}><Satellite size={11} />SAR: Pending</span>
                          </div>
                          <div className="acn-action" style={{ color: 'var(--muted2)' }}>
                            <span>Connect backend to load live risk assessment</span>
                          </div>
                        </div>
                        <div className="acn-right">
                          <div className="acn-prob" style={{ color: 'var(--muted)' }}>
                            <span className="acn-prob-val">—%</span>
                            <span className="acn-prob-label">Flood Risk</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* No alerts */}
              {!alertsLoading && alertsData && !alertsData?.alerts?.length && (
                <div className="vr-empty" style={{ minHeight: 200 }}>
                  <span>No alerts detected</span>
                </div>
              )}

              <div className="alerts-list">
                {alertsData?.alerts?.map(alert => {
                  const isHigh = alert.risk_level.includes('HIGH') || alert.risk_level.includes('DANGER');
                  const isMed = alert.risk_level.includes('MODERATE') || alert.risk_level.includes('MONITOR');
                  const color = isHigh ? 'var(--red)' : isMed ? 'var(--amber)' : 'var(--green)';
                  const rawColor = isHigh ? '#ef4444' : isMed ? '#f59e0b' : '#10b981';
                  const Icon = isHigh ? AlertTriangle : isMed ? ShieldAlert : CheckCircle;
                  return (
                    <div key={alert.id} className={`alert-card-new ${isHigh ? 'ac-critical' : isMed ? 'ac-warning' : 'ac-safe'}`}>
                      {/* Left accent */}
                      <div className="acn-accent" style={{ background: color }} />


                      {/* Main info */}
                      <div className="acn-body">
                        <div className="acn-header">
                          <span className="acn-city">{alert.city} REGION</span>
                          {alert.trend && (
                            <span className="acn-trend" style={{
                              background: alert.trend.includes('Rising') ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
                              color: alert.trend.includes('Rising') ? 'var(--red)' : 'var(--green)',
                              borderColor: alert.trend.includes('Rising') ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'
                            }}>{alert.trend}</span>
                          )}
                          <span className="acn-level" style={{ color, background: `${rawColor}10`, borderColor: `${rawColor}30` }}>{alert.risk_level}</span>
                        </div>
                        <div className="acn-meta">
                          <span><CloudRain size={11} />{alert.total_rain_72h}mm / 72h</span>
                          <span><TrendingUp size={11} />{alert.forecast_24h}mm forecast</span>
                          <span style={{ color: 'var(--blue)' }}><Satellite size={11} />SAR: {alert.sar_validation}</span>
                        </div>
                        <div className="acn-action">
                          <span>{alert.action}</span>
                        </div>

                        {/* Escalation Intelligence */}
                        {alert.escalation_status === "DISPATCHED" && (
                          <div className="acn-escalation">
                            <div className="escalation-header">
                              <Mail size={12} />
                              <span>Emergency Dispatch: {alert.escalation_status}</span>
                            </div>
                            <div className="escalation-authorities">
                              <Users size={11} />
                              <span>Authorities: {alert.authorities_notified?.join(", ")}</span>
                            </div>
                          </div>
                        )}

                        {/* Recommended Safe Zones */}
                        {alert.top_recommendations?.length > 0 && (
                          <div className="acn-safe-zones">
                            <div className="sz-header">TOP EVACUATION SAFE ZONES</div>
                            <div className="sz-list">
                              {alert.top_recommendations.map(sz => (
                                <div key={sz.id} className="sz-mini-card">
                                  <div className="sz-mini-top">
                                    <span className="sz-name"><Home size={10} />{sz.name}</span>
                                    <span className="sz-score">{sz.safety_score}% SAFE</span>
                                  </div>
                                  <div className="sz-mini-meta">
                                    <span>Elev: {sz.elevation_m}m</span>
                                    <span>•</span>
                                    <span>{sz.risk_state}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Chart + Probability */}
                      <div className="acn-right">
                        <div className="acn-chart">
                          <ResponsiveContainer width="100%" height={52}>
                            <AreaChart data={alert.history} margin={{ top: 2, right: 2, left: 2, bottom: 0 }}>
                              <defs>
                                <linearGradient id={`ag-${alert.city}`} x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor={rawColor} stopOpacity={0.3} />
                                  <stop offset="95%" stopColor={rawColor} stopOpacity={0} />
                                </linearGradient>
                              </defs>
                              <Area type="monotone" dataKey="prob" stroke={rawColor} strokeWidth={1.5} fill={`url(#ag-${alert.city})`} isAnimationActive={false} dot={false} />
                            </AreaChart>
                          </ResponsiveContainer>
                          <div className="acn-chart-label">5-Day Trend</div>
                        </div>
                        <div className="acn-prob" style={{ color }}>
                          <span className="acn-prob-val">{alert.probability}%</span>
                          <span className="acn-prob-label">Flood Risk</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ══ GAN SIMULATOR ══ */}
          {tab === 'simulator' && <SimulatorTab />}

          {/* ══ FLOOD MAP TAB ══ */}
          {tab === 'map' && (
            <FloodMap targetCity={targetCity} setTargetCity={setTargetCity} />
          )}

          {/* ══ PLACEHOLDER TABS ══ */}
          {tab === 'pipeline' && (
            <div className="coming-soon-page">
              <div className="coming-soon-card">
                <div className="cs-badge">COMING SOON</div>
                <div className="cs-icon">
                  <Database size={48} />
                </div>
                <div className="cs-title">Data Pipeline Manager</div>
                <div className="cs-desc">
                  Monitor ETL workflows, manage data ingestion schedules, and track processing status across all pipeline modules.
                </div>
                <div className="cs-features">
                  {['Automated scheduling', 'Error monitoring', 'Data validation'].map(f => (
                    <span key={f} className="cs-feature-tag">{f}</span>
                  ))}
                </div>
                <div className="cs-version">Expected in v3.0 Release</div>
              </div>
            </div>
          )}

        </main>
      </div>


      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(null)}>
          <div className="lightbox-box" onClick={e => e.stopPropagation()}>
            <button className="lb-close" onClick={() => setLightbox(null)}><X size={16} /></button>
            <button className="lb-nav lb-prev" disabled={lightbox.index === 0} onClick={() => setLightbox(l => ({ ...l, index: l.index - 1 }))}><ChevronLeft size={22} /></button>
            <img className="lb-img" src={`${API}/plots/image?file=${encodeURIComponent(lightbox.list[lightbox.index].file)}`} alt={lightbox.list[lightbox.index].title} />
            <button className="lb-nav lb-next" disabled={lightbox.index === lightbox.list.length - 1} onClick={() => setLightbox(l => ({ ...l, index: l.index + 1 }))}><ChevronRight size={22} /></button>
            <div className="lb-caption">
              <span>{lightbox.list[lightbox.index].title}</span>
              <span className="lb-counter">{lightbox.index + 1} / {lightbox.list.length}</span>
            </div>
          </div>
        </div>
      )}

      {/* AI Assistant Sidebar Component */}
      <ChatbotPanel targetCity={targetCity} />

    </div>
  );
}
