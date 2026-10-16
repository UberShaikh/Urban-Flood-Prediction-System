# -*- coding: utf-8 -*-
"""
AquaAlert - GEE SAR Dataset Builder
=====================================
Downloads 60 Sentinel-1 SAR images per city using Google Earth Engine.

Output:
    data/final_60/
    ├── mumbai/       mumbai_sar_01.tif ... mumbai_sar_60.tif
    ├── pune/         pune_sar_01.tif   ... pune_sar_60.tif
    ├── bangalore/    bangalore_sar_01.tif ... bangalore_sar_60.tif
    ├── chennai/      chennai_sar_01.tif ... chennai_sar_60.tif
    └── metadata.csv

Run:
    .venv\Scripts\python.exe notebooks\build_final60_dataset.py
"""

import ee
import os
import sys
import csv
import time
import zipfile
import io
import hashlib
import requests
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR      = os.path.join(PROJECT_ROOT, "data", "final_60")
META_CSV     = os.path.join(OUT_DIR, "metadata.csv")
PROJECT_ID   = "project-b484fa4f-a5a3-4f84-837"
TARGET_COUNT = 60

# ── City Config ────────────────────────────────────────────────────────────────
# bbox: [lon_min, lat_min, lon_max, lat_max]  (~20x20 km flood-prone core
# flood_seasons: multiple years to collect enough individual scenes
CITIES = {
    "mumbai": {
        "bbox": [72.77, 18.90, 72.97, 19.10],
        "flood_seasons": [
            ("2017-06-01", "2017-09-30"),
            ("2018-06-01", "2018-09-30"),
            ("2019-06-01", "2019-09-30"),
            ("2020-06-01", "2020-09-30"),
            ("2021-06-01", "2021-09-30"),
            ("2022-06-01", "2022-09-30"),
            ("2023-06-01", "2023-09-30"),
            ("2024-06-01", "2024-09-30"),
        ],
    },
    "pune": {
        "bbox": [73.75, 18.45, 73.95, 18.65],
        "flood_seasons": [
            ("2018-06-01", "2018-09-30"),
            ("2019-06-01", "2019-09-30"),
            ("2020-06-01", "2020-09-30"),
            ("2021-06-01", "2021-09-30"),
            ("2022-06-01", "2022-09-30"),
            ("2023-06-01", "2023-09-30"),
            ("2024-06-01", "2024-09-30"),
        ],
    },
    "bangalore": {
        "bbox": [77.50, 12.88, 77.70, 13.08],
        "flood_seasons": [
            ("2019-08-01", "2019-11-30"),
            ("2020-08-01", "2020-11-30"),
            ("2021-08-01", "2021-11-30"),
            ("2022-08-01", "2022-11-30"),
            ("2023-08-01", "2023-11-30"),
            ("2024-08-01", "2024-11-30"),
        ],
    },
    "chennai": {
        "bbox": [80.15, 12.95, 80.35, 13.15],
        "flood_seasons": [
            ("2015-10-01", "2015-12-31"),
            ("2019-10-01", "2019-12-31"),
            ("2020-10-01", "2020-12-31"),
            ("2021-10-01", "2021-12-31"),
            ("2022-10-01", "2022-12-31"),
            ("2023-10-01", "2023-12-31"),
            ("2024-10-01", "2024-12-31"),
        ],
    },
}


# ── GEE Init ───────────────────────────────────────────────────────────────────

def init_gee():
    print("Initializing Google Earth Engine...")
    try:
        ee.Initialize(project=PROJECT_ID)
        print("  [OK] GEE initialized.\n")
    except Exception as e:
        print("  [FAIL] GEE init failed: " + str(e))
        print("  Run: earthengine authenticate")
        sys.exit(1)


# ── Download single EE image ───────────────────────────────────────────────────

def download_image(ee_image, roi, out_path, scale=20):
    """Download one EE image as GeoTIFF. Returns True on success."""
    try:
        url = ee_image.getDownloadURL({
            "scale": scale,
            "crs": "EPSG:4326",
            "region": roi,
            "format": "GEO_TIFF",
            "bands": ["VV", "VH"],
        })
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()

        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                tif_name = next((n for n in z.namelist() if n.endswith(".tif")), z.namelist()[0])
                with open(out_path, "wb") as f:
                    f.write(z.read(tif_name))
        except zipfile.BadZipFile:
            with open(out_path, "wb") as f:
                f.write(resp.content)

        if os.path.getsize(out_path) < 1024:
            os.remove(out_path)
            return False
        return True

    except Exception as e:
        print("      [FAIL] " + str(e)[:120])
        if os.path.exists(out_path):
            os.remove(out_path)
        return False


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()


# ── Extract image metadata ─────────────────────────────────────────────────────

def get_image_meta(ee_image, city, filename):
    try:
        props = ee_image.getInfo()["properties"]
        ts = props.get("system:time_start", 0)
        try:
            date_str = datetime.utcfromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
        except Exception:
            date_str = ""
        return {
            "filename":        filename,
            "city":            city,
            "acquisition_date": date_str,
            "polarization":    "VV+VH",
            "pass_direction":  props.get("orbitProperties_pass", ""),
            "instrument_mode": props.get("instrumentMode", "IW"),
            "relative_orbit":  str(props.get("relativeOrbitNumber_start", "")),
            "platform":        props.get("platform_number", ""),
        }
    except Exception:
        return {
            "filename": filename, "city": city, "acquisition_date": "",
            "polarization": "VV+VH", "pass_direction": "", "instrument_mode": "IW",
            "relative_orbit": "", "platform": "",
        }


# ── Per-city pipeline ──────────────────────────────────────────────────────────

def build_city(city, config, meta_rows):
    city_dir = os.path.join(OUT_DIR, city)
    os.makedirs(city_dir, exist_ok=True)

    roi        = ee.Geometry.Rectangle(config["bbox"])
    collected  = 0
    failed     = 0
    duplicates = 0
    seen_hashes = set()

    print("\n" + "=" * 56)
    print("  CITY: " + city.upper() + "  |  Target: " + str(TARGET_COUNT))
    print("=" * 56)

    for season_start, season_end in config["flood_seasons"]:
        if collected >= TARGET_COUNT:
            break

        print("\n  Season: " + season_start + " -> " + season_end)

        try:
            col = (
                ee.ImageCollection("COPERNICUS/S1_GRD")
                .filterBounds(roi)
                .filterDate(season_start, season_end)
                .filter(ee.Filter.eq("instrumentMode", "IW"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
                .select(["VV", "VH"])
                .sort("system:time_start")
            )

            n = col.size().getInfo()
            print("  Found " + str(n) + " Sentinel-1 scenes")
            if n == 0:
                continue

            # Fetch up to (needed + buffer) images
            needed  = TARGET_COUNT - collected
            img_list = col.toList(min(n, needed + 10))
            list_size = img_list.size().getInfo()

            for i in range(list_size):
                if collected >= TARGET_COUNT:
                    break

                img      = ee.Image(img_list.get(i))
                idx      = collected + 1
                filename = city + "_sar_" + str(idx).zfill(2) + ".tif"
                out_path = os.path.join(city_dir, filename)

                # Already downloaded
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    print("    [" + str(idx).zfill(2) + "] Already exists - skip")
                    h = file_hash(out_path)
                    seen_hashes.add(h)
                    collected += 1
                    meta_rows.append(get_image_meta(img, city, filename))
                    continue

                print("    [" + str(idx).zfill(2) + "] Downloading " + filename + " ...", end=" ")
                sys.stdout.flush()

                ok = download_image(img, roi, out_path, scale=20)
                if not ok:
                    failed += 1
                    print("FAILED")
                    continue

                h = file_hash(out_path)
                if h in seen_hashes:
                    os.remove(out_path)
                    duplicates += 1
                    print("DUPLICATE - removed")
                    continue

                seen_hashes.add(h)
                size_kb = os.path.getsize(out_path) // 1024
                collected += 1
                print("OK  (" + str(size_kb) + " KB)")
                meta_rows.append(get_image_meta(img, city, filename))
                time.sleep(0.4)

        except Exception as e:
            print("  [ERROR] Season failed: " + str(e)[:200])
            continue

    print("\n  " + city.upper() + " result: " + str(collected) + "/" + str(TARGET_COUNT)
          + " downloaded | " + str(failed) + " failed | " + str(duplicates) + " duplicates")
    return collected


# ── Write metadata CSV ─────────────────────────────────────────────────────────

def write_metadata(rows):
    if not rows:
        print("No metadata to write.")
        return
    fields = ["filename", "city", "acquisition_date", "polarization",
              "pass_direction", "instrument_mode", "relative_orbit", "platform"]
    with open(META_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("\nMetadata -> " + META_CSV + "  (" + str(len(rows)) + " records)")


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary(results):
    print("\n" + "=" * 56)
    print("  FINAL DATASET SUMMARY")
    print("=" * 56)
    total = 0
    for city, count in results.items():
        tag = "[OK]" if count >= TARGET_COUNT else "[PARTIAL " + str(count) + "/" + str(TARGET_COUNT) + "]"
        print("  " + city.upper().ljust(14) + tag)
        total += count
    print("  " + "TOTAL".ljust(14) + str(total) + " images")
    print("  Output: " + OUT_DIR)
    print("=" * 56)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    init_gee()
    os.makedirs(OUT_DIR, exist_ok=True)

    meta_rows = []
    results   = {}

    for city, config in CITIES.items():
        results[city] = build_city(city, config, meta_rows)

    write_metadata(meta_rows)
    print_summary(results)


if __name__ == "__main__":
    main()
