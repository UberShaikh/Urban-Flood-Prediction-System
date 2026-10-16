import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt
import joblib
import os
import shap

# 1. GENERATE SYNTHETIC DATASET (Realistic distributions for Indian Metros)
def generate_synthetic_data(n_samples=5000):
    np.random.seed(42)
    
    # DYNAMIC FEATURES
    current_rainfall = np.random.gamma(2, 5, n_samples)  # 0-50mm typical
    rainfall_1h = current_rainfall * np.random.uniform(0.8, 1.2, n_samples)
    rainfall_3h = rainfall_1h * np.random.uniform(2, 4, n_samples)
    rainfall_24h = rainfall_3h * np.random.uniform(3, 8, n_samples)
    precipitation_probability = np.clip(rainfall_24h / 2, 0, 100)
    humidity = np.random.uniform(60, 95, n_samples)
    wind_speed = np.random.uniform(5, 35, n_samples)
    temperature = np.random.uniform(24, 34, n_samples)
    
    # STATIC FEATURES (Vulnerability)
    elevation_score = np.random.uniform(0, 100, n_samples)  # 100 = very low lying
    slope_score = np.random.uniform(0, 100, n_samples)      # 100 = very flat
    urban_density_score = np.random.uniform(20, 100, n_samples)
    vegetation_score = np.random.uniform(0, 80, n_samples)  # High = lower risk
    flood_history_score = np.random.uniform(0, 100, n_samples)
    waterbody_distance_score = np.random.uniform(0, 100, n_samples) # 100 = very close
    drainage_vulnerability_score = np.random.uniform(20, 100, n_samples)
    hotspot_score = np.random.uniform(0, 100, n_samples)
    coastal_risk_score = np.random.choice([0, 50, 100], n_samples, p=[0.5, 0.25, 0.25])
    lake_overflow_score = np.random.choice([0, 40, 90], n_samples, p=[0.7, 0.2, 0.1])
    
    # TARGET CALCULATION (Weighted Logic)
    # This ensures the model learns the intended physics-based relationships
    risk_score = (
        0.25 * (rainfall_3h / 50 * 100) + 
        0.15 * (rainfall_24h / 250 * 100) +
        0.20 * elevation_score +
        0.10 * slope_score +
        0.10 * hotspot_score +
        0.05 * urban_density_score +
        0.10 * drainage_vulnerability_score +
        0.05 * waterbody_distance_score -
        0.05 * vegetation_score
    )
    
    # Add some noise
    risk_score += np.random.normal(0, 3, n_samples)
    risk_score = np.clip(risk_score, 0, 100)
    
    data = pd.DataFrame({
        'current_rainfall': current_rainfall,
        'rainfall_1h': rainfall_1h,
        'rainfall_3h': rainfall_3h,
        'rainfall_24h': rainfall_24h,
        'precipitation_probability': precipitation_probability,
        'humidity': humidity,
        'wind_speed': wind_speed,
        'temperature': temperature,
        'elevation_score': elevation_score,
        'slope_score': slope_score,
        'urban_density_score': urban_density_score,
        'vegetation_score': vegetation_score,
        'flood_history_score': flood_history_score,
        'waterbody_distance_score': waterbody_distance_score,
        'drainage_vulnerability_score': drainage_vulnerability_score,
        'hotspot_score': hotspot_score,
        'coastal_risk_score': coastal_risk_score,
        'lake_overflow_score': lake_overflow_score,
        'risk_score': risk_score
    })
    
    return data

# 2. TRAINING PIPELINE
def train_model():
    print("Generating synthetic urban flood dataset...")
    df = generate_synthetic_data(10000)
    
    X = df.drop('risk_score', axis=1)
    y = df['risk_score']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Regressor...")
    model = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    # 3. EVALUATION
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    print("\nEvaluation Metrics:")
    print(f"   - MAE:  {mae:.4f}")
    print(f"   - RMSE: {rmse:.4f}")
    print(f"   - R²:   {r2:.4f}")
    
    # 4. SAVE MODEL
    model_path = 'models/flood_model_v1.joblib'
    joblib.dump(model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # 5. FEATURE IMPORTANCE
    plt.figure(figsize=(10, 6))
    xgb.plot_importance(model, max_num_features=10, importance_type='weight')
    plt.title("XGBoost Feature Importance")
    plt.tight_layout()
    plt.savefig('models/feature_importance.png')
    print("Feature importance graph saved to models/feature_importance.png")

    # 6. SHAP EXPLAINABILITY (Small sample for speed)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test.iloc[:100])
    plt.figure()
    shap.summary_plot(shap_values, X_test.iloc[:100], show=False)
    plt.title("SHAP Summary Plot")
    plt.tight_layout()
    plt.savefig('models/shap_summary.png')
    print("SHAP summary plot saved to models/shap_summary.png")

if __name__ == "__main__":
    if not os.path.exists('models'):
        os.makedirs('models')
    train_model()
