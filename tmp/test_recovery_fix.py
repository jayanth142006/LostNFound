import os
import sys
import joblib
import pandas as pd

# Add backend to path
backend_path = r"c:\Users\bhav0\Documents\Projects\lostnfound\lostnfound-backend\LostNFound\backend"
sys.path.append(backend_path)

from main import calculate_recovery_probability

def test_prediction():
    print("Testing recovery probability calculation...")
    
    # Test cases
    test_cases = [
        ("ID Card", "Blue", "Library", "10:00", 1),
        ("Wallet", "Black", "Canteen", "13:00", 0),
        ("Umbrella", "Red", "Main Gate", "17:00", 2),
        ("Phone", "Black", "Unknown", "21:00", 5)
    ]
    
    for cat, col, loc, time_val, days in test_cases:
        try:
            prob = calculate_recovery_probability(cat, col, loc, time_val, days)
            print(f"Input: {cat}, {col}, {loc}, {time_val}, {days}d -> Probability: {prob}%")
        except Exception as e:
            print(f"Error for {cat}: {e}")

if __name__ == "__main__":
    test_prediction()
