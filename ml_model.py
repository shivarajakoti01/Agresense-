import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import os
import joblib

MODEL_PATH = 'rf_model.pkl'

class SmartIrrigationModel:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.load_or_train_initial_model()

    def generate_synthetic_data(self, num_samples=1000):
        np.random.seed(42)
        # Moisture (0-100%), Temperature (10-45C)
        moisture = np.random.uniform(0, 100, num_samples)
        temperature = np.random.uniform(10, 45, num_samples)
        
        # Target: 1 if irrigation needed, 0 otherwise.
        # Rule of thumb: dry (< 30) or hot & moderately dry (< 40 and > 30C) -> needs water
        irrigation_needed = np.where((moisture < 30) | ((moisture < 40) & (temperature > 30)), 1, 0)
        
        return pd.DataFrame({
            'moisture': moisture,
            'temperature': temperature,
            'irrigation_needed': irrigation_needed
        })

    def load_or_train_initial_model(self):
        if os.path.exists(MODEL_PATH):
            self.model = joblib.load(MODEL_PATH)
            self.is_trained = True
            print("Loaded existing ML model.")
        else:
            print("Training initial model with synthetic data...")
            df = self.generate_synthetic_data()
            self.train(df)

    def train(self, data_df):
        X = data_df[['moisture', 'temperature']]
        y = data_df['irrigation_needed']
        
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True
        
        joblib.dump(self.model, MODEL_PATH)
        print("Model trained and saved.")

    def retrain(self, db_readings):
        """ Retrain based on recent database readings if enough exist. """
        if len(db_readings) < 100:
            return False # Not enough new data to retrain
            
        print(f"Retraining model with {len(db_readings)} historical data points...")
        df = pd.DataFrame(db_readings)
        # Assuming db_readings dictionaries have 'moisture', 'temperature'
        # To get the 'irrigation_needed' target for historical training, we'd ideally have manual feedback.
        # For auto-learning, we might reinforce existing logic or use external triggers.
        # Here we apply the base logic to label historical data to reinforce the model 
        # (in a real system, you'd use actual water flow events or farmer feedback).
        df['irrigation_needed'] = np.where((df['moisture'] < 30) | ((df['moisture'] < 40) & (df['temperature'] > 30)), 1, 0)
        
        self.train(df)
        return True

    def predict(self, moisture, temperature):
        if not self.is_trained:
            return {"water_needed": False, "confidence": 0.0, "plant_health": "Unknown"}
            
        features = pd.DataFrame([[moisture, temperature]], columns=['moisture', 'temperature'])
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]
        confidence = max(probabilities) * 100
        
        water_needed = bool(prediction == 1)
        
        # Additional heuristics for UI
        plant_health = "Good"
        soil_condition = "Optimal"
        recommendation = "No action needed"
        
        if moisture < 20:
            plant_health = "Critical"
            soil_condition = "Very Dry"
            recommendation = "Immediate Irrigation Required"
        elif water_needed:
            plant_health = "Fair"
            soil_condition = "Dry"
            recommendation = "Start Irrigation Cycle"
        elif moisture > 80:
            plant_health = "Fair"
            soil_condition = "Waterlogged"
            recommendation = "Stop Irrigation - Risk of Root Rot"
            
        if temperature > 38:
            recommendation += " + High Temp Warning"
            if plant_health == "Good": plant_health = "Stressed"

        # Nutrient heuristic (mock)
        if 40 <= moisture <= 60 and 20 <= temperature <= 25:
            recommendation += " | Ideal time for Nitrogen Fertilizer"

        return {
            "water_needed": water_needed,
            "plant_health": plant_health,
            "soil_condition": soil_condition,
            "recommendation": recommendation,
            "confidence": round(confidence, 2)
        }

    def predict_fallback(self, current_temperature, historical_avg_moisture):
        """ Estimate conditions when sensor fails """
        print("Using Fallback AI Prediction Mode...")
        # Estimate moisture dropping based on high temp
        estimated_moisture = historical_avg_moisture
        if current_temperature > 30:
            estimated_moisture -= 5 # Assume it's drying faster
            
        prediction = self.predict(estimated_moisture, current_temperature)
        prediction["is_fallback"] = True
        prediction["soil_condition"] = f"Estimated ({prediction['soil_condition']})"
        return prediction

# Singleton instance
irrigation_ai = SmartIrrigationModel()
