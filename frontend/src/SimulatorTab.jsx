import { useState, useCallback } from 'react';
import axios from 'axios';
import {
  Zap, CloudRain, ShieldAlert, AlertTriangle, CheckCircle,
  Brain, Activity, TrendingUp, Radio, BarChart2, Layers
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar
} from 'recharts';

const API = 'http://localhost:8001/api/v1';

const SCENARIOS = [
  { id: 'custom',        label: 'Custom',           icon: Zap,           color: '#38bdf8', desc: 'Set your own intensity multiplier' },
  { id: 'monsoon_surge', label: 'Monsoon Surge',    icon: CloudRain,     color: '#3b82f6', desc: '1.8x — Heavy sustained monsoon rainfall' },
  { id: 'cyclone',       label: 'Cyclonic Storm',   icon: AlertTriangle, color: '#f59e0b', desc: '3.5x — Cyclonic depression landfall' },
  { id: 'cloudburst',    label: 'Urban Cloudburst', icon: ShieldAlert,   color: '#ef4444', desc: '5.0x — Extreme localized cloudburst' },
];

const CITIES = ['mumbai', 'chennai', 'bengaluru', 'pune'];

const statusColor = s => {
  if (!s) return '#64748b';
  const u = s.toUpperCase();
  if (u.includes('LOW') || u.includes('SAFE')) return '#10b981';
  if (u.includes('MODERATE') || u.includes('MONITOR')) return '#f59e0b';
  if (u.includes('HIGH') || u.includes('DANGER') || u.includes('CRITICAL')) return '#ef4444';
  return '#f59e0b';
};

const SimTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 8, padding: '8px 12px', fontSize: '.7rem' }}>
      <div style={{ color: 'var(--muted2)', marginBottom: 4 }}>Hour {label}</div>
      <div style={{ color: '#ef4444', fontWeight: 700, fontFamily: 'JetBrains Mono' }}>{payload[0]?.value?.toFixed(1)} mm/h</div>
    </div>
  );
};

export default function SimulatorTab() {
  const [city, setCity] = useState('mumbai');
  const [scenario, setScenario] = useState('monsoon_surge');
  const [intensity, setIntensity] = useState(2.0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ganStatus, setGanStatus] = useState(null);
  const [training, setTraining] = useState(false);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setResult(null);
    try {
      const r = await axios.post(`${API}/simulate`, {
        city, scenario,
        intensity: scenario === 'custom' ? intensity : undefined,
        seed: Math.floor(Math.random() * 9999)
      });
      setResult(r.data);
    } catch (e) {
      setResult({ status: 'ERROR', message: e?.response?.data?.detail || e.message });
    }
    setLoading(false);
  }, [city, scenario, intensity]);

  const checkGanStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/simulate/status`);
      setGanStatus(r.data);
    } catch (error) {
      console.error('Failed to load GAN status', error);
    }
  }, []);

  const triggerTraining = useCallback(async () => {
    setTraining(true);
    try {
      await axios.post(`${API}/simulate/train`);
      setTimeout(checkGanStatus, 2000);
    } catch (error) {
      console.error('Failed to trigger GAN training', error);
    }
    setTimeout(() => setTraining(false), 3000);
  }, [checkGanStatus]);

  const selectedScenario = SCENARIOS.find(s => s.id === scenario);
  const floodColor = result ? statusColor(result.prediction?.alert_level) : '#64748b';
  const riskDeltaColor = result?.comparison?.risk_delta > 20 ? '#ef4444' : result?.comparison?.risk_delta > 10 ? '#f59e0b' : '#10b981';

  return (
    <div className="sim-page">

      {/* Hero */}
      <div className="hero-banner sim-hero">
        <div className="hero-content">
          <div className="hero-left">
            <div className="hero-greeting"><Brain size={20} /><span>GAN Scenario Simulator</span></div>
            <div className="hero-city">Extreme Rainfall Stress Testing</div>
            <div className="hero-meta">
              <span>Conditional GAN</span>
              <span className="hero-dot">•</span>
              <span>Physics fallback</span>
              <span className="hero-dot">•</span>
              <span>XGBoost fusion inference</span>
              <span className="hero-dot">•</span>
              <span>4 scenario presets</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginLeft: 'auto' }}>
            <div className={`sim-method-badge ${result?.method === 'GAN' ? 'gan' : 'physics'}`}>
              <span className="dot" />
              {result ? (result.method === 'GAN' ? 'GAN Active' : 'Physics Mode') : 'Ready'}
            </div>
          </div>
        </div>
      </div>

      <div className="sim-layout">
        {/* Left: Controls */}
        <div className="sim-controls">

          {/* City */}
          <div className="sim-section">
            <div className="sim-section-label">Target City</div>
            <select className="city-select" value={city} onChange={e => setCity(e.target.value)}>
              <option value="mumbai">Mumbai Region</option>
              <option value="chennai">Chennai Floodplains</option>
              <option value="bengaluru">Bengaluru Urban</option>
              <option value="pune">Pune District</option>
            </select>
          </div>

          {/* Scenario Presets */}
          <div className="sim-section">
            <div className="sim-section-label">Scenario Preset</div>
            <div className="sim-scenario-grid">
              {SCENARIOS.map(s => (
                <button
                  key={s.id}
                  className={`sim-scenario-btn ${scenario === s.id ? 'active' : ''}`}
                  style={{ '--sc': s.color }}
                  onClick={() => setScenario(s.id)}
                >
                  <s.icon size={14} color={scenario === s.id ? s.color : 'var(--muted2)'} />
                  <span>{s.label}</span>
                </button>
              ))}
            </div>
            <div className="sim-scenario-desc">
              {selectedScenario?.desc}
            </div>
          </div>

          {/* Custom Intensity */}
          {scenario === 'custom' && (
            <div className="sim-section">
              <div className="sim-section-label">Intensity Multiplier: <span style={{ color: '#38bdf8', fontFamily: 'JetBrains Mono' }}>{intensity.toFixed(1)}x</span></div>
              <input
                type="range" min="0.5" max="10" step="0.1"
                value={intensity}
                onChange={e => setIntensity(parseFloat(e.target.value))}
                className="sim-slider"
              />
              <div className="sim-slider-labels">
                <span>0.5x (Dry)</span>
                <span>5x (Extreme)</span>
                <span>10x (Catastrophic)</span>
              </div>
            </div>
          )}

          {/* Run Button */}
          <button className="infer-btn" onClick={runSimulation} disabled={loading} style={{ width: '100%', height: 48 }}>
            {loading ? <><span className="spinner" />Generating Scenario...</> : <><Zap size={15} />Run GAN Simulation</>}
          </button>

          {/* GAN Model Status */}
          <div className="sim-section" style={{ marginTop: 8 }}>
            <div className="sim-section-label">GAN Model Status</div>
            <div className="sim-gan-status-box">
              {ganStatus ? (
                CITIES.map(c => (
                  <div key={c} className="sim-gan-city-row">
                    <span className={`sim-gan-dot ${ganStatus.cities[c]?.model_trained ? 'trained' : 'untrained'}`} />
                    <span style={{ fontSize: '.7rem', color: 'var(--text2)', textTransform: 'capitalize' }}>{c}</span>
                    <span style={{ fontSize: '.62rem', color: 'var(--muted2)', marginLeft: 'auto' }}>
                      {ganStatus.cities[c]?.model_trained ? 'Trained' : 'Physics fallback'}
                    </span>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '.7rem', color: 'var(--muted2)' }}>Click check to load status</div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="infer-btn ghost" onClick={checkGanStatus} style={{ flex: 1, height: 36, fontSize: '.7rem' }}>
                <Radio size={12} /> Check Status
              </button>
              <button className="infer-btn ghost" onClick={triggerTraining} disabled={training} style={{ flex: 1, height: 36, fontSize: '.7rem' }}>
                {training ? <span className="spinner" /> : <Brain size={12} />} Train GAN
              </button>
            </div>
            <div style={{ fontSize: '.6rem', color: 'var(--muted)', marginTop: 6, lineHeight: 1.5 }}>
              Training fetches 3 years of monsoon data per city and trains a conditional LSTM-GAN. Takes ~5 min.
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="sim-results">
          {!result && !loading && (
            <div className="vr-empty" style={{ minHeight: 400 }}>
              <Brain size={40} style={{ color: 'var(--muted)' }} />
              <span>No simulation run yet</span>
              <span className="vr-hint">Select a city and scenario, then click Run GAN Simulation to generate a synthetic extreme rainfall event and see the predicted flood risk.</span>
            </div>
          )}

          {loading && (
            <div className="vr-loading" style={{ minHeight: 400 }}>
              <div className="scan-bar" style={{ width: '60%' }}><div className="scan-fill" /></div>
              <Brain size={20} color="#818cf8" />
              <span style={{ color: '#818cf8' }}>GENERATING SYNTHETIC RAINFALL SEQUENCE...</span>
              <span style={{ fontSize: '.65rem', color: 'var(--muted2)' }}>Conditional GAN inference in progress</span>
            </div>
          )}

          {result && result.status === 'ERROR' && (
            <div className="offline-banner">
              <div className="offline-icon"><AlertTriangle size={28} /></div>
              <div className="offline-text">
                <div className="offline-title">Simulation Failed</div>
                <div className="offline-sub">{result.message}</div>
              </div>
            </div>
          )}

          {result && result.status === 'SUCCESS' && (
            <div className="sim-result-content">

              {/* Header */}
              <div className="sim-result-header">
                <div>
                  <div className="sim-result-city">{result.city} — {result.scenario}</div>
                  <div className="sim-result-meta">
                    <span className={`sim-method-tag ${result.method === 'GAN' ? 'gan' : 'physics'}`}>
                      {result.method === 'GAN' ? 'GAN Generated' : 'Physics Simulated'}
                    </span>
                    <span style={{ fontSize: '.65rem', color: 'var(--muted2)' }}>{result.intensity_factor}x intensity</span>
                  </div>
                </div>
                <div className="sim-risk-badge" style={{ color: floodColor, background: `${floodColor}12`, border: `1px solid ${floodColor}30` }}>
                  <span style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                    {result.prediction.flood_probability}%
                  </span>
                  <span style={{ fontSize: '.55rem', letterSpacing: 1.5, textTransform: 'uppercase', opacity: .7 }}>Flood Risk</span>
                </div>
              </div>

              {/* Risk Comparison */}
              <div className="sim-comparison-row">
                <div className="sim-comp-card">
                  <div className="sim-comp-label">Baseline Risk</div>
                  <div className="sim-comp-val" style={{ color: '#10b981' }}>{result.comparison.baseline_probability}%</div>
                </div>
                <div className="sim-comp-arrow">
                  <TrendingUp size={20} color={riskDeltaColor} />
                  <span style={{ color: riskDeltaColor, fontWeight: 700, fontSize: '.8rem' }}>+{result.comparison.risk_delta}%</span>
                </div>
                <div className="sim-comp-card">
                  <div className="sim-comp-label">Simulated Risk</div>
                  <div className="sim-comp-val" style={{ color: floodColor }}>{result.prediction.flood_probability}%</div>
                </div>
                <div className="sim-comp-card" style={{ borderColor: `${riskDeltaColor}30`, background: `${riskDeltaColor}06` }}>
                  <div className="sim-comp-label">Escalation</div>
                  <div className="sim-comp-val" style={{ color: riskDeltaColor, fontSize: '.85rem' }}>{result.comparison.risk_escalation}</div>
                </div>
              </div>

              {/* Alert */}
              <div className="action-banner" style={{ borderColor: `${floodColor}40`, background: `${floodColor}08` }}>
                <AlertTriangle size={14} color={floodColor} style={{ flexShrink: 0 }} />
                <span style={{ color: 'var(--text2)', fontSize: '.75rem' }}>{result.prediction.recommended_action}</span>
              </div>

              {/* Synthetic Rainfall Chart */}
              <div className="chart-card card-accent-blue" style={{ marginTop: 4 }}>
                <div className="section-header">
                  <div className="section-icon" style={{ background: '#ef444418', border: '1px solid #ef444430' }}>
                    <CloudRain size={14} color="#ef4444" />
                  </div>
                  <span className="section-title">Synthetic 72h Rainfall Sequence</span>
                  <span className="section-badge" style={{ color: '#ef4444', borderColor: '#ef444440', background: '#ef444410' }}>
                    {result.method}
                  </span>
                </div>
                <div className="chart-body">
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={result.timeline} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="simGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="hour" tick={{ fontSize: 9 }} interval={11} label={{ value: 'Hour', position: 'insideBottom', fontSize: 9 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip content={<SimTooltip />} />
                      <ReferenceLine y={10} stroke="#f59e0b" strokeDasharray="4 4" strokeWidth={1} />
                      <ReferenceLine y={25} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1} />
                      <Area type="monotone" dataKey="mm" stroke="#ef4444" strokeWidth={2} fill="url(#simGrad)" dot={false} activeDot={{ r: 4, fill: '#ef4444' }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="sim-stats-grid">
                {[
                  { label: 'Total 72h',       value: `${result.stats.total_72h_mm} mm`,    color: '#ef4444' },
                  { label: 'Baseline 72h',    value: `${result.stats.baseline_72h_mm} mm`, color: '#10b981' },
                  { label: 'Peak Hourly',     value: `${result.stats.peak_hourly_mm} mm/h`,color: '#f59e0b' },
                  { label: 'Hours >10mm',     value: result.stats.hours_above_10mm,         color: '#f59e0b' },
                  { label: 'Hours >25mm',     value: result.stats.hours_above_25mm,         color: '#ef4444' },
                  { label: 'Intensity',       value: `${result.intensity_factor}x`,         color: '#818cf8' },
                ].map(s => (
                  <div key={s.label} className="sim-stat-item">
                    <div className="sim-stat-label">{s.label}</div>
                    <div className="sim-stat-val" style={{ color: s.color }}>{s.value}</div>
                  </div>
                ))}
              </div>

              {/* SHAP */}
              {result.prediction.shap_values?.length > 0 && (
                <div className="shap-section">
                  <div className="shap-title"><Brain size={11} />Feature Impact (Simulated Scenario)</div>
                  {result.prediction.shap_values.map(s => (
                    <div key={s.feature} className="shap-row">
                      <span className="shap-label">{s.feature}</span>
                      <div className="shap-bar-wrap">
                        <div className="shap-bar" style={{ width: `${s.pct}%`, background: floodColor }} />
                      </div>
                      <span className="shap-pct">{s.pct}%</span>
                    </div>
                  ))}
                </div>
              )}

            </div>
          )}
        </div>
      </div>
    </div>
  );
}
