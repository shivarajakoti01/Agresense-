# Smart AI Irrigation System Implementation Plan

This document outlines the architecture and implementation strategy for the Smart AI Irrigation System, an AI-powered agriculture platform.

## Background Context
The system will monitor soil and environmental conditions, provide intelligent irrigation and nutrient recommendations using Machine Learning (RandomForest), and offer a self-learning fallback mode in case of sensor failures. It will feature a premium, dynamic, and responsive frontend dashboard built with HTML/CSS/JS (Tailwind CSS and Chart.js). The backend will be powered by Flask and SQLite.

> [!IMPORTANT]
> **User Review Required**: Please review the proposed architecture, database schema, and machine learning features. If there are any specific ESP32 data formats you prefer, or a specific Tailwind version, please let me know.

## Open Questions
- Do you have a specific sample dataset you'd like to use to pre-train the model, or should I generate a synthetic dataset representing typical agriculture metrics?
- For the login system, do you need full user authentication (JWT/Sessions) or just a simple mock login screen to meet the UI requirement for now?
- Would you prefer SQLAlchemy as an ORM or raw SQLite queries for the database? (I plan to use SQLAlchemy for ease of management).

## Proposed Changes

The project will be organized into the following structure:

### Backend and Core Logic
The backend handles routing, API endpoints for the ESP32, and the self-learning ML model.

#### [NEW] `requirements.txt`
Contains backend dependencies: `Flask`, `Flask-SQLAlchemy`, `scikit-learn`, `pandas`, `numpy`.

#### [NEW] `app.py`
The main Flask application entry point. Will include:
- Page routing (`/`, `/analytics`, `/alerts`, `/sensor_status`, `/settings`, `/login`)
- ESP32 Data API (`POST /api/sensor`)
- Frontend Data API (`GET /api/live_data`, `GET /api/historical_data`)

#### [NEW] `database.py`
Database models using SQLAlchemy:
- `SensorReading`: timestamp, moisture, temperature, valid_reading (boolean)
- `Prediction`: timestamp, predicted_water_needed, plant_health, soil_condition, recommendation
- `Alert`: timestamp, message, type (e.g., Sensor Failure, Dry Soil)

#### [NEW] `ml_model.py`
Machine Learning module responsible for:
- **Initialization**: Loading or creating a synthetic dataset for initial training of the `RandomForestClassifier`.
- **Prediction**: Generating real-time predictions based on live sensor data.
- **Sensor Failure Fallback**: Detecting invalid readings and estimating soil conditions using historical patterns and current temperature.
- **Retraining**: Automatically retraining the model once enough new valid sensor readings are collected.

---

### Frontend Pages
The frontend will use Tailwind CSS (via CDN for simplicity) and custom CSS to achieve the requested premium, glassmorphism, dark green agriculture theme.

#### [NEW] `static/css/style.css`
Custom styling for animations, glassmorphism effects, and premium UI touches not covered by Tailwind utilities.

#### [NEW] `static/js/main.js`
Handles polling `/api/live_data`, updating Chart.js instances, and handling UI interactions (alerts, fallback mode indications).

#### [NEW] `templates/base.html`
The base layout containing the modern sidebar navigation and top bar.

#### [NEW] `templates/dashboard.html`
Real-time dashboard showing live soil moisture, temperature, AI predictions, alerts, and live charts.

#### [NEW] `templates/analytics.html`
Historical data analysis with larger, more detailed Chart.js graphs.

#### [NEW] `templates/alerts.html`
A log of system alerts (Dry Soil, High Temp, Sensor Failures).

#### [NEW] `templates/sensor_status.html`
Detailed view of sensor health and the AI Fallback mode status.

#### [NEW] `templates/settings.html`
Settings UI for configuring thresholds (e.g., dry soil threshold) and ML retraining frequency.

#### [NEW] `templates/login.html`
A premium login screen for the platform.

---

## Verification Plan

### Automated Tests
- Run `python app.py` and ensure the server starts without errors.
- Send simulated `POST` requests to `/api/sensor` with valid and invalid data to test the ESP32 ingestion and the sensor failure detection.
- Verify the ML model predicts successfully and triggers the retraining logic after receiving a set number of inputs.

### Manual Verification
- Open the dashboard in a browser and verify the "Premium agriculture theme", animations, and glassmorphism UI elements are present and responsive.
- Simulate a sensor failure (e.g., sending `-1` for moisture) and observe the UI updating to "AI Prediction Mode Active" and predicting based on fallback logic.
- Verify that Chart.js graphs update in real-time as new data is injected via the API.
