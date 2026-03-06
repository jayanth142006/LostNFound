import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import os

MODEL_PATH = "recovery_model_v3.pkl"
COLUMNS_PATH = "model_columns.pkl"

def retrain_model(data_path):
    """
    Retrains the RandomForest model using the provided CSV data.
    """
    print(f"🔄 Starting retraining with data from {data_path}...")
    
    try:
        # 1. Load Data
        df = pd.read_csv(data_path)
        
        # Rename columns to match model expectations if needed
        # (Assuming the CSV matches the schema: category, color, reported_location, etc.)
        
        # 2. Features & Target
        # Map User Input 'location_type' to 'reported_location' if needed
        if 'reported_location' not in df.columns and 'location_type' in df.columns:
            df['reported_location'] = df['location_type']
            
        target = "recovered"
        features = ["category", "color", "reported_location", "footfall_score", 
                   "days_since_loss", "max_similarity_score", "similar_items_nearby_48h"]
        
        X = df[features]
        y = df[target]
        
        # 3. One-Hot Encoding
        X_encoded = pd.get_dummies(X, columns=["category", "color", "reported_location"])
        
        # 4. Align with Original Model Columns (to prevent breaking the API)
        # We need to ensure the new model has the same columns, or compatible ones.
        # Actually, for a total retrain, we define the NEW columns.
        model_columns = list(X_encoded.columns)
        
        # 5. Train Model
        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X_encoded, y)
        
        # 6. Save Artifacts
        joblib.dump(clf, MODEL_PATH)
        joblib.dump(model_columns, COLUMNS_PATH)
        
        print("✅ Model retrained and saved successfully.")
        return True, f"Retrained on {len(df)} records."
        
    except Exception as e:
        print(f"❌ Retraining failed: {e}")
        return False, str(e)
