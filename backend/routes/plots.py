import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLOTS_DIR = os.path.join(BASE_DIR, "outputs", "plots")

@router.get("/plots")
def list_plots():
    result = []
    # Dynamically scan for any image assets in the outputs/plots folder
    for root, _, files in os.walk(PLOTS_DIR):
        for file in files:
            if file.endswith(".png") or file.endswith(".jpg"):
                rel_path = os.path.relpath(os.path.join(root, file), PLOTS_DIR)
                # Use parent folder name as group, or 'Analytics' if in root
                parent = os.path.basename(root)
                group = "Analytics" if parent == "plots" else parent.replace("_", " ").title()
                
                # Format a nice title from the filename
                raw_title = os.path.splitext(file)[0].replace("_", " ").title()
                
                # Special cases for algorithmic models because they are in the root
                if "Xgboost" in raw_title or "Fusion" in raw_title: group = "Predictive Fusion Layer"
                if "Lstm" in raw_title or "Temporal" in raw_title: group = "Temporal Analysis Core"
                
                result.append({
                    "group": group,
                    "title": raw_title,
                    "file": rel_path.replace("\\", "/") # Normalize for web URL
                })
    
    # Sort for consistent UI mapping
    result.sort(key=lambda x: (x["group"], x["title"]))
    return JSONResponse(result)

@router.get("/plots/image")
def get_plot(file: str):
    safe = os.path.normpath(file).lstrip("/\\")
    full = os.path.join(PLOTS_DIR, safe)
    if not full.startswith(PLOTS_DIR) or not os.path.exists(full):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(full, media_type="image/png")
