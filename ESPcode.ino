#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "OPPO A59 5G";
const char* password = "c2m255cg";

// Your Render server URL (replace with your actual Render URL)
const char* serverBaseURL = "https://ruthlessthingsboard-88ik.onrender.com";
const char* dataEndpoint = "/esp32-data";
const char* weatherEndpoint = "/weather";
const char* hourlyEndpoint = "/hourly-forecast";

// Sensor data structure
struct SensorData {
  float box_temp = 25.5;
  float frequency = 50.0;
  float power_factor = 0.95;
  float voltage = 230.0;
  float current = 5.0;
  float power = 1150.0;
  float energy = 12.5;
  float solar_voltage = 18.5;
  float solar_current = 6.2;
  float solar_power = 114.7;
  float battery_percentage = 85.0;
  float light_intensity = 850.0;
  float battery_voltage = 12.8;
};

// Weather data structure
struct WeatherData {
  float temperature = 0;
  float humidity = 0;
  float cloud_cover = 0;
  float wind_speed = 0;
  float precipitation = 0;
  int weather_code = 0;
  bool available = false;
  String error = "";
};

SensorData sensorData;
WeatherData weatherData;

unsigned long lastSendTime = 0;
const unsigned long sendInterval = 30000; // 30 seconds between sends
const unsigned long reconnectInterval = 10000; // 10 seconds between reconnect attempts
unsigned long lastReconnectAttempt = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Solar Monitoring ESP32 Client");
  Serial.println("=============================");
  
  // Initialize sensor data
  initializeSensorData();
  
  // Connect to WiFi
  connectToWiFi();
}

void loop() {
  // Check WiFi connection and reconnect if necessary
  if (WiFi.status() != WL_CONNECTED) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastReconnectAttempt >= reconnectInterval) {
      Serial.println("WiFi disconnected. Attempting to reconnect...");
      connectToWiFi();
      lastReconnectAttempt = currentMillis;
    }
    delay(1000);
    return;
  }
  
  // Send data at regular intervals
  if (millis() - lastSendTime >= sendInterval) {
    updateSensorData(); // Simulate new sensor readings
    
    // Send data to server and get response
    if (sendDataToServer()) {
      Serial.println("Data sent successfully");
    } else {
      Serial.println("Failed to send data");
    }
    
    // Optionally get weather data separately
    if (getWeatherData()) {
      Serial.println("Weather data retrieved successfully");
    } else {
      Serial.println("Failed to get weather data");
    }
    
    lastSendTime = millis();
  }
  
  // Small delay to avoid overwhelming the system
  delay(1000);
}

void initializeSensorData() {
  // Initial values
  sensorData.box_temp = 25.5;
  sensorData.frequency = 50.0;
  sensorData.power_factor = 0.95;
  sensorData.voltage = 230.0;
  sensorData.current = 5.0;
  sensorData.power = 1150.0;
  sensorData.energy = 12.5;
  sensorData.solar_voltage = 18.5;
  sensorData.solar_current = 6.2;
  sensorData.solar_power = 114.7;
  sensorData.battery_percentage = 85.0;
  sensorData.light_intensity = 850.0;
  sensorData.battery_voltage = 12.8;
}

void connectToWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.disconnect(true); // Disconnect and clear settings
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected successfully!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println();
    Serial.println("Failed to connect to WiFi. Please check credentials.");
  }
}

void updateSensorData() {
  // Simulate changing sensor values with realistic patterns
  sensorData.box_temp = 25.0 + random(0, 100) / 20.0; // 25-30°C

  // "AC" side -> actually from battery-powered DC load (scaled for Li-ion battery)
  sensorData.voltage = 3.2 + random(0, 100) / 250.0; // 3.2–4.2V
  sensorData.current = 0.1 + random(0, 200) / 100.0; // 0.1–2.0A
  sensorData.power = sensorData.voltage * sensorData.current; // 0.3–8W approx.

  // Solar panel (6V plate, up to ~1A)
  sensorData.solar_voltage = 5.5 + random(0, 10) / 10.0; // 5.5–6.5V
  sensorData.solar_current = 0.1 + random(0, 100) / 100.0; // 0.1–1.1A
  sensorData.solar_power = sensorData.solar_voltage * sensorData.solar_current; // ~0.5–7W

  // Battery (3.7V Li-ion, 2500mAh)
  sensorData.battery_voltage = sensorData.voltage; // keep same for consistency
  sensorData.battery_percentage = random(30,101);

  // Light intensity (simulate day/night changes)
  sensorData.light_intensity = 200 + random(0, 800); // 200–1000 lux

  // Energy accumulation
  sensorData.energy += sensorData.power / 3600; // Wh accumulation

  Serial.println("Updated sensor readings:");
  Serial.printf("  Load Power: %.2fW, Solar: %.2fW, Battery: %.1f%% (%.2fV)\n", 
                sensorData.power, sensorData.solar_power, sensorData.battery_percentage, sensorData.battery_voltage);
}


bool sendDataToServer() {
  HTTPClient http;
  bool success = false;
  
  // Construct full URL
  String url = String(serverBaseURL) + String(dataEndpoint);
  
  Serial.print("Sending data to: ");
  Serial.println(url);
  
  // Create JSON document
  DynamicJsonDocument doc(1024);
  
  // Add sensor data to JSON
  doc["box_temp"] = sensorData.box_temp;
  doc["frequency"] = sensorData.frequency;
  doc["power_factor"] = sensorData.power_factor;
  doc["voltage"] = sensorData.voltage;
  doc["current"] = sensorData.current;
  doc["power"] = sensorData.power;
  doc["energy"] = sensorData.energy;
  doc["solar_voltage"] = sensorData.solar_voltage;
  doc["solar_current"] = sensorData.solar_current;
  doc["solar_power"] = sensorData.solar_power;
  doc["battery_percentage"] = sensorData.battery_percentage;
  doc["light_intensity"] = sensorData.light_intensity;
  doc["battery_voltage"] = sensorData.battery_voltage;
  
  // Serialize JSON to string
  String jsonString;
  serializeJson(doc, jsonString);
  
  Serial.print("JSON payload: ");
  Serial.println(jsonString);
  
  // Start HTTP connection with timeout
  http.begin(url);
  http.setConnectTimeout(10000); // 10 second timeout
  http.setTimeout(10000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-Solar-Monitor");
  
  // Send POST request
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    String response = http.getString();
    Serial.print("Server response: ");
    Serial.println(response);
    
    // Parse the JSON response
    DynamicJsonDocument responseDoc(1024);
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      // Check if the response contains status information
      if (responseDoc.containsKey("status") && String(responseDoc["status"]) == "ok") {
        success = true;
        
        // Check if weather data is available in response
        if (responseDoc.containsKey("weather_available") && responseDoc["weather_available"]) {
          // Extract weather data from response
          weatherData.temperature = responseDoc["weather"]["temperature"];
          weatherData.humidity = responseDoc["weather"]["humidity"];
          weatherData.cloud_cover = responseDoc["weather"]["cloud_cover"];
          weatherData.wind_speed = responseDoc["weather"]["wind_speed"];
          weatherData.precipitation = responseDoc["weather"]["precipitation"];
          weatherData.weather_code = responseDoc["weather"]["weather_code"];
          weatherData.available = true;
          weatherData.error = "";
          
          Serial.println("Weather Data Received:");
          Serial.printf("  Temperature: %.1f°C\n", weatherData.temperature);
          Serial.printf("  Humidity: %.1f%%\n", weatherData.humidity);
          Serial.printf("  Cloud Cover: %.1f%%\n", weatherData.cloud_cover);
          Serial.printf("  Wind Speed: %.1fkm/h\n", weatherData.wind_speed);
        } else if (responseDoc.containsKey("weather_error")) {
          weatherData.error = responseDoc["weather_error"].as<String>();
          Serial.print("Weather error: ");
          Serial.println(weatherData.error);
        }
      } else {
        Serial.println("Server responded with error status");
      }
    } else {
      Serial.print("JSON parsing failed: ");
      Serial.println(error.c_str());
    }
  } else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
    Serial.print("Error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  // Free resources
  http.end();
  return success;
}

bool getWeatherData() {
  HTTPClient http;
  bool success = false;
  
  // Construct full URL
  String url = String(serverBaseURL) + String(weatherEndpoint);
  
  Serial.print("Getting weather data from: ");
  Serial.println(url);
  
  // Start HTTP connection with timeout
  http.begin(url);
  http.setConnectTimeout(10000); // 10 second timeout
  http.setTimeout(10000);
  http.addHeader("User-Agent", "ESP32-Solar-Monitor");
  
  // Send GET request
  int httpResponseCode = http.GET();
  
  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    String response = http.getString();
    
    // Parse the JSON response
    DynamicJsonDocument responseDoc(1024);
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      if (responseDoc.containsKey("current")) {
        // Extract weather data
        weatherData.temperature = responseDoc["current"]["temperature"];
        weatherData.humidity = responseDoc["current"]["humidity"];
        weatherData.cloud_cover = responseDoc["current"]["cloud_cover"];
        weatherData.wind_speed = responseDoc["current"]["wind_speed"];
        weatherData.precipitation = responseDoc["current"]["precipitation"];
        weatherData.weather_code = responseDoc["current"]["weather_code"];
        weatherData.available = true;
        weatherData.error = "";
        
        Serial.println("Weather Data Retrieved:");
        Serial.printf("  Temperature: %.1f°C\n", weatherData.temperature);
        Serial.printf("  Humidity: %.1f%%\n", weatherData.humidity);
        Serial.printf("  Cloud Cover: %.1f%%\n", weatherData.cloud_cover);
        
        success = true;
      } else if (responseDoc.containsKey("error")) {
        weatherData.error = responseDoc["error"].as<String>();
        Serial.print("Weather error: ");
        Serial.println(weatherData.error);
      }
    } else {
      Serial.print("JSON parsing failed: ");
      Serial.println(error.c_str());
    }
  } else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
    Serial.print("Error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  // Free resources
  http.end();
  return success;
}

// Optional: Function to get hourly forecast
bool getHourlyForecast() {
  HTTPClient http;
  bool success = false;
  
  // Construct full URL
  String url = String(serverBaseURL) + String(hourlyEndpoint);
  
  Serial.print("Getting hourly forecast from: ");
  Serial.println(url);
  
  // Start HTTP connection with timeout
  http.begin(url);
  http.setConnectTimeout(10000);
  http.setTimeout(10000);
  http.addHeader("User-Agent", "ESP32-Solar-Monitor");
  
  // Send GET request
  int httpResponseCode = http.GET();
  
  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    String response = http.getString();
    
    // Parse the JSON response
    DynamicJsonDocument responseDoc(2048); // Larger buffer for hourly data
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      if (responseDoc.containsKey("hourly_forecast")) {
        JsonArray hourlyArray = responseDoc["hourly_forecast"];
        Serial.println("Hourly Forecast Received:");
        
        for (JsonObject hour : hourlyArray) {
          String time = hour["time"];
          float temp = hour["temperature"];
          float humidity = hour["humidity"];
          
          Serial.printf("  %s: %.1f°C, %.1f%% humidity\n", time.substring(11).c_str(), temp, humidity);
        }
        
        success = true;
      }
    } else {
      Serial.print("JSON parsing failed: ");
      Serial.println(error.c_str());
    }
  } else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
    Serial.print("Error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  http.end();
  return success;
}
