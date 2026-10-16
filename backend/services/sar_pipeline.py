import numpy as np
import rasterio
try:
    import torch
except ImportError:
    torch = None

def process_sar_geotiff(tif_path):
    """
    Complete model-ready SAR preprocessing pipeline.
    GeoTIFF -> Rasterio -> 512x512 Patches -> SAR Normalization -> PyTorch Tensor
    """
    with rasterio.open(tif_path) as src:
        # 1. Read raw Float32 SAR tensor
        img_array = src.read().astype(np.float32)
        
        # Handle cases where GEE only returned VV (missing VH)
        vv_raw = img_array[0]
        if img_array.shape[0] >= 2:
            vh_raw = img_array[1]
        else:
            print("WARNING: VH band missing in GeoTIFF. Filling with -35.0 dB fallback.")
            vh_raw = np.full_like(vv_raw, -35.0)
        
        # Extract metadata
        meta = {
            "crs": str(src.crs),
            "transform": src.transform,
            "bounds": src.bounds,
            "res": src.res,
            "shape_original": img_array.shape
        }

    # 2. Extract 512x512 Tile (Center crop with padding if necessary)
    target_size = 512
    h, w = vv_raw.shape
    
    # Calculate crop coordinates
    top = max(0, (h - target_size) // 2)
    left = max(0, (w - target_size) // 2)
    bottom = min(h, top + target_size)
    right = min(w, left + target_size)
    
    vv_crop = vv_raw[top:bottom, left:right]
    vh_crop = vh_raw[top:bottom, left:right]
    
    # Pad to 512x512 if the original image was smaller than 512x512
    pad_h = target_size - vv_crop.shape[0]
    pad_w = target_size - vv_crop.shape[1]
    
    if pad_h > 0 or pad_w > 0:
        vv_crop = np.pad(vv_crop, ((0, pad_h), (0, pad_w)), mode='constant', constant_values=-30.0)
        vh_crop = np.pad(vh_crop, ((0, pad_h), (0, pad_w)), mode='constant', constant_values=-35.0)

    # 3. SAR Normalization (Sen1Floods11 Standard)
    # VV: clip [-30, 0] -> normalize (VV + 30) / 30
    vv_norm = np.clip(vv_crop, -30.0, 0.0)
    vv_norm = (vv_norm + 30.0) / 30.0
    
    # VH: clip [-35, -5] -> normalize (VH + 35) / 30
    vh_norm = np.clip(vh_crop, -35.0, -5.0)
    vh_norm = (vh_norm + 35.0) / 30.0

    # Stack channels back together -> shape: (2, 512, 512)
    sar_tensor_np = np.stack([vv_norm, vh_norm], axis=0)

    # 4. Convert to PyTorch Tensor -> shape: (1, 2, 512, 512)
    if torch is not None:
        sar_tensor_pt = torch.from_numpy(sar_tensor_np).unsqueeze(0)
    else:
        # Fallback for environments without PyTorch installed yet
        sar_tensor_pt = np.expand_dims(sar_tensor_np, axis=0)

    return sar_tensor_pt, meta, sar_tensor_np

def mock_inference_model(tensor):
    """
    Placeholder for future Sen1Floods11 U-Net / DeepLabV3 segmentation model.
    Expects tensor of shape (1, 2, 512, 512).
    Returns binary mask of shape (1, 512, 512).
    """
    assert tensor.shape == (1, 2, 512, 512), f"Expected shape (1, 2, 512, 512), got {tensor.shape}"
    
    # MOCK LOGIC: If VV is very dark (normalized value near 0), it's likely water.
    # threshold at 0.35
    if torch is not None and isinstance(tensor, torch.Tensor):
        vv_channel = tensor[:, 0, :, :]
        mock_mask = (vv_channel < 0.35).float()
    else:
        vv_channel = tensor[:, 0, :, :]
        mock_mask = (vv_channel < 0.35).astype(np.float32)
    return mock_mask

def generate_visual_overlay(binary_mask_tensor):
    """
    Converts binary segmentation mask tensor (1, 512, 512) into a visualization array.
    Returns an RGBA numpy array suitable for frontend map overlays.
    """
    mask_np = binary_mask_tensor.squeeze().cpu().numpy()
    
    # Create RGBA Image (Red overlay for flooded areas)
    rgba = np.zeros((512, 512, 4), dtype=np.uint8)
    rgba[mask_np == 1] = [255, 0, 0, 150] # Red with transparency
    
    return rgba
