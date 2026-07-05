from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, Response
from flask_cors import CORS
from database import db, SensorReading, PredictionHistory, Alert, User, IrrigationLog
from ml_model import irrigation_ai
import os
from datetime import datetime, timedelta
import threading
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import requests
import smtplib
from email.message import EmailMessage
import csv
import io
import json
import serial
import serial.tools.list_ports


app = Flask(__name__, template_folder='html', static_folder='html', static_url_path='/static')
app.secret_key = 'super_secret_agrisense_key_123'
CORS(app)

# --- CONFIGURATION ---
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

def load_settings():
    default_settings = {
        "weather_prediction_enabled": True,
        "fallback_mode_enabled": True,
        "retraining_frequency": 100,
        "dry_threshold": 20,
        "high_temp_threshold": 38,
        "latitude": 12.9172,
        "longitude": 74.856,
        "auto_location_enabled": True,
        "location_name": "auto-detected location",
        "pump_flow_rate": 5.0,
        "sensor_dry_raw": 4095,
        "sensor_wet_raw": 1500
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                # Merge defaults
                for k, v in default_settings.items():
                    if k not in settings:
                        settings[k] = v
                return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
    return default_settings

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

# Global memory settings
_settings = load_settings()

# Pump state tracking variables
last_pump_state = False
active_log_id = None
manual_trigger_flag = False
manual_trigger_pending = False
manual_stop_pending = False

# ESP32 state variables
_esp32_state = {
    "gps_valid": False,
    "location_source": "none"
}
last_raw_moisture = 4095

def auto_detect_location():
    global _settings
    if not _settings.get("auto_location_enabled", True):
        print("Auto-location is disabled (user-configured manual coordinates). Skipping startup geolocation.")
        return
    try:
        # Check coordinates from IP Geolocation
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        if resp.status_code == 200:
            geo_data = resp.json()
            if geo_data.get("status") == "success":
                _settings["latitude"] = float(geo_data["lat"])
                _settings["longitude"] = float(geo_data["lon"])
                _settings["location_name"] = geo_data.get("city", "Unknown") + ", " + geo_data.get("regionName", "")
                save_settings(_settings)
                print(f"Successfully auto-detected hardware location: {_settings['latitude']}, {_settings['longitude']}")
                # Run reverse geocoding in a background thread for more precise name
                threading.Thread(target=reverse_geocode_and_save, args=(_settings["latitude"], _settings["longitude"], "Server IP"), daemon=True).start()
    except Exception as e:
        print(f"Auto-location detection on startup failed: {e}")

# Run automatic detection in a background thread on startup
threading.Thread(target=auto_detect_location, daemon=True).start()

def geolocate_esp32_ip(ip_address):
    global _settings
    if not ip_address or ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.') or ip_address.startswith('172.16.'):
        print(f"ESP32 is connected via local IP {ip_address}, skipping IP geolocation.")
        return
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        if resp.status_code == 200:
            geo_data = resp.json()
            if geo_data.get("status") == "success":
                lat = float(geo_data["lat"])
                lon = float(geo_data["lon"])
                if abs(lat) > 0.1 or abs(lon) > 0.1:
                    if abs(_settings.get("latitude", 0) - lat) > 0.0001 or abs(_settings.get("longitude", 0) - lon) > 0.0001:
                        # Only geolocate if auto location detection is enabled
                        if _settings.get("auto_location_enabled", True):
                            _settings["latitude"] = lat
                            _settings["longitude"] = lon
                            _settings["location_name"] = geo_data.get("city", "Unknown") + ", " + geo_data.get("regionName", "")
                            save_settings(_settings)
                            print(f"Automatically aligned location with ESP32 public IP Geolocation: {lat}, {lon} (City: {geo_data.get('city')})")
                            # Perform reverse geocoding in a background thread to get high-accuracy town/suburb/village name
                            threading.Thread(target=reverse_geocode_and_save, args=(lat, lon, "ESP32 IP"), daemon=True).start()
                        else:
                            print(f"Ignored geolocate_esp32_ip ({lat}, {lon}) to preserve user's manual coordinates.")
    except Exception as e:
        print(f"Failed to geolocate ESP32 connection IP {ip_address}: {e}")

def reverse_geocode_and_save(lat, lon, source="GPS"):
    global _settings
    try:
        headers = {
            'User-Agent': 'AgriSense-Smart-Irrigation/1.0'
        }
        # Use OpenStreetMap reverse geocoding
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            address = data.get('address', {})
            
            # Construct detailed accurate place name
            parts = []
            if address.get('road'):
                parts.append(address['road'])
            if address.get('suburb') or address.get('neighbourhood'):
                parts.append(address.get('suburb') or address.get('neighbourhood'))
            if address.get('village') or address.get('town') or address.get('city'):
                parts.append(address.get('village') or address.get('town') or address.get('city'))
            if address.get('state'):
                parts.append(address['state'])
                
            if parts:
                name = ", ".join(parts)
            else:
                name = data.get('display_name', '')
                if not name and 'city' in address:
                    name = address['city']
                
            if name:
                full_location = f"[{source}] {name}"
                _settings["location_name"] = full_location
                save_settings(_settings)
                print(f"Successfully reverse-geocoded coordinates ({lat}, {lon}) to: {full_location}")
                return
    except Exception as e:
        print(f"Reverse geocoding failed: {e}")
        
    # If Nominatim fails or returns nothing, use generic coordinate string
    _settings["location_name"] = f"[{source}] {lat:.4f}°, {lon:.4f}°"
    save_settings(_settings)

def send_email_alert(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("Email not configured. Skipping alert.")
        return
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email alert sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__name__))
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://' which some cloud providers supply
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'smart_irrigation.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()
    # Enable SQLite WAL mode only when using SQLite database
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
        try:
            db.session.execute(db.text("PRAGMA journal_mode=WAL;"))
            db.session.commit()
            print("Successfully enabled WAL (Write-Ahead Logging) mode in SQLite.")
        except Exception as e:
            print(f"Error enabling WAL mode: {e}")
    # Migration to add pump_status column if it doesn't exist
    try:
        db.session.execute(db.text("ALTER TABLE sensor_reading ADD COLUMN pump_status BOOLEAN DEFAULT 0"))
        db.session.commit()
        print("Successfully ran database migration to add pump_status column.")
    except Exception:
        db.session.rollback()

    # Migration to add node_id column to sensor_reading if it doesn't exist
    try:
        db.session.execute(db.text("ALTER TABLE sensor_reading ADD COLUMN node_id VARCHAR(50) DEFAULT 'AGR-Node-001'"))
        db.session.commit()
        print("Successfully ran database migration to add node_id column.")
    except Exception:
        db.session.rollback()

    # Migration to add start_moisture and end_moisture to irrigation_log if they don't exist
    try:
        db.session.execute(db.text("ALTER TABLE irrigation_log ADD COLUMN start_moisture FLOAT"))
        db.session.commit()
        print("Successfully ran database migration to add start_moisture column.")
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text("ALTER TABLE irrigation_log ADD COLUMN end_moisture FLOAT"))
        db.session.commit()
        print("Successfully ran database migration to add end_moisture column.")
    except Exception:
        db.session.rollback()

    # Initialize in-memory pump states from DB logs
    try:
        latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
        if latest_reading:
            last_pump_state = latest_reading.pump_status if latest_reading.pump_status is not None else False
        else:
            last_pump_state = False
            
        open_log = IrrigationLog.query.filter(IrrigationLog.end_time == None).order_by(IrrigationLog.start_time.desc()).first()
        if open_log:
            active_log_id = open_log.id
        else:
            active_log_id = None
        print(f"Initialized pump states: last_pump_state={last_pump_state}, active_log_id={active_log_id}")
    except Exception as e:
        print(f"Error initializing database state variables: {e}")

# Store last valid readings in memory for fallback mode
last_valid_moisture = 50.0
last_valid_temp = 25.0

# ---- AUTHENTICATION ----

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    global _settings
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email address already exists.', 'error')
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        
        # Automatically detect and set hardware location based on server's public IP connection
        if _settings.get("auto_location_enabled", True):
            try:
                resp = requests.get("http://ip-api.com/json/", timeout=3)
                if resp.status_code == 200:
                    geo_data = resp.json()
                    if geo_data.get("status") == "success":
                        _settings["latitude"] = float(geo_data["lat"])
                        _settings["longitude"] = float(geo_data["lon"])
                        save_settings(_settings)
                        print(f"Auto-detected hardware location at registration: {geo_data['lat']}, {geo_data['lon']}")
            except Exception as e:
                print(f"Could not auto-detect location at registration: {e}")
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('login'))
            
        session['user_id'] = user.id
        # Extract the email's username (first name part before @) and format it nicely
        email_username = user.email.split('@')[0]
        clean_name = email_username.replace('.', ' ').replace('_', ' ').title()
        session['user_name'] = clean_name
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('login'))

# ---- PROTECTED ROUTES ----

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', current_user=session.get('user_name'))

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html', current_user=session.get('user_name'))

@app.route('/alerts')
@login_required
def alerts():
    return render_template('alerts.html', current_user=session.get('user_name'))

@app.route('/sensor_status')
@login_required
def sensor_status():
    return render_template('sensor_status.html', current_user=session.get('user_name'))

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', current_user=session.get('user_name'))

# ---- API ENDPOINTS ----

last_weather_temp = 25.0
last_weather_fetch_time = None

def fetch_backup_weather(lat, lon):
    try:
        url = f"https://wttr.in/{lat},{lon}?format=j1"
        headers = {'User-Agent': 'AgriSenseIrrigationSystem/1.0 (contact: shivarajakoti01@github.com)'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            curr = data['current_condition'][0]
            temp = float(curr['temp_C'])
            humidity = float(curr['humidity'])
            summary = curr['weatherDesc'][0]['value']
            
            hourly = data['weather'][0]['hourly']
            max_prob = max([int(h['chanceofrain']) for h in hourly])
            
            # Map weather description to appropriate icons
            desc_lower = summary.lower()
            icon = "fa-cloud text-gray-400"
            if "rain" in desc_lower or "shower" in desc_lower or "drizzle" in desc_lower:
                icon = "fa-cloud-showers-heavy text-blue-400"
            elif "thunder" in desc_lower:
                icon = "fa-cloud-bolt text-yellow-500"
            elif "sunny" in desc_lower or "clear" in desc_lower:
                icon = "fa-sun text-yellow-400"
            elif "cloud" in desc_lower or "overcast" in desc_lower:
                icon = "fa-cloud-sun text-gray-300"
            elif "fog" in desc_lower or "mist" in desc_lower or "haze" in desc_lower:
                icon = "fa-smog text-gray-400"
                
            return {
                'success': True,
                'temperature': temp,
                'humidity': humidity,
                'precipitation_probability': max_prob,
                'summary': summary,
                'icon': icon
            }
    except Exception as e:
        print(f"wttr.in backup weather failed: {e}")
    return {'success': False}

def get_current_weather_temp(lat, lon):
    global last_weather_temp, last_weather_fetch_time
    now = datetime.utcnow()
    # Cache for 15 minutes (900 seconds)
    if last_weather_fetch_time is None or (now - last_weather_fetch_time).total_seconds() > 900:
        # Try Open-Meteo first
        try:
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m&forecast_days=1"
            headers = {'User-Agent': 'AgriSenseIrrigationSystem/1.0 (contact: shivarajakoti01@github.com)'}
            resp = requests.get(weather_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                wdata = resp.json()
                temp_array = wdata.get('hourly', {}).get('temperature_2m', [])
                if temp_array:
                    last_weather_temp = temp_array[0]
                    last_weather_fetch_time = now
                    print(f"Updated cached weather temperature: {last_weather_temp}C")
                    return last_weather_temp
        except Exception as e:
            print(f"Failed to fetch weather temp from Open-Meteo: {e}")
            
        # Try wttr.in backup
        backup = fetch_backup_weather(lat, lon)
        if backup['success']:
            last_weather_temp = backup['temperature']
            last_weather_fetch_time = now
            print(f"Updated cached weather temperature using backup wttr.in: {last_weather_temp}C")
            
    return last_weather_temp

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    global last_valid_moisture, last_valid_temp, _settings, manual_trigger_pending, manual_trigger_flag, _esp32_state, manual_stop_pending, last_raw_moisture
    data = request.json
    
    if not data or 'moisture' not in data:
        return jsonify({'error': 'Invalid data'}), 400
        
    moisture = data['moisture']
    temperature = data.get('temperature', 25.0)
    heat_detected = data.get('heat_detected', False)
    pump_status = data.get('pump_status', False)
    node_id = data.get('node_id', 'AGR-Node-001')

    # Get raw moisture or reconstruct it
    raw_moisture = data.get('raw_moisture')
    if raw_moisture is None:
        # Reconstruct raw moisture from pre-mapped moisture percent
        raw_moisture = int((moisture / 100.0) * (1500 - 4095) + 4095)
    
    # Save the raw moisture in memory
    last_raw_moisture = raw_moisture

    # Apply backend user calibration if dry/wet thresholds are configured
    dry_val = _settings.get("sensor_dry_raw", 4095)
    wet_val = _settings.get("sensor_wet_raw", 1500)
    if dry_val != wet_val:
        moisture = float((raw_moisture - dry_val) * 100.0 / (wet_val - dry_val))
        moisture = max(0.0, min(100.0, moisture))
    
    # Handle incoming GPS data from ESP32 module
    gps_valid = data.get('gps_valid', False)
    location_source = data.get('location_source', 'unknown')
    _esp32_state["gps_valid"] = gps_valid
    _esp32_state["location_source"] = location_source
    if gps_valid and 'latitude' in data and 'longitude' in data:
        try:
            lat = float(data['latitude'])
            lon = float(data['longitude'])
            # Verify coordinates are valid non-zero
            if abs(lat) > 0.1 or abs(lon) > 0.1:
                is_real_gps = (location_source == "gps")
                auto_loc_enabled = _settings.get("auto_location_enabled", True)
                
                # Only align coordinates if it's a physical GPS lock OR if auto-location is enabled
                if is_real_gps or auto_loc_enabled:
                    # Update settings if they have changed by more than ~10 meters (approx 0.0001 deg)
                    if abs(_settings.get("latitude", 0) - lat) > 0.0001 or abs(_settings.get("longitude", 0) - lon) > 0.0001:
                        _settings["latitude"] = lat
                        _settings["longitude"] = lon
                        
                        # Only turn off auto-overwrite lock if we got a real physical GPS location
                        if is_real_gps:
                            _settings["auto_location_enabled"] = False
                            
                        save_settings(_settings)
                        print(f"Automatically aligned location with ESP32 {location_source.upper()} module: {lat}, {lon}")
                        
                        # Run reverse geocoding in a background thread
                        source_str = "GPS" if is_real_gps else "IP"
                        threading.Thread(target=reverse_geocode_and_save, args=(lat, lon, source_str), daemon=True).start()
                else:
                    print(f"Ignored incoming IP-derived coordinates ({lat}, {lon}) to preserve user's manual settings coordinates.")
        except (ValueError, TypeError) as e:
            print(f"Error parsing GPS coordinates: {e}")
    else:
        # Fallback: geolocate ESP32's connection IP in a background thread
        client_ip = request.headers.get('CF-Connecting-IP') or \
                    request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                    request.remote_addr
        if client_ip:
            threading.Thread(target=geolocate_esp32_ip, args=(client_ip,), daemon=True).start()
            
    # Overwrite temperature always with weather API temperature since DHT11 sensor is not present
    lat = _settings.get("latitude", 12.9172)
    lon = _settings.get("longitude", 74.856)
    temperature = get_current_weather_temp(lat, lon)

    # Save reading to CSV file
    csv_folder = os.path.join(basedir, 'csv_data')
    os.makedirs(csv_folder, exist_ok=True)
    csv_file = os.path.join(csv_folder, 'sensor_readings.csv')
    file_exists = os.path.isfile(csv_file)
    
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'moisture', 'temperature', 'heat_detected', 'pump_status'])
        writer.writerow([datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), moisture, temperature, heat_detected, pump_status])

    # Load dynamic settings
    weather_enabled = _settings.get("weather_prediction_enabled", True)
    fallback_enabled = _settings.get("fallback_mode_enabled", True)
    dry_thresh = _settings.get("dry_threshold", 20)
    high_temp_thresh = _settings.get("high_temp_threshold", 38)
    lat = _settings.get("latitude", 12.9172)
    lon = _settings.get("longitude", 74.856)
    
    # Validation / Sensor Failure Detection
    is_valid = True
    is_fallback = False
    if moisture < 0 or moisture > 100 or temperature < -20 or temperature > 60:
        is_valid = False
        if fallback_enabled:
            is_fallback = True
            
            # Create an Alert for Sensor Failure
            new_alert = Alert(message="Sensor Failure Detected: Out of bounds values", alert_type="Sensor Failure")
            db.session.add(new_alert)
            db.session.commit()
            
            # Use Fallback Logic
            ai_result = irrigation_ai.predict_fallback(last_valid_temp, last_valid_moisture)
        else:
            is_fallback = False
            ai_result = {
                'water_needed': False,
                'plant_health': 'Unknown (Sensor Error)',
                'soil_condition': 'Error',
                'recommendation': 'Sensor Failure. Fallback Mode is disabled.'
            }
    else:
        # Valid data
        last_valid_moisture = moisture
        last_valid_temp = temperature
        ai_result = irrigation_ai.predict(moisture, temperature)
        
        # Check if heat or fire is detected ("more than in range")
        is_heat_sensed = heat_detected or (temperature > high_temp_thresh)
        
        # Check if soil is in critical need of water (below user-configured dry threshold)
        is_critically_dry = moisture < dry_thresh
        
        if is_heat_sensed:
            ai_result['water_needed'] = True
            if heat_detected:
                ai_result['soil_condition'] = "Fire Warning"
                ai_result['recommendation'] = "CRITICAL: Flame/Fire detected! Turning pump ON immediately to extinguish."
            else:
                ai_result['soil_condition'] = "High Heat"
                ai_result['recommendation'] = f"High Temperature Sensed ({temperature}°C) above safe range. Turning pump ON to protect crops."
        elif is_critically_dry:
            ai_result['water_needed'] = True
            ai_result['soil_condition'] = "Critical Dry"
            ai_result['recommendation'] = "Soil is critically dry (mainly needed). Irrigating immediately."
        
        # Weather API Integration
        # Weather override applies if there is NO fire/heat detected (even if soil is dry, to save water when rain is expected).
        if ai_result['water_needed'] and weather_enabled and not is_heat_sensed:
            try:
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation_probability&forecast_days=1"
                headers = {'User-Agent': 'AgriSenseIrrigationSystem/1.0 (contact: shivarajakoti01@github.com)'}
                resp = requests.get(weather_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    raise Exception(f"Open-Meteo API returned status code {resp.status_code}")
                if resp.status_code == 200:
                    weather_data = resp.json()
                    prob_array = weather_data.get('hourly', {}).get('precipitation_probability', [])
                    if prob_array and max(prob_array) > 0:
                        max_prob = max(prob_array)
                        ai_result['water_needed'] = False
                        ai_result['recommendation'] = f"Rain expected today (Probability: {max_prob}%). Irrigation cancelled to save water."
                        db.session.add(Alert(message=f"Rain expected today ({max_prob}%). Irrigation cancelled.", alert_type="Weather Override"))
            except Exception as e:
                print(f"Weather API failed: {e}")
                # Try wttr.in backup weather API
                backup = fetch_backup_weather(lat, lon)
                if backup['success']:
                    max_prob = backup['precipitation_probability']
                    if max_prob > 0:
                        ai_result['water_needed'] = False
                        ai_result['recommendation'] = f"Rain expected today (Backup Probability: {max_prob}%). Irrigation cancelled to save water."
                        db.session.add(Alert(message=f"Rain expected today (Backup {max_prob}%). Irrigation cancelled.", alert_type="Weather Override"))
                else:
                    # Fallback / Mock weather logic when BOTH APIs fail:
                    # Default mock probability is 85% to trigger override for Mangaluru/standard fallback.
                    mock_prob = 85
                    if mock_prob > 0:
                        ai_result['water_needed'] = False
                        ai_result['recommendation'] = f"Rain expected today (Demo Mode Probability: {mock_prob}%). Irrigation cancelled to save water."
                        db.session.add(Alert(message=f"Rain expected today (Demo Mode {mock_prob}%). Irrigation cancelled.", alert_type="Weather Override"))
        
        # Create alerts for extreme valid conditions
        if heat_detected:
            db.session.add(Alert(message="CRITICAL: Extreme Heat / Fire Detected by Sensor!", alert_type="Fire Warning"))
            threading.Thread(target=send_email_alert, args=("CRITICAL: FIRE/HEAT DETECTED", f"Your irrigation system sensors have detected extreme heat.\nTemperature reading: {temperature} C")).start()
        if moisture < dry_thresh:
            db.session.add(Alert(message=f"Critical Dry Soil ({moisture}%)", alert_type="Dry Soil"))
        if temperature > high_temp_thresh:
            db.session.add(Alert(message=f"High Temperature Warning ({temperature}°C)", alert_type="High Temp"))
            
    # Apply manual trigger override
    if manual_trigger_pending:
        ai_result['water_needed'] = True
        ai_result['recommendation'] = "Irrigation pump manually triggered via web dashboard."
        manual_trigger_pending = False
        if pump_status:
            # Pump is already running, reset manual_trigger_flag to avoid mislabeling future auto starts
            manual_trigger_flag = False
    elif manual_stop_pending:
        ai_result['water_needed'] = False
        ai_result['recommendation'] = "Irrigation pump manually stopped via web dashboard."
        manual_stop_pending = False
            
    # Save Reading
    new_reading = SensorReading(node_id=node_id, moisture=moisture, temperature=temperature, valid_reading=is_valid, pump_status=pump_status)
    db.session.add(new_reading)
    
    # Track and log pump state transitions (irrigation cycles)
    global last_pump_state, active_log_id
    try:
        # 1. Pump turned ON (False -> True)
        if pump_status and not last_pump_state:
            new_log = IrrigationLog(
                start_time=datetime.utcnow(),
                trigger_type="Manual Override" if manual_trigger_flag else "Automatic",
                start_moisture=moisture
            )
            db.session.add(new_log)
            db.session.commit()
            active_log_id = new_log.id
            manual_trigger_flag = False
            print(f"[LOG] Pump ON detected. Started irrigation log: {active_log_id} (Moisture: {moisture}%)")
            
        # 2. Pump turned OFF (True -> False)
        elif not pump_status and last_pump_state:
            if active_log_id:
                log_entry = IrrigationLog.query.get(active_log_id)
                if log_entry:
                    log_entry.end_time = datetime.utcnow()
                    log_entry.duration_seconds = int((log_entry.end_time - log_entry.start_time).total_seconds())
                    log_entry.end_moisture = moisture
                    db.session.commit()
                    print(f"[LOG] Pump OFF detected. Closed irrigation log: {active_log_id} ({log_entry.duration_seconds}s, Moisture: {moisture}%)")
                active_log_id = None
                
        last_pump_state = pump_status
    except Exception as e:
        print(f"Error logging pump transitions: {e}")
        db.session.rollback()

    # Save Prediction History
    new_pred = PredictionHistory(
        water_needed=ai_result['water_needed'],
        plant_health=ai_result['plant_health'],
        soil_condition=ai_result['soil_condition'],
        recommendation=ai_result['recommendation'],
        is_fallback_mode=is_fallback
    )
    db.session.add(new_pred)
    db.session.commit()

    # Trigger async retraining check (e.g., every 50 valid readings)
    threading.Thread(target=check_and_retrain).start()

    return jsonify({'status': 'success', 'ai_prediction': ai_result}), 201


def find_serial_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if any(x in desc for x in ["cp210", "ch340", "ftdi", "arduino", "usb serial", "usb-to-uart", "cp210x"]):
            return p.device
    if ports:
        return ports[0].device
    return None

def send_serial_command(command):
    port = find_serial_port()
    if not port:
        print("No serial port found!")
        return False, "No active serial port found."
    try:
        import time
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.timeout = 1
        ser.dsrdtr = False
        ser.rtscts = False
        ser.open()
        
        # Wait 2 seconds for ESP32 to boot in case it auto-resets when the port is opened
        time.sleep(2.0)
        ser.reset_input_buffer() # Clear any bootloader message noise
        
        ser.write(f"{command}\n".encode())
        
        # Explicitly release DTR/RTS lines to ensure the ESP32 boots and runs normally
        ser.dtr = False
        ser.rts = False
        time.sleep(0.1)
        
        ser.close()
        print(f"Successfully sent command '{command}' to serial port {port}")
        return True, f"Sent override command successfully via serial port {port}."
    except Exception as e:
        error_msg = f"Error writing to serial port {port}: {e}"
        print(error_msg)
        if "PermissionError" in str(e) or "Access is denied" in str(e) or "13" in str(e):
            return False, f"Serial port {port} is busy. Please close Arduino IDE Serial Monitor or any other open serial tools, then try again!"
        return False, error_msg

@app.route('/api/pump/trigger', methods=['POST'])
def trigger_pump():
    global manual_trigger_flag, manual_trigger_pending
    manual_trigger_flag = True
    manual_trigger_pending = True
    
    success, message = send_serial_command("TRIGGER_PUMP")
    
    new_pred = PredictionHistory(
        water_needed=True,
        plant_health="Manual Override",
        soil_condition="Manual Trigger",
        recommendation="Irrigation pump manually triggered via web dashboard.",
        is_fallback_mode=False
    )
    db.session.add(new_pred)
    db.session.commit()
    
    if success:
        return jsonify({'status': 'success', 'message': message})
    else:
        # Fall back to wireless queueing if serial port fails (normal wireless operation)
        msg = "Serial port unavailable. Pump trigger queued wirelessly (will activate on next telemetry update, up to 10s delay)."
        print(f"[INFO] {msg}")
        return jsonify({'status': 'success', 'message': msg})


@app.route('/api/pump/stop', methods=['POST'])
def stop_pump():
    global manual_trigger_flag, manual_trigger_pending, manual_stop_pending
    manual_trigger_flag = False
    manual_trigger_pending = False
    manual_stop_pending = True
    
    success, message = send_serial_command("PUMP_OFF")
    
    new_pred = PredictionHistory(
        water_needed=False,
        plant_health="Manual Override",
        soil_condition="Manual Stop",
        recommendation="Irrigation pump manually stopped via web dashboard.",
        is_fallback_mode=False
    )
    db.session.add(new_pred)
    db.session.commit()
    
    if success:
        return jsonify({'status': 'success', 'message': message})
    else:
        # Fall back to wireless queueing if serial port fails (normal wireless operation)
        msg = "Serial port unavailable. Pump stop queued wirelessly (will deactivate on next telemetry update)."
        print(f"[INFO] {msg}")
        return jsonify({'status': 'success', 'message': msg})


@app.route('/api/irrigation/history', methods=['GET'])
def get_irrigation_history():
    logs = IrrigationLog.query.order_by(IrrigationLog.start_time.desc()).limit(10).all()
    return jsonify([log.to_dict() for log in logs])


@app.route('/api/alerts/resolve', methods=['POST'])
def resolve_alerts():
    Alert.query.filter_by(resolved=False).update({'resolved': True})
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/live_data', methods=['GET'])
def get_live_data():
    """ Used by the frontend dashboard to poll for the latest state """
    global _esp32_state
    
    # Backwards compatible: Main node is AGR-Node-001 (or absolute latest if node_id is missing/unassigned)
    latest_reading = SensorReading.query.filter_by(node_id='AGR-Node-001').order_by(SensorReading.timestamp.desc()).first()
    if not latest_reading:
        latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
        
    latest_pred = PredictionHistory.query.order_by(PredictionHistory.timestamp.desc()).first()
    recent_alerts = Alert.query.filter_by(resolved=False).order_by(Alert.timestamp.desc()).limit(5).all()
    
    # Main node status check (3s threshold)
    sensor_offline = False
    seconds_since_last_seen = None
    if latest_reading:
        time_diff = datetime.utcnow() - latest_reading.timestamp
        seconds_since_last_seen = int(time_diff.total_seconds())
        if time_diff > timedelta(seconds=30):
            sensor_offline = True

    # Aggregate information for all 3 nodes
    nodes_data = {}
    for node in ['AGR-Node-001', 'AGR-Node-002', 'AGR-Node-003']:
        r = SensorReading.query.filter_by(node_id=node).order_by(SensorReading.timestamp.desc()).first()
        offline = True
        node_seconds_since_last_seen = None
        if r:
            time_diff = datetime.utcnow() - r.timestamp
            node_seconds_since_last_seen = int(time_diff.total_seconds())
            if time_diff <= timedelta(seconds=30):
                offline = False
        nodes_data[node] = {
            'sensor': r.to_dict() if r else None,
            'sensor_status': 'Online' if (r and r.valid_reading and not offline) else 'Offline',
            'seconds_since_last_seen': node_seconds_since_last_seen
        }

    global last_raw_moisture
    response = {
        'sensor': latest_reading.to_dict() if latest_reading else None,
        'prediction': latest_pred.to_dict() if latest_pred else None,
        'alerts': [a.to_dict() for a in recent_alerts],
        'sensor_status': 'Online' if (latest_reading and latest_reading.valid_reading and not sensor_offline) else 'Offline / Failing',
        'fallback_active': latest_pred.is_fallback_mode if latest_pred else False,
        'usb_connected': find_serial_port() is not None,
        'seconds_since_last_seen': seconds_since_last_seen,
        'gps_valid': _esp32_state.get("gps_valid", False),
        'location_source': _esp32_state.get("location_source", "none"),
        'latitude': _settings.get("latitude", 12.9172),
        'longitude': _settings.get("longitude", 74.856),
        'location_name': _settings.get("location_name", "Unknown Location"),
        'auto_location_enabled': _settings.get("auto_location_enabled", True),
        'raw_moisture': last_raw_moisture,
        'nodes': nodes_data
    }
    return jsonify(response)


@app.route('/api/historical_data', methods=['GET'])
def get_historical_data():
    # Last 20 readings for charts
    readings = SensorReading.query.order_by(SensorReading.timestamp.desc()).limit(20).all()
    readings.reverse() # Oldest first for charts
    
    data = {
        'labels': [r.timestamp.strftime('%H:%M:%S') for r in readings],
        'moisture': [r.moisture for r in readings],
        'temperature': [r.temperature for r in readings]
    }
    return jsonify(data)

@app.route('/api/water_stats', methods=['GET'])
@login_required
def get_water_stats():
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # The ESP32 sends data every 10 seconds.
    # Each 'water_needed=True' record represents 10 seconds of watering.
    # Retrieve flow rate from settings (Liters per Minute)
    flow_rate = _settings.get("pump_flow_rate", 5.0)
    LITERS_PER_RECORD = (flow_rate / 60.0) * 10.0
    MINS_PER_RECORD = 10.0 / 60.0
    
    day_recs = PredictionHistory.query.filter(PredictionHistory.water_needed == True, PredictionHistory.timestamp >= day_ago).count()
    week_recs = PredictionHistory.query.filter(PredictionHistory.water_needed == True, PredictionHistory.timestamp >= week_ago).count()
    month_recs = PredictionHistory.query.filter(PredictionHistory.water_needed == True, PredictionHistory.timestamp >= month_ago).count()
    
    return jsonify({
        'day_liters': round(day_recs * LITERS_PER_RECORD, 1),
        'week_liters': round(week_recs * LITERS_PER_RECORD, 1),
        'month_liters': round(month_recs * LITERS_PER_RECORD, 1),
        'day_minutes': round(day_recs * MINS_PER_RECORD, 1)
    })

@app.route('/api/settings/weather', methods=['GET', 'POST'])
@login_required
def toggle_weather_prediction():
    global _settings
    if request.method == 'POST':
        data = request.json
        if 'enabled' in data:
            _settings['weather_prediction_enabled'] = bool(data['enabled'])
            save_settings(_settings)
            return jsonify({'status': 'success', 'weather_prediction_enabled': _settings['weather_prediction_enabled']})
        return jsonify({'error': 'Invalid request'}), 400
    
    return jsonify({'weather_prediction_enabled': _settings.get('weather_prediction_enabled', True)})

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def handle_settings():
    global _settings
    if request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
            
        should_geocode = False
        
        # 1. Handle city/place name geocoding if query is supplied and differs from current setting
        location_query = data.get('location_query')
        if location_query:
            clean_query = location_query.strip()
            # If the user typed a new location query, let's geocode it using Nominatim
            current_clean = _settings.get('location_name', '').replace('[Manual] ', '').replace('[GPS] ', '').replace('[IP] ', '')
            if clean_query and clean_query != current_clean:
                try:
                    headers = {'User-Agent': 'AgriSenseIrrigationSystem/1.0 (contact: shivarajakoti01@github.com)'}
                    geocode_url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(clean_query)}&format=json&limit=1"
                    resp = requests.get(geocode_url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        results = resp.json()
                        if results:
                            res = results[0]
                            _settings["latitude"] = float(res["lat"])
                            _settings["longitude"] = float(res["lon"])
                            
                            display_name = res.get("display_name", "")
                            parts = [p.strip() for p in display_name.split(",")]
                            clean_name = ", ".join(parts[:3]) if len(parts) >= 3 else display_name
                            
                            _settings["location_name"] = f"[Manual] {clean_name}"
                            _settings["auto_location_enabled"] = False
                            print(f"Successfully geocoded '{clean_query}' to: {_settings['latitude']}, {_settings['longitude']} ({_settings['location_name']})")
                        else:
                            # Fallback: Try geocoding via wttr.in nearest_area if Nominatim fails to return anything
                            try:
                                wttr_url = f"https://wttr.in/{requests.utils.quote(clean_query)}?format=j1"
                                resp_wttr = requests.get(wttr_url, headers=headers, timeout=5)
                                if resp_wttr.status_code == 200:
                                    res_wttr = resp_wttr.json()
                                    area = res_wttr.get('nearest_area', [{}])[0]
                                    if area:
                                        _settings["latitude"] = float(area["latitude"])
                                        _settings["longitude"] = float(area["longitude"])
                                        _settings["location_name"] = f"[Manual] {clean_query.title()}"
                                        _settings["auto_location_enabled"] = False
                                        print(f"Successfully geocoded '{clean_query}' via wttr.in to: {_settings['latitude']}, {_settings['longitude']}")
                                    else:
                                        return jsonify({'error': f"Location '{clean_query}' not found. Please try another place name."}), 400
                                else:
                                    return jsonify({'error': f"Geocoding service returned error {resp_wttr.status_code}"}), 503
                            except Exception:
                                return jsonify({'error': f"Location '{clean_query}' not found. Please check spelling."}), 400
                    else:
                        # Fallback: Try geocoding via wttr.in nearest_area if Nominatim service is blocked/failing
                        try:
                            wttr_url = f"https://wttr.in/{requests.utils.quote(clean_query)}?format=j1"
                            resp_wttr = requests.get(wttr_url, headers=headers, timeout=5)
                            if resp_wttr.status_code == 200:
                                res_wttr = resp_wttr.json()
                                area = res_wttr.get('nearest_area', [{}])[0]
                                if area:
                                    _settings["latitude"] = float(area["latitude"])
                                    _settings["longitude"] = float(area["longitude"])
                                    _settings["location_name"] = f"[Manual] {clean_query.title()}"
                                    _settings["auto_location_enabled"] = False
                                    print(f"Successfully geocoded '{clean_query}' via wttr.in to: {_settings['latitude']}, {_settings['longitude']}")
                                else:
                                    return jsonify({'error': f"Location '{clean_query}' not found. Please try another place name."}), 400
                            else:
                                return jsonify({'error': f"Geocoding service returned error {resp_wttr.status_code}"}), 503
                        except Exception:
                            return jsonify({'error': f"Location '{clean_query}' not found. Please check spelling."}), 400
                except Exception as e:
                    print(f"Geocoding error: {e}")
                    return jsonify({'error': f"Geocoding failed: {str(e)}"}), 500

        # Update other settings keys
        for key in ['weather_prediction_enabled', 'fallback_mode_enabled', 'retraining_frequency', 
                    'dry_threshold', 'high_temp_threshold', 'auto_location_enabled', 'pump_flow_rate',
                    'sensor_dry_raw', 'sensor_wet_raw']:
            if key in data:
                if key in ['weather_prediction_enabled', 'fallback_mode_enabled', 'auto_location_enabled']:
                    _settings[key] = bool(data[key])
                elif key in ['retraining_frequency', 'dry_threshold', 'high_temp_threshold', 'sensor_dry_raw', 'sensor_wet_raw']:
                    _settings[key] = int(data[key])
                elif key == 'pump_flow_rate':
                    _settings[key] = float(data[key])
                    
        # Update coordinates directly only if explicitly sent (e.g. from browser geolocator bypass)
        if 'latitude' in data and 'longitude' in data:
            _settings["latitude"] = float(data["latitude"])
            _settings["longitude"] = float(data["longitude"])
            _settings["auto_location_enabled"] = False
            should_geocode = True
                        
        if should_geocode:
            # Perform reverse geocoding in background
            threading.Thread(target=reverse_geocode_and_save, args=(_settings["latitude"], _settings["longitude"], "Manual"), daemon=True).start()
        else:
            save_settings(_settings)
            
        return jsonify({'status': 'success', 'settings': _settings})
        
    return jsonify(_settings)

@app.route('/api/weather', methods=['GET'])
def get_weather_forecast():
    global _settings
    lat = request.args.get('latitude', default=_settings.get("latitude", 12.9172), type=float)
    lon = request.args.get('longitude', default=_settings.get("longitude", 74.856), type=float)
    weather_enabled = _settings.get("weather_prediction_enabled", True)
    
    try:
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation_probability,temperature_2m,relative_humidity_2m&forecast_days=1"
        headers = {'User-Agent': 'AgriSenseIrrigationSystem/1.0 (contact: shivarajakoti01@github.com)'}
        resp = requests.get(weather_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"Open-Meteo API returned status code {resp.status_code}: {resp.text[:100]}")
        if resp.status_code == 200:
            wdata = resp.json()
            prob_array = wdata.get('hourly', {}).get('precipitation_probability', [])
            temp_array = wdata.get('hourly', {}).get('temperature_2m', [])
            humidity_array = wdata.get('hourly', {}).get('relative_humidity_2m', [])
            
            max_prob = max(prob_array) if prob_array else 0
            current_temp = temp_array[0] if temp_array else 25.0
            current_humidity = humidity_array[0] if humidity_array else 60.0
            
            # Determine summary
            summary = "Clear Sky"
            icon = "fa-sun text-yellow-400"
            if max_prob > 60:
                summary = "Rain Expected"
                icon = "fa-cloud-showers-heavy text-blue-400"
            elif max_prob > 20:
                summary = "Partly Cloudy"
                icon = "fa-cloud-sun text-gray-300"
            elif current_humidity > 80:
                summary = "Humid"
                icon = "fa-smog text-gray-400"
                
            return jsonify({
                'status': 'success',
                'latitude': lat,
                'longitude': lon,
                'weather_prediction_enabled': weather_enabled,
                'precipitation_probability': max_prob,
                'temperature': current_temp,
                'humidity': current_humidity,
                'summary': summary,
                'icon': icon,
                'rain_override': bool(max_prob > 0 and weather_enabled),
                'location_name': _settings.get("location_name", "auto-detected location")
            })
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        tb = traceback.format_exc()
        print(f"Weather route failed: {error_msg}\n{tb}")
        
        # Try wttr.in backup weather API
        backup = fetch_backup_weather(lat, lon)
        if backup['success']:
            return jsonify({
                'status': 'success',
                'latitude': lat,
                'longitude': lon,
                'weather_prediction_enabled': weather_enabled,
                'precipitation_probability': backup['precipitation_probability'],
                'temperature': backup['temperature'],
                'humidity': backup['humidity'],
                'summary': backup['summary'],
                'icon': backup['icon'],
                'rain_override': bool(backup['precipitation_probability'] > 0 and weather_enabled),
                'location_name': _settings.get("location_name", "auto-detected location"),
                'backup_active': True
            })
        
    # Return mockup/fallback if BOTH APIs fail
    return jsonify({
        'status': 'fallback',
        'latitude': lat,
        'longitude': lon,
        'weather_prediction_enabled': weather_enabled,
        'precipitation_probability': 85,
        'temperature': 28.0,
        'humidity': 85,
        'summary': "Thundery Showers (Demo Mode)",
        'icon': "fa-cloud-showers-heavy text-blue-400",
        'rain_override': bool(85 > 0 and weather_enabled),
        'location_name': _settings.get("location_name", "auto-detected location"),
        'error_details': error_msg if 'error_msg' in locals() else None
    })


@app.route('/api/train/synthetic', methods=['POST'])
@login_required
def train_synthetic():
    import os
    from ml_model import MODEL_PATH
    
    # Delete the existing model if it exists
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        
    # Force a retrain
    irrigation_ai.load_or_train_initial_model()
    
    return jsonify({'status': 'success', 'message': 'Model successfully trained with 1000 new synthetic data points.'})


@app.route('/api/train/database', methods=['POST'])
@login_required
def train_database():
    # Fetch historical readings from DB
    records = SensorReading.query.filter_by(valid_reading=True).order_by(SensorReading.id.desc()).all()
    
    if len(records) < 100:
        return jsonify({'status': 'error', 'message': f'Not enough valid records to train. Have {len(records)}, need at least 100.'}), 400
        
    data_dicts = [{'moisture': r.moisture, 'temperature': r.temperature} for r in records]
    success = irrigation_ai.retrain(data_dicts)
    
    if success:
        return jsonify({'status': 'success', 'message': f'Model successfully retrained using {len(data_dicts)} real database records.'})
    else:
        return jsonify({'status': 'error', 'message': 'Training failed.'}), 500

def check_and_retrain():
    """ Background task to see if we should retrain the ML model """
    with app.app_context():
        freq = _settings.get("retraining_frequency", 100)
        if freq <= 0:
            return
        readings_count = SensorReading.query.filter_by(valid_reading=True).count()
        if readings_count > 0 and readings_count % freq == 0:
            # Fetch last 500 valid records
            records = SensorReading.query.filter_by(valid_reading=True).order_by(SensorReading.id.desc()).limit(500).all()
            data_dicts = [{'moisture': r.moisture, 'temperature': r.temperature} for r in records]
            irrigation_ai.retrain(data_dicts)


# Tracking variable to ensure we only send ONE alert per offline event (no spam)
esp32_alert_sent = False

def check_esp32_offline():
    global esp32_alert_sent
    import time
    while True:
        try:
            with app.app_context():
                latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
                if latest_reading:
                    time_diff = datetime.utcnow() - latest_reading.timestamp
                    if time_diff > timedelta(minutes=2):
                        if not esp32_alert_sent:
                            # 1. Log alert into DB
                            alert_msg = "ESP32 is off, please switch it on!"
                            new_alert = Alert(message=alert_msg, alert_type="Sensor Failure")
                            db.session.add(new_alert)
                            db.session.commit()
                            
                            # 2. Trigger email dispatch in another thread
                            threading.Thread(target=send_email_alert, args=(
                                "ALERT: ESP32 Transmitter Offline",
                                "Your smart irrigation ESP32 transmitter is in OFF mode.\n\nAction Required: Go to the field and switch it on immediately!"
                            )).start()
                            
                            esp32_alert_sent = True
                            print("ESP32 Offline Alert generated and dispatched.")
                    else:
                        # Reset tracking variable when sensor is back online
                        if esp32_alert_sent:
                            esp32_alert_sent = False
                            print("ESP32 back online. Resetting alert tracker.")
        except Exception as e:
            print(f"Error in background ESP32 offline check: {e}")
        time.sleep(30) # Check every 30 seconds

if __name__ == '__main__':
    # Start the offline device detection thread
    threading.Thread(target=check_esp32_offline, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
