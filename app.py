from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
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
send_telegram_message=None

# Weather data cache
weather_cache = None
weather_last_updated = None
CACHE_DURATION = 3600

# Bareilly coordinates
BAREILLY_LAT = 28.3640
BAREILLY_LON = 79.4151

# Open-Meteo API
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

#Telergam token and id
TELEGRAM_BOT_TOKEN = os.environ.get('8352010252:AAFxUDRp1ihGFQk_cu4ifQgQ8Yi4a_UVpDA')
TELEGRAM_CHAT_ID = os.environ.get('5625474222')


# ThingsBoard Configuration
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'Z1kBA2x2yG6R661ArK7E')

@app.route('/')
def home():
    return jsonify({
        "message": "Solar Monitoring System API",
        "endpoints": {
            "POST /esp32-data": "Receive data from ESP32",
            "GET /weather": "Get weather data",
            "GET /combined-data": "Get combined ESP32 and weather data",
            "GET /test-open-meteo": "Test Open-Meteo API connection",
            "GET /test-params": "Check current parameter values",
            "POST /send-to-thingsboard": "Send data to ThingsBoard",
            "POST /resend-weather": "Resend weather data to ThingsBoard"
        },
        "thingsboard_config": {
            "host": THINGSBOARD_HOST,
            "device_token": THINGSBOARD_ACCESS_TOKEN,
            "status": "configured" if THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN' else "not_configured"
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
        return False

def resend_weather_to_thingsboard():
    try:
        weather_data = get_weather_data(force_refresh=False)
        if 'error' in weather_data:
            print(f"❌ Cannot resend weather data: {weather_data['error']}")
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
    global light_intensity, battery_voltage,send_telegram_message
    
    print("📨 Received POST request to /esp32-data")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        print(f"✅ JSON data received: {data}")
        
        # Update ESP32 data variables (your existing code)
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
        
        # Send to ThingsBoard (your existing code)
        if any([box_temp, power, solar_power]):
            telemetry_data = {
                "box_temperature": box_temp,
                "power": power,
                "solar_power": solar_power,
                "battery_percentage": battery_percentage,
                "voltage": voltage,
                "current": current,
                "light_intensity": light_intensity,
                "energy": energy,
                "frequency": frequency
            }
            send_to_thingsboard(THINGSBOARD_ACCESS_TOKEN, telemetry_data)
        
        # Get current weather data to send back to ESP32
        weather_data = get_weather_data(force_refresh=False)
        
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
def test_params():
    return jsonify({
        "box_temp": box_temp,
        "power": power,
        "solar_power": solar_power,
        "battery_percentage": battery_percentage,
        "light_intensity": light_intensity,
        "voltage": voltage,
        "current": current,
        "last_updated": datetime.now().isoformat(),
        "status": "active" if any([box_temp, power, solar_power]) else "no_data_received"
    })

@app.route('/check-config', methods=['GET'])
def check_config():
    return jsonify({
        "thingsboard_host": THINGSBOARD_HOST,
        "device_token": THINGSBOARD_ACCESS_TOKEN,
        "solar_data_available": any([box_temp, power, solar_power]),
        "weather_cache_age": (datetime.now() - weather_last_updated).total_seconds() if weather_last_updated else None,
        "weather_cache_valid": weather_cache is not None
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
            'timezone': 'auto'
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
        error_msg = f"Weather API error: {str(e)}"
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

  # function seperatelty for telegram alert..............................................................................................................
def send_telegram_message(message):
    """Send message to Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"error": "Telegram credentials not configured"}
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to send message: {str(e)}"}

@app.route('/alert', methods=['POST'])
def handle_alert():
    """Endpoint to receive alerts and forward to Telegram"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided"}), 400
        
        message = data['message']
        
        # Optional: Add server info to the message
        server_info = f"🚨 <b>Alert from Render Server</b> 🚨\n\n"
        formatted_message = server_info + str(message)
        
        # Send to Telegram
        result = send_telegram_message(formatted_message)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({"status": "Message sent to Telegram", "telegram_response": result}), 200
        
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



#end of telegram sending alert from server functions ........................................................................................

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


send_telegram_message("alert from server")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    application = app
