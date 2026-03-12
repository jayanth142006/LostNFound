import sys
import os

# Add backend to path
backend_path = r"c:\Users\bhav0\Documents\Projects\lostnfound\lostnfound-backend\LostNFound\backend"
sys.path.append(backend_path)
os.chdir(backend_path) # Important for relative paths in main.py

from main import calculate_recovery_probability, recovery_model, recovery_columns, SessionLocal
from models import LostItem, Base
from database import engine

def test_recovery_logic():
    print(f"Checking if model is loaded...")
    if recovery_model is not None:
        print("✅ Recovery model loaded successfully.")
    else:
        print("❌ Recovery model NOT loaded.")
        return

    print("\nTesting calculate_recovery_probability...")
    prob = calculate_recovery_probability(
        category="id card",
        color="black",
        location="Clock Tower",
        time_str="12:00",
        days_since_loss=1
    )
    print(f"Calculated Probability for 'id card' at 'Clock Tower': {prob}%")
    
    if prob == 10.0:
        print("⚠️ Warning: Probability is 10.0 (fallback value). Check if this is expected.")
    else:
        print("✅ Probability is not the default fallback.")

    print("\nTesting database storage...")
    db = SessionLocal()
    try:
        # Create a dummy lost item
        dummy_lost = LostItem(
            description="Test item for recovery probability",
            email="test@example.com",
            category="id card",
            color="black",
            location="Clock Tower",
            time="12:00",
            days_since_loss=1,
            created_at="now",
            recovery_probability=prob
        )
        db.add(dummy_lost)
        db.commit()
        db.refresh(dummy_lost)
        
        print(f"Stored Item ID: {dummy_lost.id}")
        print(f"Stored Probability: {dummy_lost.recovery_probability}")
        
        if dummy_lost.recovery_probability == prob:
            print("✅ Database storage verified.")
        else:
            print(f"❌ Database storage FAILED. Expected {prob}, got {dummy_lost.recovery_probability}")
            
        # Clean up
        db.delete(dummy_lost)
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    test_recovery_logic()
