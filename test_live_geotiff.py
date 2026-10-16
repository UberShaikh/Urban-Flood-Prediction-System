import os
import rasterio
import numpy as np
import sys

# ensure backend is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from backend.services.sar_pipeline import process_sar_geotiff
except ImportError as e:
    print(f"Error importing pipeline: {e}")

def test_real_geotiff():
    tif_path = r"c:\Projects\pa_new\data\raw\mumbai\mumbai_flood_sar_2023-07-01.tif"
    
    print("==================================================")
    print("REAL LIVE GEOTIFF VALIDATION")
    print(f"File: {tif_path}")
    print(f"File size: {os.path.getsize(tif_path) / 1024 / 1024:.2f} MB")
    print("==================================================\n")

    print("STEP 3 — VERIFY RAW SAR VALUES")
    print("------------------------------")
    with rasterio.open(tif_path) as src:
        print(f"CRS: {src.crs}")
        print(f"Resolution (pixel scale): {src.res}")
        print(f"Number of bands: {src.count}")
        print(f"Dtype: {src.dtypes[0]}")
        
        arr = src.read()
        print(f"Tensor shape: {arr.shape}")
        
        for i in range(src.count):
            band = arr[i]
            print(f"\nBand {i} stats:")
            print(f"  Min: {np.nanmin(band):.2f}")
            print(f"  Max: {np.nanmax(band):.2f}")
            print(f"  Mean: {np.nanmean(band):.2f}")

    print("\n==================================================")
    print("STEP 4 — VERIFY PIPELINE COMPATIBILITY")
    print("--------------------------------------")
    try:
        tensor_pt, meta, tensor_np = process_sar_geotiff(tif_path)
        print(f"Final PyTorch Tensor shape: {tensor_pt.shape}")
        print(f"Final Tensor Dtype: {tensor_pt.dtype}")
        
        print(f"\nPost-Normalization Range:")
        print(f"  Channel 0 (VV) Min: {tensor_np[0].min():.4f}, Max: {tensor_np[0].max():.4f}")
        print(f"  Channel 1 (VH) Min: {tensor_np[1].min():.4f}, Max: {tensor_np[1].max():.4f}")
        
        if tensor_pt.shape == (1, 2, 512, 512):
            print("\n=> PIPELINE SUCCESS: 512x512 tensor generated.")
        else:
            print("\n=> PIPELINE FAILURE: Incorrect shape.")
            
    except Exception as e:
        print(f"Pipeline crashed during execution: {e}")

if __name__ == "__main__":
    test_real_geotiff()
