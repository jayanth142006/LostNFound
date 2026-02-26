import os
import joblib
import pandas as pd
from pydantic import BaseModel, Field

# Load model and columns
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
MODEL_PATH = os.path.join(MODEL_DIR, "recovery_model_v3.pkl")
COLUMNS_PATH = os.path.join(MODEL_DIR, "model_columns.pkl")

class RecoveryEngine:
    def __init__(self):
        self.model = None
        self.columns = None
        self.load_model()

    def load_model(self):
        try:
            if os.path.exists(MODEL_PATH) and os.path.exists(COLUMNS_PATH):
                self.model = joblib.load(MODEL_PATH)
                self.columns = joblib.load(COLUMNS_PATH)
                print("INFO: Recovery model and columns loaded successfully.")
            else:
                print(f"ERROR: Model files not found at {MODEL_DIR}")
        except Exception as e:
            print(f"ERROR: Error loading model files: {e}")

    def get_footfall_score(self, location: str, time_str: str) -> float:
        location = location.lower()
        if not location or "unknown" in location or "not sure" in location:
            return 0.2
        
        base_score = 0.45 
        if any(k in location for k in ["clock", "tower", "landmark", "statue", "monument", "entrance", "gate"]):
            base_score = 0.90
        elif any(k in location for k in ["canteen", "library", "audi", "class", "lab", "block", "dept", "office", "room", "hall", "building"]):
            base_score = 0.85
        elif any(k in location for k in ["bus", "stop", "station", "subway", "transit", "vehicle", "parking"]):
            base_score = 0.75
        elif any(k in location for k in ["path", "way", "road", "walk", "corridor", "stairs", "lobby"]):
            base_score = 0.60
        elif any(k in location for k in ["ground", "field", "garden", "open", "area", "court"]):
            base_score = 0.45

        try:
            hour = int(time_str.split(":")[0])
            is_peak = (8 <= hour <= 9) or (12 <= hour <= 14) or (15 <= hour <= 16)
            is_night = (hour >= 20) or (hour < 6)
            if is_peak:
                base_score = base_score * 1.1
            elif is_night:
                base_score = base_score * 0.6
        except:
            pass 
        return min(1.0, float(base_score))

    def predict(self, category: str, color: str, location_type: str, lost_time: str, days_since_loss: int):
        if self.model is None or self.columns is None:
            return None

        footfall_score = self.get_footfall_score(location_type, lost_time)
        
        # Simulate Similarity Score (matching logic from original app.py)
        common_items = ["id card", "wallet", "phone", "umbrella", "bottle"]
        max_similarity_score = 0.4
        if any(k in category.lower() for k in common_items):
            max_similarity_score = 0.75
        
        similar_items_nearby_48h = int(footfall_score * max_similarity_score * 0.5)

        enriched_data = {
            "category": category,
            "color": color,
            "location_type": location_type,
            "footfall_score": footfall_score,
            "days_since_loss": days_since_loss,
            "max_similarity_score": max_similarity_score,
            "similar_items_nearby_48h": similar_items_nearby_48h
        }

        input_df = pd.DataFrame([enriched_data])
        input_df = pd.get_dummies(input_df)
        input_df = input_df.reindex(columns=self.columns, fill_value=0)

        probability = float(self.model.predict_proba(input_df)[0][1])
        return round(probability * 100, 2)

# Singleton instance
engine = RecoveryEngine()
