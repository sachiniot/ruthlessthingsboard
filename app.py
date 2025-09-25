from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
import random
import math
import os
import time
from flask_cors import CORS  
import pandas as pd
import numpy as np
import csv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)
CORS(app) 

# Global variables for ESP32 data
box_temp = None
frequency = None
power_factor = None
voltage = None
current = None
power = None
energy = None
solar_voltage = None
solar_current = None
solar_power = None
battery_percentage = None
light_intensity = None
battery_voltage = None

# Alert system variables
prev_light_intensity = 0
current_light_intensity = 0
light_slope = 0       
threshold_slope = -100
irradiance = 0
prev_battery_percent = 0
current_battery_percent = 0
battery_percent_slope=0
threshold_battery_slope =-0.05
inverter_rating = 500
last_alert_time = {}
ALERT_COOLDOWN = 300
nonessentialrelaystate=1

averageenergyconsume=2.5
predicttotalenergy=0
alert1=None
alert2=None
alert3=None
alert4=None
alert5=None
alert6=None
alert7=None
alert8=None

# Weather data cache
weather_cache = None
weather_last_updated = None
CACHE_DURATION = 3600

# Bareilly coordinates
BAREILLY_LAT = 28.3640
BAREILLY_LON = 79.4151

# Open-Meteo API
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Your app's API endpoint
APP_API_URL = "https://energy-vison.vercel.app/api/dashboard-data"

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8352010252:AAFxUDRp1ihGFQk_cu4ifQgQ8Yi4a_UVpDA')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5625474222')

THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'B1xqPBWrB9pZu4pkUU69')

# CSV Configuration - 15 seconds
CSV_FILE_PATH = 'solar_data.csv'
DATA_INTERVAL = 15
last_data_received = None

# Initialize scheduler
scheduler = BackgroundScheduler()

def init_csv_file():
    """Initialize CSV file with headers if it doesn't exist"""
    try:
        if not os.path.exists(CSV_FILE_PATH):
            headers = [
                'timestamp', 'box_temp', 'frequency', 'power_factor', 'voltage', 
                'current', 'power', 'energy', 'solar_voltage', 'solar_current',
                'solar_power', 'battery_percentage', 'light_intensity', 
                'battery_voltage', 'temperature', 'humidity', 'cloud_cover',
                'wind_speed', 'precipitation', 'weather_code', 'alert1', 'alert2',
                'alert3', 'alert4', 'alert5', 'alert6', 'alert7', 'alert8',
                'nonessentialrelaystate', 'data_source'
            ]
            
            with open(CSV_FILE_PATH, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            print(f"✅ CSV file initialized: {CSV_FILE_PATH}")
        else:
            print(f"✅ CSV file already exists: {CSV_FILE_PATH}")
    except Exception as e:
        print(f"❌ Error initializing CSV file: {str(e)}")

def save_to_csv(esp32_data, weather_data, alerts):
    """Save current data to CSV file"""
    try:
        timestamp = datetime.now().isoformat()
        
        row_data = {
            'timestamp': timestamp,
            'box_temp': esp32_data.get('box_temp', np.nan),
            'frequency': esp32_data.get('frequency', np.nan),
            'power_factor': esp32_data.get('power_factor', np.nan),
            'voltage': esp32_data.get('voltage', np.nan),
            'current': esp32_data.get('current', np.nan),
            'power': esp32_data.get('power', np.nan),
            'energy': esp32_data.get('energy', np.nan),
            'solar_voltage': esp32_data.get('solar_voltage', np.nan),
            'solar_current': esp32_data.get('solar_current', np.nan),
            'solar_power': esp32_data.get('solar_power', np.nan),
            'battery_percentage': esp32_data.get('battery_percentage', np.nan),
            'light_intensity': esp32_data.get('light_intensity', np.nan),
            'battery_voltage': esp32_data.get('battery_voltage', np.nan),
            'data_source': 'esp32_live'
        }
        
        if 'error' not in weather_data:
            current_weather = weather_data.get('current', {})
            row_data.update({
                'temperature': current_weather.get('temperature', np.nan),
                'humidity': current_weather.get('humidity', np.nan),
                'cloud_cover': current_weather.get('cloud_cover', np.nan),
                'wind_speed': current_weather.get('wind_speed', np.nan),
                'precipitation': current_weather.get('precipitation', np.nan),
                'weather_code': current_weather.get('weather_code', np.nan),
            })
        else:
            row_data.update({
                'temperature': np.nan, 'humidity': np.nan, 'cloud_cover': np.nan,
                'wind_speed': np.nan, 'precipitation': np.nan, 'weather_code': np.nan,
            })
        
        row_data.update({
            'alert1': alerts.get('alert1', ''), 'alert2': alerts.get('alert2', ''),
            'alert3': alerts.get('alert3', ''), 'alert4': alerts.get('alert4', ''),
            'alert5': alerts.get('alert5', ''), 'alert6': alerts.get('alert6', ''),
            'alert7': alerts.get('alert7', ''), 'alert8': alerts.get('alert8', ''),
            'nonessentialrelaystate': esp32_data.get('nonessentialrelaystate', 1)
        })
        
        with open(CSV_FILE_PATH, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=row_data.keys())
            writer.writerow(row_data)
        
        print(f"✅ Data saved to CSV: {timestamp}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving to CSV: {str(e)}")
        return False

def save_missing_data_entry():
    """Save NaN entry when ESP32 fails to send data"""
    try:
        timestamp = datetime.now().isoformat()
        
        row_data = {
            'timestamp': timestamp,
            'box_temp': np.nan, 'frequency': np.nan, 'power_factor': np.nan,
            'voltage': np.nan, 'current': np.nan, 'power': np.nan, 'energy': np.nan,
            'solar_voltage': np.nan, 'solar_current': np.nan, 'solar_power': np.nan,
            'battery_percentage': np.nan, 'light_intensity': np.nan, 'battery_voltage': np.nan,
            'temperature': np.nan, 'humidity': np.nan, 'cloud_cover': np.nan,
            'wind_speed': np.nan, 'precipitation': np.nan, 'weather_code': np.nan,
            'alert1': '', 'alert2': '', 'alert3': '', 'alert4': '', 'alert5': '',
            'alert6': '', 'alert7': '', 'alert8': '', 'nonessentialrelaystate': 1,
            'data_source': 'missing_data'
        }
        
        with open(CSV_FILE_PATH, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=row_data.keys())
            writer.writerow(row_data)
        
        print(f"⚠️ Missing data entry saved: {timestamp}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving missing data entry: {str(e)}")
        return False

def check_missing_data():
    """Check if we haven't received data and save NaN entry every 15 seconds"""
    global last_data_received
    
    if last_data_received is None:
        last_data_received = datetime.now()
        return
    
    time_since_last_data = (datetime.now() - last_data_received).total_seconds()
    
    if time_since_last_data >= 15:
        print(f"⚠️ No data received for {time_since_last_data} seconds. Saving NaN entry.")
        save_missing_data_entry()
        last_data_received = datetime.now()

def start_background_scheduler():
    """Start the background scheduler for data monitoring"""
    try:
        scheduler.add_job(
            func=check_missing_data,
            trigger=IntervalTrigger(seconds=15),
            id='missing_data_check',
            name='Check for missing ESP32 data every 15 seconds',
            replace_existing=True
        )
        
        scheduler.start()
        print("✅ Background scheduler started for 15-second data monitoring")
    except Exception as e:
        print(f"❌ Error starting scheduler: {str(e)}")

def send_to_app(data):
    """Send data to your app's API endpoint"""
    max_retries = 2
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            headers = {'Content-Type': 'application/json', 'User-Agent': 'SolarMonitor/1.0'}
            verify_ssl = attempt == 0
            
            response = requests.post(APP_API_URL, json=data, headers=headers, timeout=5, verify=verify_ssl)
            response.raise_for_status()
            print(f"✅ Successfully sent to app")
            return True
            
        except requests.exceptions.SSLError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False
        except Exception as e:
            return False
    
    return False

@app.route('/')
def home():
    return jsonify({"message": "Solar Monitoring System API", "status": "active"})

def send_to_thingsboard(device_token, telemetry_data):
    try:
        if THINGSBOARD_HOST == 'http://localhost:8080' or device_token == 'YOUR_DEVICE_ACCESS_TOKEN':
            return False
            
        url = f"{THINGSBOARD_HOST}/api/v1/{device_token}/telemetry"
        telemetry_with_ts = {
            "ts": int(datetime.now().timestamp() * 1000),
            "values": telemetry_data
        }
        
        response = requests.post(url, json=telemetry_with_ts, headers={'Content-Type': 'application/json'}, timeout=10)
        response.raise_for_status()
        return True
        
    except Exception as e:
        return False

def get_weather_data(force_refresh=False):
    global weather_cache, weather_last_updated
    
    if not force_refresh and weather_cache and weather_last_updated:
        cache_age = (datetime.now() - weather_last_updated).total_seconds()
        if cache_age < CACHE_DURATION:
            return weather_cache
    
    try:
        params = {
            'latitude': BAREILLY_LAT, 'longitude': BAREILLY_LON,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m',
            'hourly': 'temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m',
            'timezone': 'auto', 'forecast_days': 2
        }
        
        response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        current = data.get('current', {})
        current_weather = {
            'temperature': current.get('temperature_2m'),
            'feels_like': current.get('apparent_temperature'),
            'humidity': current.get('relative_humidity_2m'),
            'cloud_cover': current.get('cloud_cover'),
            'wind_speed': current.get('wind_speed_10m'),
            'precipitation': current.get('precipitation'),
            'weather_code': current.get('weather_code'),
            'timestamp': datetime.now().isoformat()
        }
        
        weather_data = {
            'current': current_weather,
            'location': {'lat': BAREILLY_LAT, 'lon': BAREILLY_LON, 'name': 'Bareilly, India'},
            'last_updated': datetime.now().isoformat(),
            'source': 'open-meteo'
        }
        
        weather_cache = weather_data
        weather_last_updated = datetime.now()
        
        return weather_data
        
    except Exception as e:
        return {'error': f"Weather API error: {str(e)}"}

def send_telegram_alert(message, alert_type="general"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"error": "Telegram credentials not configured"}
    
    current_time = datetime.now().timestamp()
    last_sent = last_alert_time.get(alert_type, 0)
    
    if current_time - last_sent < ALERT_COOLDOWN:
        return {"status": "skipped", "reason": "cooldown"}
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    formatted_message = f"🚨 Solar Monitor Alert 🚨\n\n{message}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": formatted_message}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        last_alert_time[alert_type] = current_time
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def check_alerts():
    global alert1, alert2, alert3, alert4, alert5, nonessentialrelaystate
    try:
        alert1 = alert2 = alert3 = alert4 = alert5 = None

        if current_battery_percent is None or light_intensity is None or solar_voltage is None or solar_current is None:
            return

        if current_battery_percent == 100:
            alert1 = "Overcharge!"
            nonessentialrelaystate=1
            send_telegram_alert(alert1, "battery")
        if current_battery_percent < 10:
            alert1 = "Discharge!"
            nonessentialrelaystate=0
            send_telegram_alert(alert1, "battery")

        irradiance = light_intensity / 120
        solar_power = (solar_voltage * solar_current) / 1000
        
        if 900 <= irradiance < 1200 and not (0.31 <= solar_power <= 0.37):
            alert2 = "solar panel low efficiency!"
            nonessentialrelaystate=0
            send_telegram_alert(alert2, "panel alert")
        elif 600 <= irradiance < 900 and not (0.22 <= solar_power <= 0.30):
            alert2 = "solar panel low efficiency!"
            nonessentialrelaystate=0
            send_telegram_alert(alert2, "panel alert")
        elif 350 <= irradiance < 600 and not (0.14 <= solar_power <= 0.22):
            alert2 = "solar panel low efficiency!"
            nonessentialrelaystate=0
            send_telegram_alert(alert2, "panel alert")
        elif 150 <= irradiance < 350 and not (0.05 <= solar_power <= 0.14):
            alert2 = "solar panel low efficiency!"
            nonessentialrelaystate=0
            send_telegram_alert(alert2, "panel alert")
        elif irradiance < 100 and not (0.0 <= solar_power <= 0.05):
            alert2 = "solar panel low efficiency!"
            nonessentialrelaystate=0
            send_telegram_alert(alert2, "panel alert")

        if voltage is not None and current is not None and (voltage * current / 1000) > inverter_rating:
            alert3 = "Overload!"
            nonessentialrelaystate=0
            send_telegram_alert(alert3, "load alert")

        if prev_light_intensity is not None:
            current_light_intensity = irradiance
            timegap = 300
            light_slope = (current_light_intensity - prev_light_intensity) / timegap
            if light_slope < threshold_slope:
                alert4 = "Sudden drop in sun light!"
                nonessentialrelaystate=0
                send_telegram_alert(alert4, "light intensity alert")

        if solar_power != 0 and prev_battery_percent is not None:
            timegap = 300
            battery_percent_slope = (current_battery_percent - prev_battery_percent) / timegap
            if battery_percent_slope < threshold_battery_slope:
                alert5 = "Battery not charging!"
                nonessentialrelaystate=0
                send_telegram_alert(alert5, "battery alert")

    except Exception as e:
        print(f"❌ Error in alert system: {str(e)}")

def predictionalerts():
    global alert6, alert7, alert8, nonessentialrelaystate
    predicttotalenergy=random.random()*4
    try:
        alert6=alert7=alert8=None
        if averageenergyconsume > predicttotalenergy:
            alert6 = "consumption is higher than expected solar generation!"
            send_telegram_alert("consumption is higher than expected solar generation!","prediction alert")
            if battery_percentage < 40:
                alert7 = "Battery is low. Risk of blackout in future!"
                send_telegram_alert("Battery is low. Risk of blackout in future!","prediction alert")
                nonessentialrelaystate=0

        if averageenergyconsume < predicttotalenergy:
            if battery_percentage > 40 and battery_percentage < 80:
                nonessentialrelaystate=1
            if battery_percentage > 80:
                alert8 = "Battery may overcharge in next upcoming hours!"
                nonessentialrelaystate=1
                send_telegram_alert("Battery may overcharge in next upcoming hours!","prediction alert")
    except Exception as e:
        print(f"❌ Error in prediction alerts: {str(e)}")

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    global box_temp, frequency, power_factor, voltage, current, power, energy
    global solar_voltage, solar_current, solar_power, battery_percentage
    global light_intensity, battery_voltage, prev_light_intensity, current_light_intensity
    global prev_battery_percent, current_battery_percent, nonessentialrelaystate, last_data_received

    print("📨 Received POST request to /esp32-data")
    last_data_received = datetime.now()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        box_temp = data.get('box_temp') or data.get('BoxTemperature')
        frequency = data.get('frequency') or data.get('Frequency')
        power_factor = data.get('power_factor') or data.get('PowerFactor')
        voltage = data.get('voltage') or data.get('Voltage')
        current = data.get('current') or data.get('Current')
        power = data.get('power') or data.get('Power')
        energy = data.get('energy') or data.get('Energy')
        solar_voltage = data.get('solar_voltage') or data.get('SolarVoltage')
        solar_current = data.get('solar_current') or data.get('solarCurrent')
        solar_power = data.get('solar_power') or data.get('solarPower')
        battery_percentage = data.get('battery_percentage') or data.get('batteryPercentage')
        light_intensity = data.get('light_intensity') or data.get('lightIntensity')
        battery_voltage = data.get('battery_voltage') or data.get('batteryVoltage')
        
        prev_battery_percent = current_battery_percent
        current_battery_percent = battery_percentage if battery_percentage else 0
        prev_light_intensity = current_light_intensity
        current_light_intensity = light_intensity if light_intensity else 0

        check_alerts()
        predictionalerts()
        
        esp32_data_for_csv = {
            'box_temp': box_temp, 'frequency': frequency, 'power_factor': power_factor,
            'voltage': voltage, 'current': current, 'power': power, 'energy': energy,
            'solar_voltage': solar_voltage, 'solar_current': solar_current, 'solar_power': solar_power,
            'battery_percentage': battery_percentage, 'light_intensity': light_intensity,
            'battery_voltage': battery_voltage, 'nonessentialrelaystate': nonessentialrelaystate
        }
        
        weather_data = get_weather_data(force_refresh=False)
        alerts_data = {
            'alert1': alert1, 'alert2': alert2, 'alert3': alert3, 'alert4': alert4,
            'alert5': alert5, 'alert6': alert6, 'alert7': alert7, 'alert8': alert8
        }
        
        import threading
        csv_thread = threading.Thread(target=save_to_csv, args=(esp32_data_for_csv, weather_data, alerts_data))
        csv_thread.daemon = True
        csv_thread.start()
        
        if any([box_temp, power, solar_power]):
            telemetry_data = {
                "power": power, "solar_power": solar_power, "battery_percentage": battery_percentage,
                "voltage": voltage, "current": current, "solar_voltage": solar_voltage,
                "solar_current": solar_current, "light_intensity": light_intensity,
                "energy": energy, "frequency": frequency, "nonessentialrelaystate": nonessentialrelaystate,
                "alert1": alert1, "alert2": alert2, "alert3": alert3, "alert4": alert4,
                "alert5": alert5, "alert6": alert6, "alert7": alert7, "alert8": alert8
            }
            send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        combined_data = {
            "esp32_data": esp32_data_for_csv,
            "alerts": alerts_data,
            "weather_data": weather_data if 'error' not in weather_data else {"error": weather_data['error']},
            "timestamp": datetime.now().isoformat()
        }
        
        app_thread = threading.Thread(target=send_to_app, args=(combined_data,))
        app_thread.daemon = True
        app_thread.start()
        
        if 'error' in weather_data:
            response_data = {
                "message": "Data received successfully (weather data unavailable)", 
                "status": "ok", "weather_available": False, "weather_error": weather_data['error']
            }
        else:
            response_data = {
                "message": "Data received successfully", "nonessentialrelaystate": nonessentialrelaystate,
                "alert1": alert1, "alert2": alert2, "alert3": alert3, "alert4": alert4,
                "alert5": alert5, "alert6": alert6, "alert7": alert7, "alert8": alert8,
                "status": "ok", "weather_available": True,
                "weather": {
                    "temperature": weather_data['current'].get('temperature'),
                    "humidity": weather_data['current'].get('humidity'),
                    "cloud_cover": weather_data['current'].get('cloud_cover'),
                    "wind_speed": weather_data['current'].get('wind_speed'),
                    "precipitation": weather_data['current'].get('precipitation'),
                    "weather_code": weather_data['current'].get('weather_code'),
                    "feels_like": weather_data['current'].get('feels_like'),
                    "timestamp": weather_data['current'].get('timestamp')
                },
                "location": {"lat": BAREILLY_LAT, "lon": BAREILLY_LON, "name": "Bareilly, India"}
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/csv-data', methods=['GET'])
def get_csv_data():
    """Endpoint for model to fetch CSV data"""
    try:
        if not os.path.exists(CSV_FILE_PATH):
            return jsonify({"error": "CSV file not found"}), 404
        
        df = pd.read_csv(CSV_FILE_PATH)
        data = df.to_dict('records')
        
        return jsonify({
            "data": data,
            "total_records": len(data),
            "last_updated": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/csv-stats', methods=['GET'])
def get_csv_stats():
    """Get statistics about the CSV data"""
    try:
        if not os.path.exists(CSV_FILE_PATH):
            return jsonify({"error": "CSV file not found"}), 404
        
        df = pd.read_csv(CSV_FILE_PATH)
        
        stats = {
            "total_records": len(df),
            "data_sources": df['data_source'].value_counts().to_dict(),
            "missing_data_count": len(df[df['data_source'] == 'missing_data']),
            "date_range": {"start": df['timestamp'].min(), "end": df['timestamp'].max()},
            "columns": list(df.columns)
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "csv": "active"}), 200

# Initialize the system when the app starts
@app.before_request
def initialize_system():
    if not hasattr(app, 'initialized'):
        init_csv_file()
        start_background_scheduler()
        app.initialized = True
        print("✅ Solar Monitoring System Initialized")

if __name__ == '__main__':
    init_csv_file()
    start_background_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    application = app
