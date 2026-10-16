import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook", palette="husl")
plt.rcParams['figure.figsize'] = (10, 6)
flood_palette = {0: '#2ecc71', 1: '#e74c3c', '0': '#2ecc71', '1': '#e74c3c', 0.0: '#2ecc71', 1.0: '#e74c3c'}

dataset_path = os.path.join(RAW_DIR, "Dataset.csv")
df = pd.read_csv(dataset_path)

# PREPROCESSING PLOT A: CLASS BALANCE
plt.figure(figsize=(8, 5))
sns.countplot(data=df, x='Flood Occurred', palette=flood_palette, edgecolor='black', alpha=0.9)
plt.title("Preprocessing: Flood Occurrence Class Balance", weight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'plot4_class_balance.png'), dpi=300)
plt.close()

# PREPROCESSING PLOT B: OUTLIERS
plt.figure(figsize=(10, 6))
features_to_plot = [f for f in ['Rainfall (mm)', 'River Discharge (m³/s)'] if f in df.columns]
sns.boxplot(data=df[features_to_plot], orient="h", palette="mako")
plt.title("Preprocessing: Outlier Detection in Water Metrics", weight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'plot5_outliers.png'), dpi=300)
plt.close()

# API VARIANCE PLOT
nasa_path = os.path.join(RAW_DIR, "nasa_power_weather.json")
try:
    with open(nasa_path, 'r') as f:
        nasa_data = json.load(f)
        precip_dict = nasa_data['properties']['parameter'].get('PRECTOTCORR', {})
        precip_ts = list(precip_dict.values())
        if len(precip_ts) > 0:
            plt.figure(figsize=(12, 5))
            plt.plot(precip_ts, color='#3498db', marker='o', alpha=0.7, label='NASA API Daily Precip')
            if 'Rainfall (mm)' in df.columns:
                static_median = df['Rainfall (mm)'].median()
                plt.axhline(static_median, color='#e74c3c', linestyle='--', linewidth=2, label='Local CSV Static Median')
            plt.title("Time-Series Variance: NASA API vs Local Dataset", weight='bold')
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(OUTPUT_DIR, 'plot6_api_variance.png'), dpi=300)
            plt.close()
except:
    pass

print("New preprocessing plots generated successfully!")
