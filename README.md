# AquaAlert: Agentic Flood Intelligence Platform

AquaAlert is a high-performance, clinical-grade diagnostic platform for urban flood detection and risk assessment. It transforms complex geospatial and meteorological data into actionable situational awareness using a multi-model AI fusion pipeline.

---

## 🚀 Vision and Architecture
AquaAlert operates as a **Digital Twin Command Center**, providing real-time monitoring across four major Indian metros: **Mumbai, Bengaluru, Chennai, and Pune**.

- **Hydrological Command Center**: Interactive Leaflet-based geospatial engine with dynamic GeoJSON/KML masking.
- **Multi-Model Fusion**: Integrates temporal (LSTM), spatial (K-Means), and visual (ResNet50 SAR) signals.
- **Explainable AI (XAI)**: Diagnostic insights powered by SHAP (Shapley Additive Explanations) and Gemini Pro reasoning.
- **GAN Simulation**: Historical replay and predictive "What-If" flood scenario generation.

### Core Tech Stack
- **Frontend**: React 18, Leaflet.js, Lucide Icons, Recharts, Framer Motion.
- **Backend**: FastAPI (Python 3.10+), XGBoost, TensorFlow/Keras, Scikit-Learn.
- **Data Engine**: Open-Meteo (Real-time & Archive), Google Earth Engine (SAR Imagery).
- **Geospatial**: Custom KML-to-GeoJSON unification engine for cross-city drainage mapping.

---

## 🛠 Prerequisites
Ensure you have the following installed:
- **Node.js**: v18.0+
- **Python**: v3.9+
- **Google Earth Engine (GEE) Account**: Required for satellite imagery synchronization.

---

## 📥 Quick Start

### 1. Repository Setup
```bash
git clone https://github.com/jagdishbabalsure/Urban-Flood-Prediction-System.git
cd Urban-Flood-Prediction-System
```

### 2. Backend Initialization
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
*Note: Ensure your `.env` file contains a valid `GEMINI_API_KEY` for AI insights.*

### 3. Frontend Initialization
```bash
cd frontend
npm install
npm run dev
```
Access the dashboard at `http://localhost:5173`.

---

## 🔧 Core Modules

### 🗺 Geospatial Intelligence (Command Center)
- **Administrative Masking**: High-fidelity ward-level GeoJSON boundaries.
- **Hydrological Overlay**: Advanced drainage network visualization with vibrant 'Aqua Neon' aesthetics.
- **Data Unification**: Automated handling of disparate city formats (Mumbai GeoJSON vs. BLR/CHN KML).

### 🛰 SAR Vision Pipeline
- **ResNet50 Architecture**: Deep learning segmentation for flood detection in radar imagery.
- **Cloud Penetration**: SAR technology allows for monitoring during heavy monsoon cloud cover.
- **GradCAM Saliency**: Heatmap overlays highlighting specific inundation signatures.

### 🧠 Predictive Fusion
- **Temporal LSTM**: Analyzes 72-hour rainfall sequences for intensity patterns.
- **XGBoost Ensemble**: Final risk scoring (0-100%) incorporating elevation, drain proximity, and forecast data.

---

## 📁 Project Structure
```text
/
├── backend/            # FastAPI orchestration & AI routes
│   ├── routes/         # Geospatial, SAR, and Prediction endpoints
│   └── services/       # GEE integration and ML inference
├── frontend/           # React dashboard & Leaflet mapping
├── Data_Urban/         # City-specific GeoJSON/KML repositories
├── models/             # Pre-trained .h5 and .json ML artifacts
└── notebooks/          # Research, SHAP analysis, and training logs
```

---

## 📜 License
Internal Project - Proprietary Information.
