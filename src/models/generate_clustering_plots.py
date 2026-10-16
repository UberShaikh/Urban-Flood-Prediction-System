import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os
import warnings
warnings.filterwarnings('ignore')

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "plots", "clustering")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook", palette="husl")
plt.rcParams['figure.figsize'] = (10, 6)
# Safely rendering multi-type mappings
cluster_palette = {0: '#2ecc71', 1: '#f1c40f', 2: '#e74c3c', '0': '#2ecc71', '1': '#f1c40f', '2': '#e74c3c', 0.0: '#2ecc71', 1.0: '#f1c40f', 2.0: '#e74c3c'}

dataset_path = os.path.join(PROCESSED_DIR, "matched_processed_data.csv")
df = pd.read_csv(dataset_path)

features = ['Rainfall (mm)', 'River Discharge (m³/s)', 'Water Level (m)', 'Elevation (m)']
X_scaled = StandardScaler().fit_transform(df[features])

# Plot 1: Elbow
inertia = [KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled).inertia_ for k in range(2, 8)]
plt.figure()
plt.plot(range(2, 8), inertia, marker='o', color='#9b59b6', linewidth=3, markersize=8)
plt.title("Plot 1: Elbow Method")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot1_elbow.png'), dpi=300, bbox_inches='tight')
plt.close()

# Plot 2: Silhouette
sil_scores = [silhouette_score(X_scaled, KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X_scaled)) for k in range(2, 8)]
plt.figure()
plt.bar(range(2, 8), sil_scores, color='#3498db', edgecolor='black')
plt.title("Plot 2: Silhouette Score Evaluation")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot2_silhouette.png'), dpi=300, bbox_inches='tight')
plt.close()

# kmeans mapping
km = KMeans(n_clusters=3, random_state=42, n_init=10)
df['Cluster'] = km.fit_predict(X_scaled)
cluster_elevations = df.groupby('Cluster')['Elevation (m)'].mean()
danger_cluster = cluster_elevations.idxmin()
safe_cluster = cluster_elevations.idxmax()
warning_cluster = [c for c in [0, 1, 2] if c not in [danger_cluster, safe_cluster]][0]
mapping = {safe_cluster: 0, warning_cluster: 1, danger_cluster: 2}
df['Risk_Zone'] = df['Cluster'].map(mapping)

# Plot 3: Spatial 1
plt.figure()
sns.scatterplot(data=df, x="Elevation (m)", y="River Discharge (m³/s)", hue="Risk_Zone", palette=cluster_palette, alpha=0.8)
plt.title("Plot 3: Spatial Zoning")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot3_spatial.png'), dpi=300, bbox_inches='tight')
plt.close()

# Plot 4: Spatial 2
plt.figure()
sns.scatterplot(data=df, x="Rainfall (mm)", y="Water Level (m)", hue="Risk_Zone", palette=cluster_palette, alpha=0.8)
plt.title("Plot 4: Meteorological Zoning")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot4_meteo.png'), dpi=300, bbox_inches='tight')
plt.close()

# Plot 5: Validation
plt.figure()
zone_flood_rates = df.groupby('Risk_Zone')['Flood Occurred'].mean() * 100
sns.barplot(x=zone_flood_rates.index, y=zone_flood_rates.values, palette=cluster_palette, edgecolor='black')
plt.title("Plot 5: Validation Probability %")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot5_validation.png'), dpi=300, bbox_inches='tight')
plt.close()

# Plot 6: Violin
plt.figure(figsize=(12, 12))
for i, f in enumerate(features, 1):
    plt.subplot(2, 2, i)
    sns.violinplot(data=df, x="Risk_Zone", y=f, palette=cluster_palette)
plt.suptitle("Plot 6: Environmental Feature Distributions")
plt.savefig(os.path.join(OUTPUT_DIR, 'plot6_violin.png'), dpi=300, bbox_inches='tight')
plt.close()

print("Clustering plots securely built in outputs/plots/clustering/")
