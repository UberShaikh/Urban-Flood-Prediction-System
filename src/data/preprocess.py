import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DATA_PATH = os.path.join(BASE_DIR, "data", "raw", "Dataset.csv")
PROCESSED_DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "Dataset_processed.csv")

def preprocess_data():
    print(f"Loading raw dataset from {RAW_DATA_PATH}...")
    if not os.path.exists(RAW_DATA_PATH):
        print("Raw dataset not found.")
        return
        
    df = pd.read_csv(RAW_DATA_PATH)
    print(f"Original shape: {df.shape}")
    
    # Drop rows with missing target
    if 'Flood Occurred' in df.columns:
        df = df.dropna(subset=['Flood Occurred'])
        
    # Fill missing numerics with median
    num_cols = df.select_dtypes(include=['float64', 'int64']).columns
    df[num_cols] = df[num_cols].fillna(df[num_cols].median())
    
    # Encode categorical variables
    cat_cols = ['Land Cover', 'Soil Type']
    le = LabelEncoder()
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
            df[col] = le.fit_transform(df[col])
            
    # Save the processed dataset
    os.makedirs(os.path.dirname(PROCESSED_DATA_PATH), exist_ok=True)
    df.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"Processed dataset saved to {PROCESSED_DATA_PATH}")
    print(f"Processed shape: {df.shape}")

if __name__ == "__main__":
    preprocess_data()
