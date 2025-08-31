
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
import math
import os  # Added for environment variables

app = Flask(__name__)

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

# Weather data cache
weather_cache = None
weather_last_updated = None
CACHE_DURATION = 3600  # Cache weather data for 1 hour

# Bareilly, Uttar Pradesh, India coordinates
BAREILLY_LAT = 28.3640
BAREILLY_LON = 79.4151

# Open-Meteo API (NO API KEY REQUIRED - global coverage)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# ThingsBoard Configuration (Update these with your ThingsBoard details)
THINGSBOARD_HOST = os.environ.get('THINGSBOARD_HOST', 'https://demo.thingsboard.io')
THINGSBOARD_ACCESS_TOKEN = os.environ.get('THINGSBOARD_ACCESS_TOKEN', 'Z1kBA2x2yG6R661ArK7E')
THINGSBOARD_WEATHER_DEVICE_TOKEN = os.environ.get('THINGSBOARD_WEATHER_DEVICE_TOKEN', 'YOUR_WEATHER_DEVICE_TOKEN')

@app.route('/')
def home():
    """Home endpoint with API information"""
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
            "solar_device_token": THINGSBOARD_ACCESS_TOKEN,
            "weather_device_token": THINGSBOARD_WEATHER_DEVICE_TOKEN,
            "status": "configured" if THINGSBOARD_ACCESS_TOKEN != 'YOUR_DEVICE_ACCESS_TOKEN' else "not_configured"
        },
        "status": "active"
    })

def send_to_thingsboard(device_token, telemetry_data):
    """
    Send telemetry data to ThingsBoard
    """
    try:
        if THINGSBOARD_HOST == 'http://localhost:8080' or device_token == 'YOUR_DEVICE_ACCESS_TOKEN':
            print("⚠️ ThingsBoard not configured - skipping send")
            return False
            
        url = f"{THINGSBOARD_HOST}/api/v1/{device_token}/telemetry"
        
        # Add timestamp to telemetry data
        telemetry_with_ts = {
            "ts": int(datetime.now().timestamp() * 1000),  # ThingsBoard expects milliseconds
            "values": telemetry_data
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        print(f"📤 Sending to ThingsBoard: {url}")
        print(f"   Data: {telemetry_data}")
        
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
    """
    Resend current weather data to ThingsBoard (even if cached)
    """
    try:
        # Get current weather data (may be cached)
        weather_data = get_weather_data(force_refresh=False)
        
        if 'error' in weather_data:
            print(f"❌ Cannot resend weather data: {weather_data['error']}")
            return False
        
        # Prepare telemetry data
        telemetry_data = {
            "temperature": weather_data['current'].get('temperature'),
            "humidity": weather_data['current'].get('humidity'),
            "cloud_cover": weather_data['current'].get('cloud_cover'),
            "wind_speed": weather_data['current'].get('wind_speed'),
            "precipitation": weather_data['current'].get('precipitation'),
            "weather_code": weather_data['current'].get('weather_code'),
            "location_lat": BAREILLY_LAT,
            "location_lon": BAREILLY_LON,
            "data_source": "open-meteo",
            "resend_timestamp": datetime.now().isoformat()
        }
        
        print(f"🔄 Resending weather data to ThingsBoard: {telemetry_data}")
        
        # Send to ThingsBoard
        success = send_to_thingsboard(THINGSBOARD_WEATHER_DEVICE_TOKEN, telemetry_data)
        
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
    """Force resend current weather data to ThingsBoard"""
    try:
        success = resend_weather_to_thingsboard()
        return jsonify({
            "success": success,
            "message": "Weather data resent to ThingsBoard" if success else "Failed to resend weather data",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = f"Resend weather error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "error": error_msg}), 500

@app.route('/send-to-thingsboard', methods=['POST'])
def send_data_to_thingsboard():
    """
    Manual endpoint to send current data to ThingsBoard
    """
    try:
        data = request.get_json() or {}
        device_type = data.get('device_type', 'weather')  # 'weather' or 'solar'
        
        if device_type == 'weather':
            # Send weather data
            success = resend_weather_to_thingsboard()
            return jsonify({"success": success, "device": "weather", "message": "Weather data sent to ThingsBoard"})
        
        elif device_type == 'solar':
            # Send solar data (if available)
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
        
        return jsonify({"error": "No data available to send", "device_type": device_type})
        
    except Exception as e:
        error_msg = f"Error sending to ThingsBoard: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/esp32-data', methods=['POST'])
def receive_esp32_data():
    """Receive data from ESP32 device"""
    global box_temp, frequency, power_factor, voltage, current, power, energy
    global solar_voltage, solar_current, solar_power, battery_percentage
    global light_intensity, battery_voltage
    
    print("📨 Received POST request to /esp32-data")
    
    try:
        data = request.get_json()
        
        if not data:
            print("❌ No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400
        
        print(f"✅ JSON data received: {data}")
        
        # Handle both camelCase and snake_case keys from ESP32
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
        
        print("✅ ESP32 data processed:")
        print(f"   Box Temp: {box_temp}°C, Power: {power}W")
        print(f"   Solar: {solar_power}W, Battery: {battery_percentage}%")
        
        # Automatically send solar data to ThingsBoard
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
        
        return jsonify({
            "message": "Data received successfully", 
            "status": "ok",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = f"Error processing ESP32 data: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/debug', methods=['GET', 'POST'])
def debug():
    """Debug endpoint to check server status"""
    if request.method == 'POST':
        print("📨 Received POST data:", request.get_json())
        return jsonify({"message": "POST received", "data": request.get_json()})
    
    return jsonify({
        "status": "server is running",
        "endpoints": {
            "POST /esp32-data": "Receive ESP32 data",
            "GET /weather": "Get weather data",
            "GET /debug": "This debug endpoint",
            "GET /test-params": "Check current parameters",
            "POST /send-to-thingsboard": "Send to ThingsBoard",
            "POST /resend-weather": "Resend weather data"
        }
    })

@app.route('/test-params', methods=['GET'])
def test_params():
    """Test endpoint to check current parameter values"""
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
    """Check current configuration"""
    return jsonify({
        "thingsboard_host": THINGSBOARD_HOST,
        "solar_device_token": THINGSBOARD_ACCESS_TOKEN,
        "weather_device_token": THINGSBOARD_WEATHER_DEVICE_TOKEN,
        "solar_data_available": any([box_temp, power, solar_power]),
        "weather_cache_age": (datetime.now() - weather_last_updated).total_seconds() if weather_last_updated else None,
        "weather_cache_valid": weather_cache is not None
    })

def get_weather_data(force_refresh=False):
    """
    Fetch current and 7-day forecast weather data using Open-Meteo
    Returns: Dictionary with current weather and forecast
    """
    global weather_cache, weather_last_updated
    
    # Check if cache is still valid (unless force refresh)
    if not force_refresh and weather_cache and weather_last_updated:
        cache_age = (datetime.now() - weather_last_updated).total_seconds()
        if cache_age < CACHE_DURATION:
            print(f"🌤️ Using cached weather data (age: {int(cache_age)}s)")
            return weather_cache
    
    try:
        print("🌤️ Fetching fresh weather data from Open-Meteo...")
        print(f"📍 Location: Bareilly, India ({BAREILLY_LAT}, {BAREILLY_LON})")
        
        # Open-Meteo API parameters
        params = {
            'latitude': BAREILLY_LAT,
            'longitude': BAREILLY_LON,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m',
            'hourly': 'temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m',
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,weather_code',
            'timezone': 'auto',
            'forecast_days': 7
        }
        
        # Make API request
        print("🌐 Making API request to Open-Meteo...")
        response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Extract current weather
        current = data.get('current', {})
        current_weather = {
            'temperature': current.get('temperature_2m'),
            'feels_like': current.get('apparent_temperature'),
            'humidity': current.get('relative_humidity_2m'),
            'cloud_cover': current.get('cloud_cover'),
            'wind_speed': current.get('wind_speed_10m'),
            'wind_direction': current.get('wind_direction_10m'),
            'precipitation': current.get('precipitation'),
            'rain': current.get('rain'),
            'weather_code': current.get('weather_code'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Extract daily forecast (next 5 days)
        forecast = []
        daily_data = data.get('daily', {})
        times = daily_data.get('time', [])
        
        for i in range(min(5, len(times))):  # Next 5 days
            forecast.append({
                'date': times[i],
                'temperature_max': daily_data.get('temperature_2m_max', [])[i] if i < len(daily_data.get('temperature_2m_max', [])) else None,
                'temperature_min': daily_data.get('temperature_2m_min', [])[i] if i < len(daily
