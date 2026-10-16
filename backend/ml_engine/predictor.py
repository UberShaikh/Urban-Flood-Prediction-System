import joblib
import pandas as pd
import numpy as np
import os

class FloodPredictor:
    def __init__(self, model_path=None):
        if model_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base_dir, 'models', 'flood_model_v1.joblib')
        
        self.model = joblib.load(model_path)
        self.feature_names = [
            'current_rainfall', 'rainfall_1h', 'rainfall_3h', 'rainfall_24h',
            'precipitation_probability', 'humidity', 'wind_speed', 'temperature',
            'elevation_score', 'slope_score', 'urban_density_score', 'vegetation_score',
            'flood_history_score', 'waterbody_distance_score', 'drainage_vulnerability_score',
            'hotspot_score', 'coastal_risk_score', 'lake_overflow_score'
        ]

    def predict(self, features_dict):
        """
        Input: Dictionary of features
        Output: Prediction result with category and explanation
        """
        # Ensure all features are present
        input_data = []
        for feat in self.feature_names:
            input_data.append(features_dict.get(feat, 0))
            
        df_input = pd.DataFrame([input_data], columns=self.feature_names)
        
        # Predict
        risk_score = self.model.predict(df_input)[0]
        risk_score = float(np.clip(risk_score, 0, 100))
        
        # Map Category
        if risk_score <= 25:
            category = "Low"
        elif risk_score <= 50:
            category = "Moderate"
        elif risk_score <= 75:
            category = "High"
        else:
            category = "Critical"
            
        # Basic Explanation Logic
        explanations = []
        if features_dict.get('rainfall_3h', 0) > 30:
            explanations.append("Extreme short-term rainfall accumulation")
        if features_dict.get('elevation_score', 0) > 70:
            explanations.append("Very low-lying topographic profile")
        if features_dict.get('drainage_vulnerability_score', 0) > 80:
            explanations.append("Significant drainage infrastructure lag")
        if features_dict.get('hotspot_score', 0) > 75:
            explanations.append("Historical inundation hotspot zone")
            
        if not explanations:
            explanations.append("Standard seasonal variation")
            
        return {
            "risk_score": round(risk_score, 2),
            "category": category,
            "explanations": explanations,
            "status": "SUCCESS"
        }

# Example Usage
if __name__ == "__main__":
    predictor = FloodPredictor()
    sample_input = {
        'current_rainfall': 15,
        'rainfall_1h': 20,
        'rainfall_3h': 45,
        'rainfall_24h': 120,
        'precipitation_probability': 85,
        'humidity': 90,
        'wind_speed': 15,
        'temperature': 28,
        'elevation_score': 85,
        'slope_score': 90,
        'urban_density_score': 95,
        'vegetation_score': 5,
        'flood_history_score': 90,
        'waterbody_distance_score': 80,
        'drainage_vulnerability_score': 95,
        'hotspot_score': 95,
        'coastal_risk_score': 100,
        'lake_overflow_score': 0
    }
    
    result = predictor.predict(sample_input)
    print("\n--- Prediction Result ---")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Category:   {result['category']}")
    print(f"Reasoning:  {', '.join(result['explanations'])}")
