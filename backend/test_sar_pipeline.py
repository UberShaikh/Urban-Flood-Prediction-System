import os
import numpy as np
import rasterio
from rasterio.transform import from_origin
from services.sar_pipeline import process_sar_geotiff, mock_inference_model

def create_mock_geotiff(path):
    """Creates a mock Sentinel-1 GeoTIFF with VV and VH bands."""
    transform = from_origin(72.8, 19.1, 0.000089831, 0.000089831)
    
    # Create (2, 800, 800) float32 array
    # VV typical range: -30 to 5 dB
    vv = np.random.uniform(-30, 5, (800, 800)).astype(np.float32)
    # VH typical range: -35 to -2 dB
    vh = np.random.uniform(-35, -2, (800, 800)).astype(np.float32)
    
    data = np.stack([vv, vh])
    
    with rasterio.open(
        path, 'w', driver='GTiff',
        height=data.shape[1], width=data.shape[2],
        count=data.shape[0], dtype=data.dtype,
        crs='EPSG:4326', transform=transform
    ) as dst:
        dst.write(data)

def run_validation():
    print("==================================================")
    print("STEP 6 — TEST AND VERIFY API OUTPUT")
    print("==================================================")
    
    test_path = "mock_sar_mumbai.tif"
    create_mock_geotiff(test_path)
    
    print("1. GeoTIFF Validation")
    with rasterio.open(test_path) as src:
        print(f"  CRS: {src.crs}")
        print(f"  Resolution: {src.res}")
        print(f"  Tensor shape: {src.shape}")
        print(f"  Number of bands: {src.count}")
        print(f"  Data type: {src.dtypes[0]}")
    
    print("\n2. Processing Pipeline Validation")
    tensor_pt, meta, tensor_np = process_sar_geotiff(test_path)
    
    print(f"  Final PyTorch Tensor Shape: {tensor_pt.shape}")
    print(f"  Tensor DataType: {tensor_pt.dtype}")
    print(f"  Channels: 2 (VV, VH)")
    
    vv_norm = tensor_np[0]
    vh_norm = tensor_np[1]
    
    print("\n3. SAR Normalization Validation")
    print(f"  VV Min: {vv_norm.min():.4f}, Max: {vv_norm.max():.4f} (Expected 0.0 to 1.0)")
    print(f"  VH Min: {vh_norm.min():.4f}, Max: {vh_norm.max():.4f} (Expected 0.0 to 1.0)")
    
    print("\n4. Architecture Readiness Validation")
    print("  Running Mock Inference...")
    mock_mask = mock_inference_model(tensor_pt)
    print(f"  Mock Flood Mask Shape: {mock_mask.shape}")
    print(f"  Mock Flood Mask Unique Values: {torch.unique(mock_mask).tolist()}")
    
    if tensor_pt.shape == (1, 2, 512, 512) and vv_norm.min() >= 0.0 and vv_norm.max() <= 1.0:
        print("\n=> VALIDATION SUCCESS: Pipeline matches Sen1Floods11 expectations.")
    else:
        print("\n=> VALIDATION FAILED: Pipeline does not match expectations.")

    os.remove(test_path)

if __name__ == "__main__":
    import torch
    run_validation()
