from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
import random
import json  
import math
import os
from flask_cors import CORS  

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
battery_percent_slope = 0
threshold_battery_slope = -0.05   # Set appropriate threshold for battery charging rate
inverter_rating = 500  # Set your inverter rating in watts
last_alert_time = {}
ALERT_COOLDOWN = 300  # 5 minutes in seconds
nonessentialrelaystate = 1

averageenergyconsume = 2.5  # in same interval in which total predict energy calculated calculated it like avg power of one day then avg power of this time-?
predicttotalenergy = 0
alert1 = None
alert2 = None
alert3 = None
alert4 = None
alert5 = None
alert6 = None
alert7 = None
alert8 = None

# Weather data cache
weather_cache = None
weather_last_updated = None
CACHE_DURATION = 3600  # 1 hour

# Bareilly coordinates
BAREILLY_LAT = 28.3640
BAREILLY_LON = 79.4151

# Open-Meteo API
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8352010252:AAFxUDRp1ihGFQk_cu4ifQgQ8Yi4a_UVpDA')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5625474222')
# ThingsBoard Configuration
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'SKXA7Q19fcvLoevrFdJz')
APP_URL = os.environ.get('APP_URL', 'https://energy-vison.vercel.app')  
API_ENDPOINT = os.environ.get('API_ENDPOINT', 'https://energy-vison.vercel.app/api/dashboard-data')     

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
            "POST /send-all-data-to-app": "Send all global variables and weather data to external app"
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
        "status": "active"
    })


def send_to_thingsboard(device_token, telemetry_data):
    try:
        if THINGSBOARD_HOST == 'http://localhost:8080' or device_token == 'YOUR_DEVICE_ACCESS_TOKEN':
            print("⚠️ ThingsBoard not configured - skipping send")
            return False
            
        url = f"{THINGSBOARD_HOST}/api/v1/{device_token}/telemetry"
        
        # Clean the telemetry data to ensure all values are valid
        cleaned_telemetry = {}
        for key, value in telemetry_data.items():
            # Convert all values to basic types that ThingsBoard can handle
            if value is None:
                cleaned_telemetry[key] = 0  # Replace None with 0
            elif isinstance(value, (int, float)):
                cleaned_telemetry[key] = value
            elif isinstance(value, str):
                # For strings, ensure they're not too long and don't contain problematic characters
                cleaned_telemetry[key] = value[:100]  # Limit string length
            elif isinstance(value, bool):
                cleaned_telemetry[key] = int(value)  # Convert bool to 0/1
            else:
                # Convert any other type to string and limit length
                cleaned_telemetry[key] = str(value)[:100]
        
        telemetry_with_ts = {
            "ts": int(datetime.now().timestamp() * 1000),
            "values": cleaned_telemetry
        }
        
        headers = {'Content-Type': 'application/json'}
        
        print(f"📤 Sending to ThingsBoard: {url}")
        print(f"📤 Data sample: { {k: cleaned_telemetry[k] for k in list(cleaned_telemetry.keys())[:5]} }")  # Show first 5 fields
        
        response = requests.post(url, json=telemetry_with_ts, headers=headers, timeout=10)
        
        # Check for specific error responses
        if response.status_code >= 400:
            print(f"❌ ThingsBoard API error: Status {response.status_code}")
            if response.text:
                print(f"❌ Response: {response.text[:200]}")  # Show first 200 chars of response
            
            # Try to identify if it's a specific field issue by sending minimal data
            if response.status_code == 500 and len(cleaned_telemetry) > 3:
                print("🔄 Trying to identify problematic field by testing minimal data...")
                minimal_data = {
                    "power": float(power) if power is not None else 0,
                    "solar_power": float(solar_power) if solar_power is not None else 0,
                    "battery_percentage": float(battery_percentage) if battery_percentage is not None else 0,
                }
                minimal_success = send_to_thingsboard(device_token, minimal_data)
                if minimal_success:
                    print("✅ Minimal data works - one of the additional fields is causing the issue")
            
            return False
            
        response.raise_for_status()
        
        print(f"✅ Successfully sent to ThingsBoard (Status: {response.status_code})")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ThingsBoard API error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error sending to ThingsBoard: {str(e)}")
        return False


def send_all_data_to_thingsboard():
    """Central function to send all data to ThingsBoard"""
    try:
        # Get weather data
        weather_data = get_weather_data(force_refresh=False)
        
        # Prepare all telemetry data in a single dictionary
        telemetry_data = {
            # ESP32 data (basic working fields)
            "power": float(power) if power is not None else 0,
            "solar_power": float(solar_power) if solar_power is not None else 0,
            "battery_percentage": float(battery_percentage) if battery_percentage is not None else 0,
            "voltage": float(voltage) if voltage is not None else 0,
            "current": float(current) if current is not None else 0,
            "light_intensity": float(light_intensity) if light_intensity is not None else 0,
            
            # Weather data
            "temperature": float(weather_data['current'].get('temperature', 0)) if weather_data and not weather_data.get('error') else 0,
            "humidity": float(weather_data['current'].get('humidity', 0)) if weather_data and not weather_data.get('error') else 0,
            
            # System state
            "nonessentialrelaystate": int(nonessentialrelaystate) if nonessentialrelaystate is not None else 0,
        }
        
        # Add optional fields only if they have values
        optional_fields = {
            "energy": float(energy) if energy is not None else None,
            "box_temp": float(box_temp) if box_temp is not None else None,
            "solar_voltage": float(solar_voltage) if solar_voltage is not None else None,
            "solar_current": float(solar_current) if solar_current is not None else None,
            "frequency": float(frequency) if frequency is not None else None,
            "power_factor": float(power_factor) if power_factor is not None else None,
            "battery_voltage": float(battery_voltage) if battery_voltage is not None else None,
            "cloud_cover": float(weather_data['current'].get('cloud_cover')) if weather_data and not weather_data.get('error') and weather_data['current'].get('cloud_cover') is not None else None,
            "wind_speed": float(weather_data['current'].get('wind_speed')) if weather_data and not weather_data.get('error') and weather_data['current'].get('wind_speed') is not None else None,
            "precipitation": float(weather_data['current'].get('precipitation')) if weather_data and not weather_data.get('error') and weather_data['current'].get('precipitation') is not None else None,
            "weather_code": int(weather_data['current'].get('weather_code')) if weather_data and not weather_data.get('error') and weather_data['current'].get('weather_code') is not None else None,
            "averageenergyconsume": float(averageenergyconsume) if averageenergyconsume is not None else None,
            "predicttotalenergy": float(predicttotalenergy) if predicttotalenergy is not None else None,
        }
        
        # Add optional fields that are not None
        for key, value in optional_fields.items():
            if value is not None:
                telemetry_data[key] = value
        
        # Add alert fields as strings (replace None with empty string)
        alert_fields = {
            "alert1": str(alert1) if alert1 is not None else "",
            "alert2": str(alert2) if alert2 is not None else "",
            "alert3": str(alert3) if alert3 is not None else "",
            "alert4": str(alert4) if alert4 is not None else "",
            "alert5": str(alert5) if alert5 is not None else "",
            "alert6": str(alert6) if alert6 is not None else "",
            "alert7": str(alert7) if alert7 is not None else "",
            "alert8": str(alert8) if alert8 is not None else "",
        }
        telemetry_data.update(alert_fields)
        
        # Always add location data
        telemetry_data.update({
            "location_lat": float(BAREILLY_LAT),
            "location_lon": float(BAREILLY_LON),
        })
        
        print(f"📊 Prepared data for ThingsBoard with {len(telemetry_data)} fields")
        
        # Send to ThingsBoard
        success = send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        return success
        
    except Exception as e:
        print(f"❌ Error in send_all_data_to_thingsboard: {str(e)}")
        # Try to send at least basic data as fallback
        try:
            basic_data = {
                "power": float(power) if power is not None else 0,
                "solar_power": float(solar_power) if solar_power is not None else 0,
                "battery_percentage": float(battery_percentage) if battery_percentage is not None else 0,
            }
            return send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, basic_data)
        except:
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
            success = send_all_data_to_thingsboard()
            return jsonify({"success": success, "device": "solar", "message": "All data sent to ThingsBoard"})
        
        return jsonify({"error": "Invalid device type"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    global box_temp, frequency, power_factor, voltage, current, power, energy
    global solar_voltage, solar_current, solar_power, battery_percentage
    global light_intensity, battery_voltage, prev_light_intensity, current_light_intensity
    global prev_battery_percent, current_battery_percent, nonessentialrelaystate
    
    print("📨 Received POST request to /esp32-data")
    
    try:
        data = request.get_json()
        if not data:
            send_telegram_alert("No JSON data received", "data error")
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
        
        # Send all data to ThingsBoard from one place
        send_all_data_to_thingsboard()
            
        # ⭐⭐⭐ AUTO-FORWARD TO DASHBOARD APP ⭐⭐⭐
        try:
            # Get weather data
            weather_data = get_weather_data(force_refresh=False)
            
            # Prepare all data to send
            all_data = {
                # ESP32 data variables
                "box_temp": box_temp,
                "frequency": frequency,
                "power_factor": power_factor,
                "voltage": voltage,
                "current": current,
                "power": power,
                "energy": energy,
                "solar_voltage": solar_voltage,
                "solar_current": solar_current,
                "solar_power": solar_power,
                "battery_percentage": battery_percentage,
                "light_intensity": light_intensity,
                "battery_voltage": battery_voltage,
                
                # Alert system variables
                "prev_light_intensity": prev_light_intensity,
                "current_light_intensity": current_light_intensity,
                "light_slope": light_slope,
                "threshold_slope": threshold_slope,
                "irradiance": irradiance,
                "prev_battery_percent": prev_battery_percent,
                "current_battery_percent": current_battery_percent,
                "battery_percent_slope": battery_percent_slope,
                "threshold_battery_slope": threshold_battery_slope,
                "inverter_rating": inverter_rating,
                "nonessentialrelaystate": nonessentialrelaystate,
                
                # Prediction and alert variables
                "averageenergyconsume": averageenergyconsume,
                "predicttotalenergy": predicttotalenergy,
                "alert1": alert1,
                "alert2": alert2,
                "alert3": alert3,
                "alert4": alert4,
                "alert5": alert5,
                "alert6": alert6,
                "alert7": alert7,
                "alert8": alert8,
                
                # Weather data
                "weather_data": weather_data if not weather_data.get('error') else {"error": weather_data.get('error')},
                
                # Metadata
                "server_timestamp": datetime.now().isoformat(),
                "location": {"lat": BAREILLY_LAT, "lon": BAREILLY_LON, "name": "Bareilly, India"}
            }
            
            # Send to your dashboard app
            dashboard_url = "https://energy-vison.vercel.app/api/dashboard-data"
           
            print(f"📤 SENDING TO EXTERNAL APP:")
            print(f"📤 URL: {dashboard_url}")
            
            headers = {'Content-Type': 'application/json'}
            response = requests.post(dashboard_url, json=all_data, headers=headers, timeout=10)
            
            if response.status_code >= 200 and response.status_code < 300:
                print("✅ Auto-forwarded to dashboard successfully")
            else:
                print(f"❌ Auto-forward failed: Status {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Auto-forward error: {str(e)}")
        # ⭐⭐⭐ END AUTO-FORWARD ⭐⭐⭐
        
        # Get current weather data to send back to ESP32
        weather_data = get_weather_data(force_refresh=False)
        
        # Handle case where weather data contains error
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
                "nonessentialrelaystate": nonessentialrelaystate,
                "alert1": alert1,
                "alert2": alert2,
                "alert3": alert3,
                "alert4": alert4,
                "alert5": alert5,
                "alert6": alert6,
                "alert7": alert7,
                "alert8": alert8,
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

# NEW ENDPOINT: Send all global variables and weather data to external app
@app.route('/send-all-data-to-app', methods=['POST'])
def send_all_data_to_app():
    """Send all global variables AND weather data as JSON to external app via POST request"""
    try:
        # Get the target URL from the request or use a default
        data = request.get_json() or {}
        target_url = data.get('url', 'https://energy-vison.vercel.app')
        endpoint = data.get('endpoint', '/api/dashboard-data')
        
        if not target_url:
            return jsonify({
                "success": False, 
                "error": "No target URL provided. Please include 'url' in your request body"
            }), 400
        
        # Build the complete URL
        full_url = f"{target_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Get current weather data
        weather_data = get_weather_data(force_refresh=False)
        
        # Prepare all global variables as a dictionary
        all_data = {
            # ESP32 data variables
            "box_temp": box_temp,
            "frequency": frequency,
            "power_factor": power_factor,
            "voltage": voltage,
            "current": current,
            "power": power,
            "energy": energy,
            "solar_voltage": solar_voltage,
            "solar_current": solar_current,
            "solar_power": solar_power,
            "battery_percentage": battery_percentage,
            "light_intensity": light_intensity,
            "battery_voltage": battery_voltage,
            
            # Alert system variables
            "prev_light_intensity": prev_light_intensity,
            "current_light_intensity": current_light_intensity,
            "light_slope": light_slope,
            "threshold_slope": threshold_slope,
            "irradiance": irradiance,
            "prev_battery_percent": prev_battery_percent,
            "current_battery_percent": current_battery_percent,
            "battery_percent_slope": battery_percent_slope,
            "threshold_battery_slope": threshold_battery_slope,
            "inverter_rating": inverter_rating,
            "nonessentialrelaystate": nonessentialrelaystate,
            
            # Prediction and alert variables
            "averageenergyconsume": averageenergyconsume,
            "predicttotalenergy": predicttotalenergy,
            "alert1": alert1,
            "alert2": alert2,
            "alert3": alert3,
            "alert4": alert4,
            "alert5": alert5,
            "alert6": alert6,
            "alert7": alert7,
            "alert8": alert8,
            
            # Weather data
            "weather_data": weather_data if not weather_data.get('error') else {"error": weather_data.get('error')},
            
            # Metadata
            "server_timestamp": datetime.now().isoformat(),
            "location": {"lat": BAREILLY_LAT, "lon": BAREILLY_LON, "name": "Bareilly, India"}
        }
        
        # Send the data via POST request
        headers = {'Content-Type': 'application/json'}
        response = requests.post(full_url, json=all_data, headers=headers, timeout=10)
        
        # Check if the request was successful
        if response.status_code >= 200 and response.status_code < 300:
            return jsonify({
                "success": True,
                "message": f"Data sent successfully to {full_url}",
                "status_code": response.status_code,
                "response": response.text
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Failed to send data. Status code: {response.status_code}",
                "response": response.text
            }), 500
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "error": error_msg}), 500
    except Exception as e:
        error_msg = f"Internal server error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "error": error_msg}), 500

# Alert checking functions
def check_alerts():
    global alert1, alert2, alert3, alert4, alert5, nonessentialrelaystate
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
                # 7. send alert that Battery is low. Risk of blackout in future ..
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    telegram_status = "configured" if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else "not_configured"
    return jsonify({
        "status": "healthy", 
        "telegram": telegram_status,
        "thingsboard": "configured" if THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN' else "not_configured"
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    application = app
