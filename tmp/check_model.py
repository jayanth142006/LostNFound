import joblib
import pandas as pd
import os

COLUMNS_PATH = r"c:\Users\bhav0\Documents\Projects\lostnfound\rec_prob\model_columns.pkl"
try:
    columns = joblib.load(COLUMNS_PATH)
    print("Columns in model:")
    for col in columns:
        print(f"- {col}")
except Exception as e:
    print(f"Error: {e}")
