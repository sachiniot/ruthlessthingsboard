
# Configuration file for Solar Monitoring System

# Flask configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
FLASK_DEBUG = True

# Location configuration (default: Bareilly, India)
LOCATION_LAT = 28.3640
LOCATION_LON = 79.4151
LOCATION_NAME = 'Bareilly, India'

# Weather API configuration
WEATHER_CACHE_DURATION = 3600  # 1 hour in seconds
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# CORS configuration (if needed)
CORS_ORIGINS = ["http://localhost:3000", "http://yourdomain.com"]

# Security configuration
API_KEY = "your_optional_api_key_here"  # For future authentication
