import os
import subprocess
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
working_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@router.post("/trigger-gee")
def trigger_gee():
    try:
        script_path = os.path.join(working_dir, "notebooks", "04_satellite_imagery_gee.py")
        
        # Determine the correct python executable to use (from virtual environment)
        python_exe = os.path.join(working_dir, ".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = "python" # fallback
            
        result = subprocess.run([python_exe, script_path], cwd=working_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            return JSONResponse({"status": "SUCCESS", "message": "Copernicus Satellite extraction synchronized and completed locally!"})
        else:
            return JSONResponse({"status": "ERROR", "message": result.stderr or result.stdout}, status_code=500)
            
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

import glob
import base64

@router.get("/sar-feed/{city}")
def get_city_sar(city: str):
    city = city.lower()
    raw_dir = os.path.join(working_dir, "data", "raw", city)
    tifs = glob.glob(os.path.join(raw_dir, "*_flood_sar_*.tif"))
    if not tifs:
        return JSONResponse({"status": "ERROR", "message": f"No SAR feed available for {city.upper()}. Try pressing Sync to query Earth Engine space parameters."}, status_code=404)
        
    target = tifs[0] # Grabs the first active satellite hit for this city
    try:
        import rasterio
        import numpy as np
        from PIL import Image
        import io
        
        with rasterio.open(target) as src:
            # Sen1Floods11 requires raw Float32 SAR backscatter (dB)
            img_array = src.read().astype(np.float32)
            
            # Extract metadata
            crs = str(src.crs)
            bounds = src.bounds
            transform = src.transform
            res = src.res
            bands_count = src.count

        # Ensure we have VV and VH (2 bands)
        if bands_count == 2:
            band_names = ["VV", "VH"]
        elif bands_count == 1:
            band_names = ["VV"]
        else:
            band_names = [f"Band_{i}" for i in range(1, bands_count + 1)]

        tensor_shape = img_array.shape # Expected: (Channels, Height, Width)
        
        # Calculate min/max SAR dB values per band
        band_stats = {}
        for i, name in enumerate(band_names):
            band_data = img_array[i]
            band_stats[name] = {
                "min_dB": float(np.nanmin(band_data)),
                "max_dB": float(np.nanmax(band_data)),
                "mean_dB": float(np.nanmean(band_data))
            }

        return {
            "status": "SUCCESS", 
            "filename": os.path.basename(target),
            "tensor_structure": {
                "shape": tensor_shape,
                "dtype": str(img_array.dtype),
                "channels": bands_count,
                "band_ordering": band_names
            },
            "geospatial_metadata": {
                "crs": crs,
                "resolution_x": res[0],
                "resolution_y": res[1],
                "bounds": {"left": bounds.left, "bottom": bounds.bottom, "right": bounds.right, "top": bounds.top}
            },
            "sar_values": band_stats
        }
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

