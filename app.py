from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
import random
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

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8352010252:AAFxUDRp1ihGFQk_cu4ifQgQ8Yi4a_UVpDA')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5625474222')
# ThingsBoard Configuration
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'GudRzRG8OWWm7YhUCziK')

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
            "POST /alert": "Send alert to Telegram"
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

@app.route('/send-to-thingsboard', methods=['POST'])
def send_data_to_thingsboard():
    try:
        data = request.get_json() or {}
        device_type = data.get('device_type', 'weather')
        
        if device_type == 'weather':
            telemetry_data = resend_weather_to_thingsboard()
            if telemetry_data:
                # DON'T send to ThingsBoard here - just return the prepared data
                return jsonify({
                    "success": True, 
                    "device": "weather", 
                    "message": "Weather data prepared (not sent to ThingsBoard)",
                    "data": telemetry_data
                })
            else:
                return jsonify({"success": False, "error": "No weather data available"})
        elif device_type == 'solar':
            if any([box_temp, power, solar_power]):
                telemetry_data = get_complete_telemetry_data()
                # DON'T send to ThingsBoard here - just return the prepared data
                return jsonify({
                    "success": True, 
                    "device": "solar", 
                    "message": "Solar data prepared (not sent to ThingsBoard)",
                    "data": telemetry_data
                })
        
        return jsonify({"error": "No data available to send"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/resend-weather', methods['POST'])
def resend_weather():
    try:
        telemetry_data = resend_weather_to_thingsboard()
        if telemetry_data:
            # DON'T send to ThingsBoard here - just return the prepared data
            return jsonify({
                "success": True,
                "message": "Weather data prepared (not sent to ThingsBoard)",
                "data": telemetry_data
            })
        else:
            return jsonify({"success": False, "error": "No weather data available"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
        
        # Check for specific error responses from ThingsBoard
        if response.status_code == 500:
            print(f"❌ ThingsBoard server error (500). This often indicates an issue with the device token or server configuration.")
            return False
        elif response.status_code == 401:
            print(f"❌ ThingsBoard authentication error (401). Check your device access token.")
            return False
        elif response.status_code == 404:
            print(f"❌ ThingsBoard device not found (404). Check your device token.")
            return False
            
        response.raise_for_status()
        
        print(f"✅ Successfully sent to ThingsBoard (Status: {response.status_code})")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ThingsBoard API error: {str(e)}")
        # Don't send Telegram alert for ThingsBoard errors to avoid spam
        return False
    except Exception as e:
        print(f"❌ Error sending to ThingsBoard: {str(e)}")
        return False

def resend_weather_to_thingsboard():
    try:
        weather_data = get_weather_data(force_refresh=False)
        if 'error' in weather_data:
            print(f"❌ Cannot resend weather data: {weather_data['error']}")
            return None
        
        telemetry_data = get_complete_telemetry_data()
        print(f"🔄 Prepared weather data for ThingsBoard")
        return telemetry_data  # Return the data instead of sending it
        
    except Exception as e:
        error_msg = f"Error preparing weather data: {str(e)}"
        print(f"❌ {error_msg}")
        return None

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
            send_telegram_alert("No JSON data received","data error")
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
        
        # Send to ThingsBoard
        if any([box_temp, power, solar_power]):
            telemetry_data = get_complete_telemetry_data()
            # Try to send to ThingsBoard but don't fail the request if it doesn't work
            try:
                send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
            except Exception as e:
                print(f"⚠️ ThingsBoard send failed but continuing: {str(e)}")
        
        # Get current weather data to send back to ESP32
        weather_data = get_weather_data(force_refresh=False)
        
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

# ... (rest of your functions remain the same, including check_alerts, predictionalerts, etc.)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    application = app
