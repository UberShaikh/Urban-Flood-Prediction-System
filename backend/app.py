import os
import sys

# ── Windows DLL fix: register torch/lib before any imports ──────────────────
# This must happen at the very top before torch is imported anywhere.
try:
    import importlib.util as _ilu
    _ts = _ilu.find_spec("torch")
    if _ts:
        _tlib = os.path.join(os.path.dirname(_ts.origin), "lib")
        if os.path.isdir(_tlib) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_tlib)
except Exception:
    pass
# ────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import vision, predict, plots, gee, live, metrics, alerts, agent, simulate, safe_zones, geospatial
import uvicorn

app = FastAPI(
    title="AquaAlert — Urban Flood Detection API",
    description="Real-time flood risk intelligence using XGBoost, LSTM, and ResNet50 SAR vision.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router,  prefix="/api/v1")
app.include_router(plots.router,    prefix="/api/v1")
app.include_router(gee.router,      prefix="/api/v1")
app.include_router(live.router,     prefix="/api/v1")
app.include_router(metrics.router,  prefix="/api/v1")
app.include_router(alerts.router,   prefix="/api/v1")
app.include_router(agent.router,    prefix="/api/v1")
app.include_router(simulate.router, prefix="/api/v1")
app.include_router(vision.router,      prefix="/api/v1")
app.include_router(safe_zones.router,  prefix="/api/v1")
app.include_router(geospatial.router,  prefix="/api/v1")

@app.get("/")
def health_check():
    return {"status": "ONLINE", "version": "2.0.0", "description": "AquaAlert Flood Risk API — Port 8001"}

@app.get("/api/v1/health")
def api_health():
    return {"status": "ONLINE"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
