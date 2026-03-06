import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# ---------------------------
# Global State & Lifespan
# ---------------------------

model_data = {}

# ---------------------------
# Global State & Imports
# ---------------------------
import os
import shutil
import pandas as pd
from model_utils import retrain_model

DATA_DIR = "data"
ORIGINAL_DATA = "snn_recovery_training_dataset_v5_demo_strong.csv"
MERGED_DATA = os.path.join(DATA_DIR, "merged_data.csv")
NEW_DATA_COUNTER = 0

# Ensure Data Directory Exists
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Merged Data if not exists
if not os.path.exists(MERGED_DATA):
    if os.path.exists(ORIGINAL_DATA):
        shutil.copy(ORIGINAL_DATA, MERGED_DATA)
    else:
        # Create empty if original not found (shouldn't happen based on context)
        df_empty = pd.DataFrame(columns=["category", "color", "reported_location", "footfall_score", 
                                       "days_since_loss", "max_similarity_score", "similar_items_nearby_48h", "recovered"])
        df_empty.to_csv(MERGED_DATA, index=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load Model & Column Schema on startup
    load_model()
    yield
    # Clean up (if necessary)
    model_data.clear()

def load_model():
    try:
        model_data["model"] = joblib.load("recovery_model_v3.pkl")
        model_data["columns"] = joblib.load("model_columns.pkl")
        print("✅ Model and columns loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading model files: {e}")
        model_data["model"] = None
        model_data["columns"] = []

app = FastAPI(title="Recovery Probability API", lifespan=lifespan)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# ---------------------------
# Input Schema
# ---------------------------

# ---------------------------
# Input Schema
# ---------------------------

class UserRecoveryInput(BaseModel):
    category: str
    color: str
    location_type: str = Field(..., description="Location or 'Unknown'")
    lost_time: str = Field(..., description="Approximate time (HH:MM) in 24h format")
    days_since_loss: int = Field(..., ge=0, description="Days passed since item was lost")

# ---------------------------
# Feature Engineering Logic
# ---------------------------

def get_footfall_score(location: str, time_str: str) -> float:
    """
    Calculates footfall score based on location and time of day.
    """
    location = location.lower()
    
    # 1. Handle Unknown Location
    if not location or "unknown" in location or "not sure" in location:
        return 2.0 # Low-Medium default for unknown (could be anywhere, but harder to find)

    # 2. Category Inference & Base Score
    # User Mapping: Landmark=0.9, Building=0.85, Transit=0.75, Pathway=0.6, Open Area=0.45
    
    # Default fallback
    base_score = 0.45 
    
    # Keyword Mappings
    if any(k in location for k in ["clock", "tower", "landmark", "statue", "monument", "entrance", "gate"]):
        base_score = 0.90 # Landmark
    elif any(k in location for k in ["canteen", "library", "audi", "class", "lab", "block", "dept", "office", "room", "hall", "building"]):
        base_score = 0.85 # Building
    elif any(k in location for k in ["bus", "stop", "station", "subway", "transit", "vehicle", "parking"]):
        base_score = 0.75 # Transit / High Traffic Zone (Parking is often distinct but Transit fits crowd profile)
    elif any(k in location for k in ["path", "way", "road", "walk", "corridor", "stairs", "lobby"]):
        base_score = 0.60 # Pathway
    elif any(k in location for k in ["ground", "field", "garden", "open", "area", "court"]):
        base_score = 0.45 # Open Area

    # 3. Time Adjustment
    try:
        hour = int(time_str.split(":")[0])
        
        # Peak: 8-9 (Arrival), 12-14 (Lunch), 15-16 (Departure)
        is_peak = (8 <= hour <= 9) or (12 <= hour <= 14) or (15 <= hour <= 16)
        
        # Night: 20:00 - 06:00
        is_night = (hour >= 20) or (hour < 6)
        
        if is_peak:
            base_score = base_score * 1.1 # Multiplier 1.1x
        elif is_night:
            base_score = base_score * 0.6 # Multiplier 0.6x
            
    except:
        pass 
        
    return min(1.0, float(base_score))

def enrich_data(user_input: UserRecoveryInput):
    """
    Automates the generation of technical features based on user input.
    """
    footfall_score = get_footfall_score(user_input.location_type, user_input.lost_time)
        
    # Simulate Similarity Score (0-1)
    common_items = ["id card", "wallet", "phone", "umbrella", "bottle"]
    
    max_similarity_score = 0.4 # Default
    if any(k in user_input.category.lower() for k in common_items):
        max_similarity_score = 0.75
    
    # Simulate Similar Items Found (48h)
    similar_items_nearby_48h = int(footfall_score * max_similarity_score * 0.5)

    return {
        "category": user_input.category,
        "color": user_input.color,
        "location_type": user_input.location_type,
        "footfall_score": footfall_score,
        "days_since_loss": user_input.days_since_loss,
        "max_similarity_score": max_similarity_score,
        "similar_items_nearby_48h": similar_items_nearby_48h
    }

# ---------------------------
# Prediction Endpoint
# ---------------------------

@app.post("/predict")
def predict_recovery(data: UserRecoveryInput):
    model = model_data.get("model")
    model_columns = model_data.get("columns")

    if model is None or not model_columns:
        raise HTTPException(status_code=503, detail="Model service is unavailable. Please check server logs.")

    try:
        # Generate full feature set
        enriched_data = enrich_data(data)
        
        # Convert to DataFrame
        input_df = pd.DataFrame([enriched_data])

        # One-hot encode
        input_df = pd.get_dummies(input_df)

        # Align with training columns
        input_df = input_df.reindex(columns=model_columns, fill_value=0)

        # Predict probability
        probability = float(model.predict_proba(input_df)[0][1])

        return {
            "recovery_probability_percent": round(probability * 100, 2),
            "debug_info": enriched_data # Return this so user can see what "AI" did
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

# Reload Trigger Check