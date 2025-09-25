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
threshold_slope = -100   # Set appropriate threshold for sudden light drop
irradiance = 0
prev_battery_percent = 0
current_battery_percent = 0
battery_percent_slope=0
threshold_battery_slope =-0.05   # Set appropriate threshold for battery charging rate
inverter_rating = 500  # Set your inverter rating in watts
last_alert_time = {}
ALERT_COOLDOWN = 300  # 5 minutes in seconds
nonessentialrelaystate=1

averageenergyconsume=2.5  # in same interval in which total predict energy calculated calculated it like avg power of one day then avg power of this time-?
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
CACHE_DURATION = 3600  # 1 hour

# Bareilly coordinates
BAREILLY_LAT = 28.3640
BAREILLY_LON = 79.4151

# Open-Meteo API
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Your app's API endpoint
APP_API_URL = "https://energy-vison.vercel.app/api/dashboard-data"

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8352010252:AAFxUDRp1ihGFQk_cu4ifQgQ8Yi4a_UVpDA')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5625474222')
# ThingsBoard Configuration
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'B1xqPBWrB9pZu4pkUU69')

# CSV Configuration
CSV_FILE_PATH = 'solar_data.csv'
DATA_INTERVAL = 15  # 15  in seconds
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
        # Prepare data row
        timestamp = datetime.now().isoformat()
        
        # ESP32 data (handle missing values)
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
        
        # Weather data
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
                'temperature': np.nan,
                'humidity': np.nan,
                'cloud_cover': np.nan,
                'wind_speed': np.nan,
                'precipitation': np.nan,
                'weather_code': np.nan,
            })
        
        # Alerts
        row_data.update({
            'alert1': alerts.get('alert1', ''),
            'alert2': alerts.get('alert2', ''),
            'alert3': alerts.get('alert3', ''),
            'alert4': alerts.get('alert4', ''),
            'alert5': alerts.get('alert5', ''),
            'alert6': alerts.get('alert6', ''),
            'alert7': alerts.get('alert7', ''),
            'alert8': alerts.get('alert8', ''),
            'nonessentialrelaystate': esp32_data.get('nonessentialrelaystate', 1)
        })
        
        # Write to CSV
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
        
        # Create row with NaN values
        row_data = {
            'timestamp': timestamp,
            'box_temp': np.nan,
            'frequency': np.nan,
            'power_factor': np.nan,
            'voltage': np.nan,
            'current': np.nan,
            'power': np.nan,
            'energy': np.nan,
            'solar_voltage': np.nan,
            'solar_current': np.nan,
            'solar_power': np.nan,
            'battery_percentage': np.nan,
            'light_intensity': np.nan,
            'battery_voltage': np.nan,
            'temperature': np.nan,
            'humidity': np.nan,
            'cloud_cover': np.nan,
            'wind_speed': np.nan,
            'precipitation': np.nan,
            'weather_code': np.nan,
            'alert1': '',
            'alert2': '',
            'alert3': '',
            'alert4': '',
            'alert5': '',
            'alert6': '',
            'alert7': '',
            'alert8': '',
            'nonessentialrelaystate': 1,
            'data_source': 'missing_data'
        }
        
        # Write to CSV
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
        # First run, initialize
        last_data_received = datetime.now()
        return
    
    time_since_last_data = (datetime.now() - last_data_received).total_seconds()
    
    # Check every 15 seconds if data is missing (CHANGED FROM DATA_INTERVAL)
    if time_since_last_data >= 15:  # CHANGED FROM DATA_INTERVAL
        print(f"⚠️ No data received for {time_since_last_data} seconds. Saving NaN entry.")
        save_missing_data_entry()
        # Update last received to prevent multiple entries
        last_data_received = datetime.now() + timedelta(seconds=15)  # Schedule next check

def start_background_scheduler():
    """Start the background scheduler for data monitoring"""
    try:
        # Schedule missing data check every 15 seconds (CHANGED FROM 1 minute)
        scheduler.add_job(
            func=check_missing_data,
            trigger=IntervalTrigger(seconds=15),  # CHANGED FROM minutes=1
            id='missing_data_check',
            name='Check for missing ESP32 data every 15 seconds',
            replace_existing=True
        )
        
        scheduler.start()
        print("✅ Background scheduler started for 15-second data monitoring")  # UPDATED MESSAGE
    except Exception as e:
        print(f"❌ Error starting scheduler: {str(e)}")
        

def send_to_app(data):
    """Send data to your app's API endpoint with detailed debugging"""
    max_retries = 2
    retry_delay = 1
    
    print(f"🔍 Attempting to connect to: {APP_API_URL}")
    
    # Test basic connectivity first
    try:
        # Test DNS resolution
        import socket
        hostname = APP_API_URL.split('//')[1].split('/')[0]
        ip_address = socket.gethostbyname(hostname)
        print(f"✅ DNS resolved: {hostname} → {ip_address}")
        
        # Test basic connectivity
        test_response = requests.head(APP_API_URL, timeout=3)
        print(f"✅ Basic connectivity: Status {test_response.status_code}")
        
        if test_response.status_code >= 400:
            print(f"⚠️ App API responded with error: {test_response.status_code}")
            return False
            
    except socket.gaierror:
        print(f"❌ DNS resolution failed for {hostname}")
        return False
    except requests.exceptions.SSLError:
        print(f"❌ SSL certificate error - trying without verification")
        # We'll handle this in the retry loop
    except requests.exceptions.RequestException as e:
        print(f"❌ Connectivity test failed: {str(e)}")
        return False
    
    for attempt in range(max_retries):
        try:
            print(f"📤 Sending data to app (attempt {attempt + 1}/{max_retries})")
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'SolarMonitor/1.0'
            }
            
            # Try with and without SSL verification
            verify_ssl = attempt == 0  # Verify on first attempt, skip on retry
            
            response = requests.post(
                APP_API_URL, 
                json=data, 
                headers=headers, 
                timeout=5,
                verify=verify_ssl
            )
            
            print(f"✅ App responded with status: {response.status_code}")
            response.raise_for_status()
            
            print(f"✅ Successfully sent to app")
            return True
            
        except requests.exceptions.SSLError:
            print(f"❌ SSL error (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print("❌ All attempts failed due to SSL issues")
                return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Timeout (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print("❌ All attempts timed out")
                return False
                
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection error: {str(e)}")
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {str(e)}")
            return False
            
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            return False
    
    return False

@app.route('/')
def home():
    return jsonify({
        "message": "Solar Monitoring System API",
        "endpoints": {
            "POST /esp32-data": "Receive data from ESP32",
            "GET /weather": "Get weather data",
            "GET /hourly-forecast": "Get hourly weather forecast",
            "GET /combined-data": "Get combined ESP32 and weather data",
            "GET /test-open-meteo": "Test Open-Meteo API connection",
            "GET /test-params": "Check current parameter values",
            "POST /send-to-thingsboard": "Send data to ThingsBoard",
            "POST /resend-weather": "Resend weather data to ThingsBoard",
            "POST /alert": "Send alert to Telegram",
            "POST /send-to-app": "Send data to your app",
            "GET /api/csv-data": "Get CSV data for model",
            "GET /api/csv-stats": "Get CSV statistics"
        },
        "thingsboard_config": {
            "host": THINGSBOARD_HOST,
            "device_token": THINGSBOARD_ACCESS_TOKEN,
            "status": "configured" if THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN' else "not_configured"
        },
        "telegram_config": {
            "bot_configured": TELEGRAM_BOT_TOKEN is not None,
            "chat_id_configured": TELEGRAM_CHAT_ID is not None
        },
        "app_config": {
            "app_url": APP_API_URL,
            "status": "configured"
        },
        "csv_config": {
            "csv_file": CSV_FILE_PATH,
            "status": "active"
        },
        "status": "active"
    })

def send_to_thingsboard(device_token, telemetry_data):
    try:
        if THINGSBOARD_HOST == 'http://localhost:8080' or device_token == 'YOUR_DEVICE_ACCESS_TOKEN':
            print("⚠️ ThingsBoard not configured - skipping send")
            return False
            
        url = f"{THINGSBOARD_HOST}/api/v1/{device_token}/telemetry"
        telemetry_with_ts = {
            "ts": int(datetime.now().timestamp() * 1000),
            "values": telemetry_data
        }
        
        headers = {'Content-Type': 'application/json'}
        
        print(f"📤 Sending to ThingsBoard: {url}")
        response = requests.post(url, json=telemetry_with_ts, headers=headers, timeout=10)
        response.raise_for_status()
        
        print(f"✅ Successfully sent to ThingsBoard (Status: {response.status_code})")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ThingsBoard API error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error sending to ThingsBoard: {str(e)}")
        send_telegram_alert("Error sending to thingsboard","server error")
        return False

def resend_weather_to_thingsboard():
    try:
        weather_data = get_weather_data(force_refresh=False)
        if 'error' in weather_data:
            print(f"❌ Cannot resend weather data: {weather_data['error']}")
            send_telegram_alert("Cannot resend weatherdata!","server error")
            return False
        
        telemetry_data = {
            "temperature": weather_data['current'].get('temperature'),
            "humidity": weather_data['current'].get('humidity'),
            "cloud_cover": weather_data['current'].get('cloud_cover'),
            "wind_speed": weather_data['current'].get('wind_speed'),
            "precipitation": weather_data['current'].get('precipitation'),
            "weather_code": weather_data['current'].get('weather_code'),
            "location_lat": BAREILLY_LAT,
            "location_lon": BAREILLY_LON,
            "data_source": "open-meteo"
        }
        
        print(f"🔄 Resending weather data to ThingsBoard")
        success = send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        if success:
            print("✅ Weather data resent successfully to ThingsBoard!")
        else:
            print("❌ Failed to resend weather data to ThingsBoard")
            send_telegram_alert("Failed to resend weather data to Thingsboard","server errror")
            
        return success
        
    except Exception as e:
        error_msg = f"Error resending weather data: {str(e)}"
        print(f"❌ {error_msg}")
        return False

@app.route('/resend-weather', methods=['POST'])
def resend_weather():
    try:
        success = resend_weather_to_thingsboard()
        return jsonify({
            "success": success,
            "message": "Weather data resent to ThingsBoard" if success else "Failed to resend weather data"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/send-to-thingsboard', methods=['POST'])
def send_data_to_thingsboard():
    try:
        data = request.get_json() or {}
        device_type = data.get('device_type', 'weather')
        
        if device_type == 'weather':
            success = resend_weather_to_thingsboard()
            return jsonify({"success": success, "device": "weather", "message": "Weather data sent to ThingsBoard"})
        elif device_type == 'solar':
            if any([box_temp, power, solar_power]):
                telemetry_data = {
                    "box_temperature": box_temp,
                    "power": power,
                    "solar_power": solar_power,
                    "battery_percentage": battery_percentage,
                    "voltage": voltage,
                    "current": current,
                    "light_intensity": light_intensity
                }
                success = send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
                return jsonify({"success": success, "device": "solar", "data_sent": telemetry_data})
        
        return jsonify({"error": "No data available to send"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    global box_temp, frequency, power_factor, voltage, current, power, energy
    global solar_voltage, solar_current, solar_power, battery_percentage
    global light_intensity, battery_voltage, prev_light_intensity, current_light_intensity
    global prev_battery_percent, current_battery_percent, nonessentialrelaystate, last_data_received

    print("📨 Received POST request to /esp32-data")
    
    # Update last data received timestamp
    last_data_received = datetime.now()
    
    try:
        data = request.get_json()
        if not data:
            send_telegram_alert("No JSON data recieved","data error")
            return jsonify({"error": "No JSON data received"}), 400
        
        print(f"✅ JSON data received: {data}")
        
        # Update ESP32 data variables
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
        
        print(f"✅ Box Temp: {box_temp}°C, Power: {power}W, Solar: {solar_power}W, Battery: {battery_percentage}%")
        
        # Update alert system variables
        prev_battery_percent = current_battery_percent
        current_battery_percent = battery_percentage if battery_percentage else 0
        
        prev_light_intensity = current_light_intensity
        current_light_intensity = light_intensity if light_intensity else 0

        check_alerts()
        predictionalerts()
        
        # Prepare ESP32 data for CSV
        esp32_data_for_csv = {
            'box_temp': box_temp,
            'frequency': frequency,
            'power_factor': power_factor,
            'voltage': voltage,
            'current': current,
            'power': power,
            'energy': energy,
            'solar_voltage': solar_voltage,
            'solar_current': solar_current,
            'solar_power': solar_power,
            'battery_percentage': battery_percentage,
            'light_intensity': light_intensity,
            'battery_voltage': battery_voltage,
            'nonessentialrelaystate': nonessentialrelaystate
        }
        
        # Get current weather data
        weather_data = get_weather_data(force_refresh=False)
        
        # Prepare alerts data
        alerts_data = {
            'alert1': alert1,
            'alert2': alert2,
            'alert3': alert3,
            'alert4': alert4,
            'alert5': alert5,
            'alert6': alert6,
            'alert7': alert7,
            'alert8': alert8
        }
        
        # Save to CSV (non-blocking)
        import threading
        csv_thread = threading.Thread(target=save_to_csv, args=(esp32_data_for_csv, weather_data, alerts_data))
        csv_thread.daemon = True
        csv_thread.start()
        
        # Send to ThingsBoard
        if any([box_temp, power, solar_power]):
            telemetry_data = {
                
                "power": power,
                "solar_power": solar_power,
                "battery_percentage": battery_percentage,
                "voltage": voltage,
                "current": current,
                "solar_voltage":solar_voltage,
                "solar_current":solar_current,
                "light_intensity": light_intensity,
                "energy": energy,
                "frequency": frequency,
                "nonessentialrelaystate":nonessentialrelaystate,
                "alert1":alert1,
                "alert2":alert2,
                "alert3":alert3,
                "alert4":alert4,
                "alert5":alert5,
                "alert6":alert6,
                "alert7":alert7,
                "alert8":alert8,
      
            }
            send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        # Get current weather data
        weather_data = get_weather_data(force_refresh=False)
        
        # Prepare combined data for your app
        combined_data = {
            "esp32_data": {
                "box_temp": box_temp,
                "power": power,
                "solar_power": solar_power,
                "battery_percentage": battery_percentage,
                "voltage": voltage,
                "current": current,
                "solar_voltage": solar_voltage,
                "solar_current": solar_current,
                "light_intensity": light_intensity,
                "energy": energy,
                "frequency": frequency,
                "nonessentialrelaystate": nonessentialrelaystate
            },
            "alerts": {
                "alert1": alert1,
                "alert2": alert2,
                "alert3": alert3,
                "alert4": alert4,
                "alert5": alert5,
                "alert6": alert6,
                "alert7": alert7,
                "alert8": alert8
            },
            "weather_data": weather_data if 'error' not in weather_data else {"error": weather_data['error']},
            "timestamp": datetime.now().isoformat()
        }
        
        # Send combined data to your app (non-blocking)
        import threading
        thread = threading.Thread(target=send_to_app, args=(combined_data,))
        thread.daemon = True
        thread.start()
        
        # FIXED: Handle case where weather data contains error
        if 'error' in weather_data:
            # Return basic success response without weather data
            response_data = {
                "message": "Data received successfully (weather data unavailable)", 
                "status": "ok",
                "weather_available": False,
                "weather_error": weather_data['error']
            }
        else:
            # Return response with weather data
            response_data = {
                "message": "Data received successfully",
                "nonessentialrelaystate":nonessentialrelaystate,
                "alert1":alert1,
                "alert2":alert2,
                "alert3":alert3,
                "alert4":alert4,
                "alert5":alert5,
                "alert6":alert6,
                "alert7":alert7,
                "alert8":alert8,
                
                "status": "ok",
                "weather_available": True,
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
                "location": {
                    "lat": BAREILLY_LAT,
                    "lon": BAREILLY_LON,
                    "name": "Bareilly, India"
                }
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/test-app-connection', methods=['GET'])
def test_app_connection():
    """Test connection to the app API"""
    try:
        print(f"🔍 Testing connection to: {APP_API_URL}")
        
        # Test DNS resolution
        import socket
        from urllib.parse import urlparse
        
        parsed_url = urlparse(APP_API_URL)
        hostname = parsed_url.hostname
        
        try:
            ip_address = socket.gethostbyname(hostname)
            dns_status = f"✅ DNS resolved: {hostname} → {ip_address}"
        except socket.gaierror:
            dns_status = f"❌ DNS failed for: {hostname}"
            return jsonify({"error": dns_status}), 500
        
        # Test HTTP connection
        try:
            response = requests.head(APP_API_URL, timeout=5, allow_redirects=True)
            http_status = f"✅ HTTP connection: Status {response.status_code}"
        except requests.exceptions.SSLError:
            http_status = "⚠️ SSL error (but connection established)"
            # Try without SSL verification
            try:
                response = requests.head(APP_API_URL, timeout=5, verify=False)
                http_status = f"⚠️ HTTP connection (no SSL): Status {response.status_code}"
            except Exception as e:
                http_status = f"❌ HTTP failed: {str(e)}"
                return jsonify({"error": http_status}), 500
        except requests.exceptions.RequestException as e:
            http_status = f"❌ HTTP failed: {str(e)}"
            return jsonify({"error": http_status}), 500
        
        # Test POST request
        try:
            test_data = {"test": "connection", "timestamp": datetime.now().isoformat()}
            response = requests.post(APP_API_URL, json=test_data, timeout=5)
            post_status = f"✅ POST test: Status {response.status_code}"
        except Exception as e:
            post_status = f"❌ POST failed: {str(e)}"
        
        return jsonify({
            "dns": dns_status,
            "http": http_status,
            "post": post_status,
            "app_url": APP_API_URL
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-params', methods=['GET'])
def test_params():
    return jsonify({
        "box_temp": box_temp,
        "power": power,
        "solar_power": solar_power,
        "battery_percentage": battery_percentage,
        "voltage": voltage,
        "current": current,
        "light_intensity": light_intensity,
        "energy": energy,
        "frequency": frequency
    })

@app.route('/check-config', methods=['GET'])
def check_config():
    return jsonify({
        "telegram_bot_token_configured": TELEGRAM_BOT_TOKEN is not None,
        "telegram_chat_id_configured": TELEGRAM_CHAT_ID is not None,
        "thingsboard_configured": THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN'
    })

def get_weather_data(force_refresh=False):
    global weather_cache, weather_last_updated
    
    if not force_refresh and weather_cache and weather_last_updated:
        cache_age = (datetime.now() - weather_last_updated).total_seconds()
        if cache_age < CACHE_DURATION:
            print(f"🌤️ Using cached weather data (age: {int(cache_age)}s)")
            return weather_cache
    
    try:
        print("🌤️ Fetching fresh weather data from Open-Meteo...")
        params = {
            'latitude': BAREILLY_LAT,
            'longitude': BAREILLY_LON,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m',
            'hourly': 'temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m',
            'timezone': 'auto',
            'forecast_days': 2
        }
        
        response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        current = data.get('current', {})
        hourly = data.get('hourly', {})
        
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
        
        # Process hourly forecast data for the next few hours
        hourly_forecast = []
        if hourly and 'time' in hourly:
            current_time = datetime.now()
            for i in range(len(hourly['time'])):
                hour_time = datetime.fromisoformat(hourly['time'][i].replace('Z', '+00:00'))
                
                # Only include future hours (next 12 hours)
                if hour_time > current_time and (hour_time - current_time) <= timedelta(hours=12):
                    hourly_data = {
                        'time': hourly['time'][i],
                        'temperature': hourly['temperature_2m'][i] if i < len(hourly['temperature_2m']) else None,
                        'humidity': hourly['relative_humidity_2m'][i] if i < len(hourly['relative_humidity_2m']) else None,
                        'precipitation': hourly['precipitation'][i] if i < len(hourly['precipitation']) else None,
                        'rain': hourly['rain'][i] if i < len(hourly['rain']) else None,
                        'weather_code': hourly['weather_code'][i] if i < len(hourly['weather_code']) else None,
                        'cloud_cover': hourly['cloud_cover'][i] if i < len(hourly['cloud_cover']) else None,
                        'wind_speed': hourly['wind_speed_10m'][i] if i < len(hourly['wind_speed_10m']) else None
                    }
                    hourly_forecast.append(hourly_data)
        
        weather_data = {
            'current': current_weather,
            'hourly_forecast': hourly_forecast,
            'location': {'lat': BAREILLY_LAT, 'lon': BAREILLY_LON, 'name': 'Bareilly, India'},
            'last_updated': datetime.now().isoformat(),
            'source': 'open-meteo'
        }
        
        weather_cache = weather_data
        weather_last_updated = datetime.now()
        
        print(f"✅ Weather data: {current_weather['temperature']}°C, {current_weather['humidity']}%")
        
        telemetry_data = {
            "temperature": current_weather['temperature'],
            "humidity": current_weather['humidity'],
            "cloud_cover": current_weather['cloud_cover'],
            "wind_speed": current_weather['wind_speed'],
            "precipitation": current_weather['precipitation'],
            "weather_code": current_weather['weather_code'],
            "location_lat": BAREILLY_LAT,
            "location_lon": BAREILLY_LON
        }
        send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        return weather_data
        
    except Exception as e:
        error_msg = f"Weater API error: {str(e)}"
        send_telegram_alert("Weather API error","api error")
        print(f"❌ {error_msg}")
        return {'error': error_msg}

@app.route('/weather', methods=['GET'])
def weather():
    try:
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        weather_data = get_weather_data(force_refresh=force_refresh)
        return jsonify(weather_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/hourly-forecast', methods=['GET'])
def hourly_forecast():
    try:
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        weather_data = get_weather_data(force_refresh=force_refresh)
        
        if 'error' in weather_data:
            return jsonify({"error": weather_data['error']}), 500
            
        return jsonify({
            "hourly_forecast": weather_data.get('hourly_forecast', []),
            "location": weather_data.get('location', {}),
            "last_updated": weather_data.get('last_updated')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/combined-data', methods=['GET'])
def combined_data():
    try:
        esp32_data = {
            "box_temp": box_temp,
            "power": power,
            "solar_power": solar_power,
            "battery_percentage": battery_percentage,
            "voltage": voltage,
            "current": current,
            "esp32_last_updated": datetime.now().isoformat() if any([box_temp, power, solar_power]) else None
        }
        
        weather_data = get_weather_data()
        
        # Prepare combined data for your app
        combined_data = {
            "esp32_data": esp32_data,
            "alerts": {
                "alert1": alert1,
                "alert2": alert2,
                "alert3": alert3,
                "alert4": alert4,
                "alert5": alert5,
                "alert6": alert6,
                "alert7": alert7,
                "alert8": alert8
            },
            "weather_data": weather_data if 'error' not in weather_data else {"error": weather_data['error']},
            "timestamp": datetime.now().isoformat()
        }
        
        # Send combined data to your app (non-blocking)
        import threading
        thread = threading.Thread(target=send_to_app, args=(combined_data,))
        thread.daemon = True
        thread.start()
        
        return jsonify({"esp32_data": esp32_data, "weather_data": weather_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-open-meteo', methods=['GET'])
def test_open_meteo():
    try:
        weather_data = get_weather_data()
        if 'error' in weather_data:
            return jsonify({"success": False, "error": weather_data['error']})
        return jsonify({
            "success": True,
            "current_temperature": weather_data['current'].get('temperature'),
            "location": weather_data['location']
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Telegram alert functions
def send_telegram_alert(message, alert_type="general"):
    """Send alert message to Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured")
        return {"error": "Telegram credentials not configured"}
    
    # Check if we should send this alert (cooldown period)
    current_time = datetime.now().timestamp()
    last_sent = last_alert_time.get(alert_type, 0)
    
    if current_time - last_sent < ALERT_COOLDOWN:
        print(f"⚠️ Alert {alert_type} skipped due to cooldown")
        return {"status": "skipped", "reason": "cooldown"}
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
   
    formatted_message = f"🚨 <b>Solar Monitor Alert</b> 🚨\n\n{message}\n\n<i>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": formatted_message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Alert sent to Telegram: {message}")
        
        # Update last sent time for this alert type
        last_alert_time[alert_type] = current_time
        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to send Telegram message: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

@app.route('/alert', methods=['POST'])
def handle_alert():
    """Endpoint to receive alerts and forward to Telegram"""
    try:
        
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided"}), 400
        
        message = data['message']
        alert_type = data.get('type', 'general')
        
        # Send to Telegram
        result = send_telegram_alert(message, alert_type)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({"status": "Message sent to Telegram", "telegram_response": result}), 200
        
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# Alert checking functions.....................................................................................................
def check_alerts():
    global alert1, alert2, alert3, alert4, alert5,nonessentialrelaystate
    try:
        alert1 = None
        alert2 = None
        alert3 = None
        alert4 = None
        alert5 = None

        # Skip alert checks if critical data is missing
        if current_battery_percent is None or light_intensity is None or solar_voltage is None or solar_current is None:
            return

        # 1 Alert for overcharge or discharge
        if current_battery_percent == 100:
            
            alert1 = "Overcharge!"
            nonessentialrelaystate=1
            send_telegram_alert(alert1, "battery")
        if current_battery_percent < 10:
            alert1 = "Discharge!"
            nonessentialrelaystate=0
            send_telegram_alert(alert1, "battery")

        # 2 Sun is sufficient but panel not produce power enough as it should be:
        irradiance = light_intensity / 120   # conversion of lux to irradiance
        solar_power = (solar_voltage * solar_current) / 1000  # both should be global variables
        
        # FIXED: Replace range() with proper float comparisons
        if 900 <= irradiance < 1200:
            if not (0.31 <= solar_power <= 0.37):
                alert2 = "solar panel low efficiency!"
                nonessentialrelaystate=0
                send_telegram_alert(alert2, "panel alert")

        if 600 <= irradiance < 900:
            if not (0.22 <= solar_power <= 0.30):
                alert2 = "solar panel low efficiency!"
                nonessentialrelaystate=0
                send_telegram_alert(alert2, "panel alert")

        if 350 <= irradiance < 600:
            if not (0.14 <= solar_power <= 0.22):
                alert2 = "solar panel low efficiency!"
                nonessentialrelaystate=0
                send_telegram_alert(alert2, "panel alert")

        if 150 <= irradiance < 350:
            if not (0.05 <= solar_power <= 0.14):
                alert2 = "solar panel low efficiency!"
                nonessentialrelaystate=0
                send_telegram_alert(alert2, "panel alert")

        if irradiance < 100:
            if not (0.0 <= solar_power <= 0.05):
                alert2 = "solar panel low efficiency!"
                nonessentialrelaystate=0
                send_telegram_alert(alert2, "panel alert")

        # 3 overload conditions:
        if voltage is not None and current is not None:
            if (voltage * current / 1000) > inverter_rating:
                alert3 = "Overload!"
                nonessentialrelaystate=0
                send_telegram_alert(alert3, "load alert")

        # 4 sudden drop in sunlight:         
        if prev_light_intensity is not None:
            current_light_intensity = irradiance
            # Assuming timegap is 5 minutes (300 seconds) between readings
            timegap = 300
            light_slope = (current_light_intensity - prev_light_intensity) / timegap
            if light_slope < threshold_slope:
                alert4 = "Sudden drop in sun light!"
                nonessentialrelaystate=0
                send_telegram_alert(alert4, "light intensity alert")

        # 5 Solar generate power But battery not charge:
        if solar_power != 0 and prev_battery_percent is not None:  # solar produces power 
            timegap = 300  # 5 minutes in seconds
            battery_percent_slope = (current_battery_percent - prev_battery_percent) / timegap
            if battery_percent_slope < threshold_battery_slope:
                alert5 = "Battery not charging!"
                nonessentialrelaystate=0
                send_telegram_alert(alert5, "battery alert")

    except Exception as e:
        print(f"❌ Error in alert system: {str(e)}")
#........................................................................................................................
def predictionalerts():
    global alert6, alert7, alert8, nonessentialrelaystate
    predicttotalenergy=random.random()*4
    try:
        alert6=alert7=alert8=None
        if averageenergyconsume > predicttotalenergy:
            # 6. send alert that consumption is higher than expected solar generation
            alert6 = "consumption is higher than expected solar generation!"
            send_telegram_alert("consumption is higher than expected solar generation!","prediction alert")
        
            if battery_percentage < 40:
                # 7. send alert that Battery is low. Risk of blackout in future 
                alert7 = "Battery is low. Risk of blackout in future!"
                send_telegram_alert("Battery is low. Risk of blackout in future!","prediction alert")
                # take action to switch off relay of non essential load
                nonessentialrelaystate=0

        if averageenergyconsume < predicttotalenergy:
            # show that solar generation is sufficient as per your need
            if battery_percentage > 40 and battery_percentage < 80:
                # show that you can turn on non essential loads
                nonessentialrelaystate=1
                

            if battery_percentage > 80:
                # 8. your battery may overcharge in next upcoming hours
                alert8 = "Battery may overcharge in next upcoming hours!"
                nonessentialrelaystate=1
                send_telegram_alert("Battery may overcharge in next upcoming hours!","prediction alert")
    except Exception as e:
        print(f"❌ Error in prediction alerts: {str(e)}")
#.........................................................................................................................................

@app.route('/api/dashboard-data', methods=['GET', 'POST'])
def dashboard_data():
    """Serve dashboard data directly from this Flask app"""
    try:
        # Get the latest data
        esp32_data = {
            "box_temp": box_temp,
            "power": power,
            "solar_power": solar_power,
            "battery_percentage": battery_percentage,
            "voltage": voltage,
            "current": current,
            "solar_voltage": solar_voltage,
            "solar_current": solar_current,
            "light_intensity": light_intensity,
            "energy": energy,
            "frequency": frequency,
            "nonessentialrelaystate": nonessentialrelaystate
        }
        
        weather_data = get_weather_data(force_refresh=False)
        
        combined_data = {
            "esp32_data": esp32_data,
            "alerts": {
                "alert1": alert1,
                "alert2": alert2,
                "alert3": alert3,
                "alert4": alert4,
                "alert5": alert5,
                "alert6": alert6,
                "alert7": alert7,
                "alert8": alert8
            },
            "weather_data": weather_data if 'error' not in weather_data else {"error": weather_data['error']},
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(combined_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    telegram_status = "configured" if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else "not_configured"
    return jsonify({
        "status": "healthy", 
        "telegram": telegram_status,
        "thingsboard": "configured" if THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN' else "not_configured",
        "app": "configured",
        "csv": "active"
    }), 200

# New CSV endpoints for model access
@app.route('/api/csv-data', methods=['GET'])
def get_csv_data():
    """Endpoint for model to fetch CSV data"""
    try:
        if not os.path.exists(CSV_FILE_PATH):
            return jsonify({"error": "CSV file not found"}), 404
        
        # Read the CSV file
        df = pd.read_csv(CSV_FILE_PATH)
        
        # Convert to JSON
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
            "date_range": {
                "start": df['timestamp'].min(),
                "end": df['timestamp'].max()
            },
            "columns": list(df.columns)
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Initialize the system when the app starts
@app.before_first_request
def initialize_system():
    init_csv_file()
    start_background_scheduler()
    print("✅ Solar Monitoring System Initialized")

if __name__ == '__main__':
    # Initialize on startup
    init_csv_file()
    start_background_scheduler()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # For production deployment
    application = app
    
    # Initialize when imported
    init_csv_file()
    start_background_scheduler()
