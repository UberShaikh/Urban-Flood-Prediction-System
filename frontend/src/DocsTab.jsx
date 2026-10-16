import {
  BookOpen, Map, CloudRain, TrendingUp, Satellite, Brain,
  ShieldAlert, Bell, Database, Eye, Activity, Zap
} from 'lucide-react';

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
    badge: 'XGBoost · 3-Class · SHAP',
    what: "The final prediction is made by an XGBoost classifier that fuses three heterogeneous signals: the LSTM temporal risk score, the city's mean sea level elevation, and the nearest drain distance. This cross-dimensional fusion is the core innovation of the pipeline.",
    how: 'Input vector: [lstm_prob, elevation_m, drain_distance_m]. XGBoost outputs a 3-class probability distribution: LOW (0), MODERATE (1), HIGH (2). A weighted score is computed: P(MODERATE)x50 + P(HIGH)x100. A safety override escalates to HIGH if 24h forecast exceeds elevation-adjusted thresholds.',
    output: ['flood_probability (0–100%)', 'prediction_status label', 'recommended_action', 'SHAP feature importances'],
    insight: 'SHAP analysis consistently shows Temporal Risk Score as the dominant feature (~60% importance), followed by Elevation (~25%) and Drain Distance (~15%). Low-elevation cities like Mumbai and Chennai are disproportionately sensitive to the LSTM score.',
  },
  {
    step: '06', color: '#fbbf24', Icon: ShieldAlert,
    title: 'Risk Scoring & Alert Classification',
    file: 'backend/routes/predict.py',
    badge: 'Elevation-Aware Heuristics',
    what: 'A vulnerability-aware safety override layer adjusts risk thresholds based on city elevation. Cities below 50m MSL (Mumbai: 14m, Chennai: 6m) use tighter thresholds — a 24h forecast of just 66mm triggers HIGH RISK, versus 100mm for higher-elevation cities.',
    how: 'vulnerability_factor = 1.5 for elevation <50m, 1.2 for <200m, 1.0 otherwise. Thresholds are divided by this factor. Final status maps to: LOW RISK — SAFE / MODERATE RISK — MONITOR / HIGH RISK — DANGER with corresponding recommended actions.',
    output: ['final_alert_level string', 'recommended_action text', 'flood_probability clamped 0–100'],
    insight: 'This heuristic layer acts as a physical safety net — even if the ML models underestimate risk during extreme events, the elevation-aware override ensures coastal cities are never under-alerted.',
  },
  {
    step: '07', color: '#34d399', Icon: Bell,
    title: 'Multi-City Alert Dispatch & AI Agent',
    file: 'routes/alerts.py + agent.py',
    badge: 'Gemini 1.5 Flash · Agentic',
    what: 'The alerts engine runs the full prediction pipeline for all 4 cities in parallel, aggregates results, and classifies each into CRITICAL / WARNING / SAFE. The AI Technical Dispatcher (powered by Gemini 1.5 Flash) provides natural language explanations of any risk scenario.',
    how: "Each city's live weather data is fetched, prediction is run, and a 5-day simulated risk history is generated. The Gemini agent uses automatic function calling to invoke get_risk_data() as a tool, fetching live telemetry before answering queries. Falls back to a rule-based safe mode if no API key is configured.",
    output: ['alerts[] with probability + trend', 'SAR validation status', 'summary counts (critical/warning/safe)', 'AI natural language explanation'],
    insight: 'The agentic AI can answer questions like "What was the flood risk in Chennai on 2015-12-01?" by calling the archive API as a tool and running inference on historical data — full temporal reasoning over any past date.',
  },
];

const TECH = [
  { cat: 'ML Models',    color: '#818cf8', items: ['XGBoost 2.1', 'Keras LSTM', 'ResNet50 CNN', 'SHAP XAI'] },
  { cat: 'Backend',      color: '#38bdf8', items: ['FastAPI', 'Python 3.12', 'TensorFlow', 'Uvicorn'] },
  { cat: 'Data Sources', color: '#34d399', items: ['Open-Meteo API', 'Google Earth Engine', 'ERA5 Archive', 'Sentinel SAR'] },
  { cat: 'Frontend',     color: '#f59e0b', items: ['React 18', 'Vite', 'Recharts', 'Lucide Icons'] },
  { cat: 'AI Agent',     color: '#c084fc', items: ['Gemini 1.5 Flash', 'Function Calling', 'Safe Mode Fallback'] },
  { cat: 'Deployment',   color: '#fb7185', items: ['Render.com', 'Docker-ready', 'CORS secured', 'REST API v1'] },
];

export default function DocsTab() {
  return (
    <div className="docs-page">

      {/* Hero */}
      <div className="hero-banner docs-hero">
        <div className="hero-content">
          <div className="hero-left">
            <div className="hero-greeting"><BookOpen size={20} /><span>Technical Documentation</span></div>
            <div className="hero-city">AquaAlert Pipeline Architecture</div>
            <div className="hero-meta">
              <span>7 pipeline stages</span>
              <span className="hero-dot">•</span>
              <span>3 AI models</span>
              <span className="hero-dot">•</span>
              <span>4 Indian cities</span>
              <span className="hero-dot">•</span>
              <span>Real-time inference</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Track */}
      <div className="docs-pipeline-track">
        {STAGES.map((s, i) => (
          <div key={s.step} className="dpt-item">
            <div className="dpt-dot" style={{ background: s.color, boxShadow: `0 0 14px ${s.color}60` }}>
              {s.step}
            </div>
            <div className="dpt-label" style={{ color: s.color }}>{s.title.split(' ')[0]}</div>
            {i < STAGES.length - 1 && <div className="dpt-line" />}
          </div>
        ))}
      </div>

      {/* Stage Cards */}
      {STAGES.map(stage => (
        <div key={stage.step} className="docs-stage-card" style={{ '--sc': stage.color }}>
          <div className="dsc-header">
            <div className="dsc-step" style={{ color: stage.color, background: `${stage.color}12`, border: `1px solid ${stage.color}30` }}>
              STAGE {stage.step}
            </div>
            <div className="dsc-icon" style={{ background: `${stage.color}12`, border: `1px solid ${stage.color}25` }}>
              <stage.Icon size={16} color={stage.color} />
            </div>
            <div className="dsc-title">{stage.title}</div>
            <span className="dsc-badge" style={{ color: stage.color, background: `${stage.color}10`, borderColor: `${stage.color}30` }}>
              {stage.badge}
            </span>
            <code className="dsc-file">{stage.file}</code>
          </div>

          <div className="dsc-body">
            <div className="dsc-row">
              <div className="dsc-section">
                <div className="dsc-section-label"><Eye size={11} />What it does</div>
                <p className="dsc-text">{stage.what}</p>
              </div>
              <div className="dsc-section">
                <div className="dsc-section-label"><Activity size={11} />How it works</div>
                <p className="dsc-text">{stage.how}</p>
              </div>
            </div>

            <div className="dsc-section">
              <div className="dsc-section-label"><Zap size={11} />Outputs</div>
              <div className="dsc-output">
                {stage.output.map(o => (
                  <span key={o} className="dsc-output-tag" style={{ color: stage.color, background: `${stage.color}08`, borderColor: `${stage.color}25` }}>
                    {o}
                  </span>
                ))}
              </div>
            </div>

            <div className="dsc-insight" style={{ borderLeftColor: stage.color }}>
              <Brain size={12} color={stage.color} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{stage.insight}</span>
            </div>
          </div>
        </div>
      ))}

      {/* Tech Stack */}
      <div className="docs-tech-section">
        <div className="docs-section-heading">
          <Database size={16} color="var(--blue)" />
          <span>Technology Stack</span>
        </div>
        <div className="docs-tech-grid">
          {TECH.map(t => (
            <div key={t.cat} className="docs-tech-card" style={{ '--tc': t.color }}>
              <div className="dtc-cat" style={{ color: t.color }}>{t.cat}</div>
              <div className="dtc-items">
                {t.items.map(item => (
                  <span key={item} className="dtc-tag" style={{ borderColor: `${t.color}25`, background: `${t.color}08`, color: 'var(--text2)' }}>
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
