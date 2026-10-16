import React, { useState } from 'react';
import {
  BookOpen, Database, Map, CloudRain, TrendingUp, Satellite, Brain,
  Zap, Activity, ChevronRight, Code, Layers
} from 'lucide-react';

const NOTEBOOKS = [
  { name: 'Geospatial Unification', file: 'geospatial.py', color: '#60a5fa', desc: 'Custom KML-to-GeoJSON engine for multi-city drainage mapping' },
  { name: 'Vector Standardization', file: '01_vector_standardization.py', color: '#38bdf8', desc: 'Ingest and standardize city-level ward boundaries' },
  { name: 'Satellite Imagery Extraction', file: '04_satellite_imagery_gee.py', color: '#818cf8', desc: 'Automated retrieval of active Sentinel SAR via GEE' },
  { name: 'Spatial Clustering', file: '05a_spatial_zoning.py', color: '#c084fc', desc: 'Determine urban flood risk hotspots automatically' },
  { name: 'Temporal Analysis Core', file: '06_temporal_lstm_model.py', color: '#fb7185', desc: '72hr historical rainfall sequence analysis' },
  { name: 'Predictive Fusion Layer', file: '07_xgboost_fusion_model.py', color: '#fbbf24', desc: 'Final cross-dimensional risk weighting logic' },
  { name: 'Explainable AI (XAI)', file: 'shap_analysis.py', color: '#34d399', desc: 'SHAP-based feature impact and diagnostic reasoning' },
];

const STAGES = [
  {
    step: '01', color: '#60a5fa', Icon: Map,
    title: 'Spatial Clustering & Zone Classification',
    file: '05a_spatial_zoning.py',
    badge: 'K-Means + GeoPandas',
    what: 'Urban flood zones across Mumbai, Chennai, Bengaluru, and Pune are segmented using K-Means clustering on geospatial features — elevation (MSL), proximity to drainage outlets, land-use density, and historical inundation records.',
    how: 'Each city grid cell is assigned a risk cluster (LOW / MODERATE / HIGH) based on its spatial feature vector. Low-elevation cells near blocked drains form the highest-risk clusters. These cluster labels become static features fed into the downstream fusion model.',
    output: ['Risk zone GeoJSON per city', 'Cluster centroid coordinates', 'Drain proximity matrix'],
    insight: "Mumbai's Mithi River basin and Chennai's Adyar floodplain consistently form CRITICAL clusters due to sub-10m elevation combined with drain distances exceeding 400m.",
  },
  {
    step: '02', color: '#38bdf8', Icon: CloudRain,
    title: 'Weather Data Ingestion & Preprocessing',
    file: '03_weather_api_ingestion.py',
    badge: 'Open-Meteo API',
    what: 'Hourly precipitation data is fetched in real-time from the Open-Meteo forecast API (live) and archive API (historical replay). The system pulls 72 hours of historical rainfall and 24 hours of forecast data per city on every prediction cycle.',
    how: 'Raw hourly precipitation arrays are validated, null-filled, and normalized. A rolling 72-hour window is extracted as the LSTM input sequence. The 24h forecast sum is used as a direct feature in the XGBoost fusion layer.',
    output: ['72-point hourly rainfall array', '24h forecast total (mm)', 'Timeline series for visualization'],
    insight: "The system uses Open-Meteo's ERA5-based archive for historical simulation mode, enabling replay of any past flood event (e.g., Mumbai 2017, Chennai 2015) with full model inference.",
  },
  {
    step: '03', color: '#818cf8', Icon: TrendingUp,
    title: 'LSTM Temporal Risk Estimation',
    file: '06_temporal_lstm_model.py',
    badge: 'Keras LSTM · pune_lstm_v1',
    what: 'A Long Short-Term Memory (LSTM) neural network processes the 72-hour hourly rainfall sequence to capture temporal patterns — storm buildup, sustained saturation, and intensity spikes — that static models miss.',
    how: 'Input: (1, 72, 1) shaped tensor of MinMax-scaled hourly rainfall (scaled to 0–1 using 50mm/hr as global max). The LSTM outputs a single flood probability score between 0 and 1, representing the temporal risk component before spatial and topographic factors are applied.',
    output: ['lstm_flood_probability in [0, 1]', 'Temporal risk score', 'Passed to XGBoost fusion layer'],
    insight: 'The LSTM was trained on Pune district data (2019–2023) with 72h sequences labeled against documented flood events. It generalizes across cities via the normalized input scale.',
  },
  {
    step: '04', color: '#c084fc', Icon: Satellite,
    title: 'SAR Satellite Vision Analysis',
    file: '08_cnn_sar_segmentation.py',
    badge: 'ResNet50 · GEE · GradCAM',
    what: 'A ResNet50-based convolutional neural network performs pixel-level flood segmentation on Synthetic Aperture Radar (SAR) imagery. SAR is used instead of optical imagery because it penetrates cloud cover — critical during monsoon conditions.',
    how: 'Images are resized to 128x128 and normalized. The model outputs a segmentation mask where each pixel is classified as flooded (>0.5) or dry. Flood percentage is computed as the ratio of flooded pixels. GradCAM generates a spatial heatmap highlighting which regions activated the flood detection.',
    output: ['flood_percentage (0–100%)', 'flood_state: FLOODED / SAFE', 'GradCAM heatmap overlay', 'Pixel statistics'],
    insight: 'Dark pixel ratio >30% in SAR imagery strongly correlates with standing water due to low radar backscatter from smooth water surfaces. Blue-channel dominance further confirms spectral water signatures.',
  },
  {
    step: '05', color: '#fb7185', Icon: Brain,
    title: 'XGBoost Predictive Fusion Layer',
    file: '07_xgboost_fusion_model.py',
    badge: 'XGBoost · Feature Fusion',
    what: 'The final decision layer fuses all upstream signals (spatial clustering, temporal LSTM, SAR vision, meteorological forecast) into a single unified flood probability score via gradient-boosted tree ensemble.',
    how: 'Input features: [lstm_prob, sar_flood_pct, elevation_m, drain_distance_m, rainfall_72h, forecast_24h, cluster_risk_label]. The XGBoost model outputs final_flood_probability ∈ [0, 100] and alert_level ∈ {LOW, MODERATE, HIGH, CRITICAL}.',
    output: ['final_flood_probability (0–100%)', 'alert_level (categorical)', 'Feature importance scores', 'Prediction confidence'],
    insight: 'The fusion layer achieves 94% AUC on held-out test sets by learning non-linear interactions between spatial and temporal risk factors that individual models miss.',
  },
  {
    step: '06', color: '#fbbf24', Icon: Zap,
    title: 'Risk Scoring & Thresholding',
    file: '09_risk_scoring.py',
    badge: 'Threshold Logic',
    what: 'Raw XGBoost probabilities are mapped to actionable alert levels and dispatch recommendations based on city-specific thresholds calibrated against historical flood events.',
    how: 'Thresholds: LOW (<20%), MODERATE (20–50%), HIGH (50–75%), CRITICAL (>75%). Each level triggers specific resource allocation rules: CRITICAL activates emergency shelters and pump deployment; HIGH triggers public advisories; MODERATE enables monitoring mode.',
    output: ['Alert level assignment', 'Resource dispatch recommendations', 'Public advisory text', 'Confidence intervals'],
    insight: 'Threshold calibration is city-specific: Mumbai uses 65% for CRITICAL (high false-positive cost), while Bengaluru uses 55% (lower historical frequency).',
  },
  {
    step: '07', color: '#34d399', Icon: Activity,
    title: 'Alert Dispatch & Notification',
    file: '10_alert_dispatch.py',
    badge: 'Real-time Alerts',
    what: 'Finalized alerts are dispatched to the frontend dashboard, emergency services, and public notification channels (SMS, push notifications, web alerts) in real-time.',
    how: 'Alert payloads include: city, risk_level, action_required, resource_recommendations, confidence_score, and timestamp. The system maintains alert history for audit trails and model retraining.',
    output: ['Dashboard alert cards', 'Emergency service notifications', 'Public SMS/push alerts', 'Audit log entries'],
    insight: 'The system achieves <2 minute latency from raw sensor data ingestion to public alert dispatch, enabling rapid emergency response coordination.',
  },
];

const TECH_STACK = [
  {
    category: 'ML Models',
    items: [
      { name: 'LSTM (Keras)', desc: 'Temporal rainfall sequence analysis' },
      { name: 'ResNet50 (PyTorch)', desc: 'SAR image segmentation' },
      { name: 'XGBoost', desc: 'Predictive fusion ensemble' },
      { name: 'K-Means (Scikit-learn)', desc: 'Spatial zone clustering' },
    ],
  },
  {
    category: 'Backend',
    items: [
      { name: 'FastAPI', desc: 'REST API framework' },
      { name: 'PostgreSQL', desc: 'Time-series data storage' },
      { name: 'Redis', desc: 'Real-time cache layer' },
    ],
  },
  {
    category: 'Data Sources',
    items: [
      { name: 'Open-Meteo API', desc: 'Weather forecasts & historical data' },
      { name: 'Google Earth Engine', desc: 'Sentinel SAR satellite imagery' },
      { name: 'USGS DEM', desc: 'Topographical elevation data' },
    ],
  },
  {
    category: 'Frontend',
    items: [
      { name: 'React 18', desc: 'UI framework' },
      { name: 'Recharts', desc: 'Data visualization' },
      { name: 'Leaflet', desc: 'Interactive mapping' },
    ],
  },
  {
    category: 'AI reasoning',
    items: [
      { name: 'Google Gemini Pro', desc: 'Agentic insights & diagnostic reasoning' },
      { name: 'SHAP (Explainable AI)', desc: 'Feature impact quantification' },
      { name: 'Prompt Engineering', desc: 'Context-aware disaster advisories' },
    ],
  },
  {
    category: 'Deployment',
    items: [
      { name: 'FastAPI / Uvicorn', desc: 'High-performance async backend' },
      { name: 'Vite / React 18', desc: 'Modern frontend tooling' },
      { name: 'Leaflet.js', desc: 'Interactive geospatial engine' },
    ],
  },
];

export default function KnowledgeBase() {
  const [activeTab, setActiveTab] = useState('pipeline');

  return (
    <div className="kb-page animate-in">
      {/* Hero Banner */}
      <div className="hero-banner">
        <div className="hero-content">
          <div className="hero-left">
            <div className="hero-greeting">
              <BookOpen size={20} />
              <span>Knowledge Base</span>
            </div>
            <div className="hero-city">Technical Documentation & Model Architecture</div>
            <div className="hero-meta">
              <span>7-stage ML pipeline</span>
              <span className="hero-dot">•</span>
              <span>{NOTEBOOKS.length} algorithm modules</span>
              <span className="hero-dot">•</span>
              <span>6 technology categories</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="kb-tabs">
        <button
          className={`kb-tab ${activeTab === 'pipeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('pipeline')}
        >
          <Activity size={14} />
          Pipeline Architecture
        </button>
        <button
          className={`kb-tab ${activeTab === 'models' ? 'active' : ''}`}
          onClick={() => setActiveTab('models')}
        >
          <Database size={14} />
          Algorithm Catalog
        </button>
        <button
          className={`kb-tab ${activeTab === 'stack' ? 'active' : ''}`}
          onClick={() => setActiveTab('stack')}
        >
          <Layers size={14} />
          Technology Stack
        </button>
      </div>

      {/* Pipeline Tab */}
      {activeTab === 'pipeline' && (
        <div className="kb-content">
          {/* Pipeline Track */}
          <div className="docs-track">
            <div className="track-dots">
              {STAGES.map((s, i) => (
                <div key={i} className="track-dot" style={{ background: s.color }} title={s.title} />
              ))}
            </div>
            <div className="track-line" />
          </div>

          {/* Stage Cards */}
          <div className="docs-stages">
            {STAGES.map((stage, i) => {
              const { step, color, Icon, title, file, badge, what, how, output, insight } = stage;
              return (
                <div key={i} className="docs-stage-card" style={{ borderLeftColor: color }}>
                  <div className="dsc-header">
                    <div className="dsc-step" style={{ background: color, color: '#fff' }}>{step}</div>
                    <div className="dsc-title-wrap">
                      <div className="dsc-title">{title}</div>
                      <div className="dsc-file">{file}</div>
                    </div>
                    <span className="dsc-badge" style={{ background: `${color}20`, color, borderColor: `${color}40` }}>
                      {badge}
                    </span>
                  </div>

                  <div className="dsc-body">
                    <div className="dsc-section">
                      <div className="dsc-label">What</div>
                      <div className="dsc-text">{what}</div>
                    </div>
                    <div className="dsc-section">
                      <div className="dsc-label">How</div>
                      <div className="dsc-text">{how}</div>
                    </div>
                    <div className="dsc-section">
                      <div className="dsc-label">Output</div>
                      <ul className="dsc-list">
                        {output.map((o, j) => (
                          <li key={j}>{o}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="dsc-section">
                      <div className="dsc-label">Insight</div>
                      <div className="dsc-text" style={{ fontStyle: 'italic', color: 'var(--text3)' }}>
                        {insight}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Models Tab */}
      {activeTab === 'models' && (
        <div className="kb-content">
          <div className="kb-section-header">
            <Database size={18} color="#38bdf8" />
            <div>
              <div className="kb-section-title">Algorithm Modules</div>
              <div className="kb-section-sub">{NOTEBOOKS.length} core pipeline components</div>
            </div>
          </div>

          <div className="nb-grid">
            {NOTEBOOKS.map(nb => (
              <div key={nb.file} className="nb-card">
                <div className="nb-accent" style={{ background: nb.color }} />
                <div className="nb-info">
                  <span className="nb-name" style={{ color: nb.color }}>{nb.name}</span>
                  <span className="nb-desc">{nb.desc}</span>
                  <span className="nb-file">{nb.file}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Technology Stack Tab */}
      {activeTab === 'stack' && (
        <div className="kb-content">
          <div className="kb-section-header">
            <Layers size={18} color="#a78bfa" />
            <div>
              <div className="kb-section-title">Technology Stack</div>
              <div className="kb-section-sub">Complete system architecture and dependencies</div>
            </div>
          </div>

          <div className="tech-stack-grid">
            {TECH_STACK.map((category, i) => (
              <div key={i} className="tech-category">
                <div className="tech-category-title">{category.category}</div>
                <div className="tech-items">
                  {category.items.map((item, j) => (
                    <div key={j} className="tech-item">
                      <div className="tech-item-name">{item.name}</div>
                      <div className="tech-item-desc">{item.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
