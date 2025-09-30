#include <WiFi.h>
#include <HTTPClient.h>

// WiFi credentials
const char* ssid = "JioFiber-f9yyR";
const char* password = "af4PCybp9eRFuGba";

// Flask server endpoint
const char* serverName = "https://ruthlessthingsboard.onrender.com/esp32-data";

// Data variables
float frequency, powerFactor;
float voltage, current, power, energy;
int inverterLoad;
float solarVoltage, solarCurrent, solarPower;
float batteryVoltage, batteryPercentage;
float lightIntensity;

void makeRandomData() {
  // Grid / inverter side
  frequency = random(495, 505) / 10.0;       // ~49.5Hz – 50.5Hz
  powerFactor = random(85, 100) / 100.0;     // 0.85 – 0.99
  voltage = random(215, 231);                // 215 – 230 V
  current = random(1, 10);                   // 1 – 10 A
  power = voltage * current * powerFactor;   // watts
  energy = random(10, 50);                   // Wh
  inverterLoad = random(50, 200);            // W load demand

  // Solar panel (6V, 60mA max)
  solarVoltage = random(500, 620) / 100.0;   // 5.0 – 6.2 V
  solarCurrent = random(10, 61) / 1000.0;    // 0.01 – 0.06 A
  solarPower = solarVoltage * solarCurrent;  // W (~0–0.36W)

  // Battery (4V Li-ion range)
  batteryVoltage = random(350, 421) / 100.0; // 3.5 – 4.2 V
  batteryPercentage = map(batteryVoltage * 100, 350, 420, 0, 100);
  if (batteryPercentage < 0) batteryPercentage = 0;
  if (batteryPercentage > 100) batteryPercentage = 100;

  // Light intensity (lux)
  lightIntensity = random(200, 1200);        // arbitrary range
}

void sendData() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    return;
  }

  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "application/json");

  // JSON payload
  String json = "{";
  json += "\"inverterLoad\":" + String(inverterLoad) + ",";
  json += "\"frequency\":" + String(frequency, 2) + ",";
  json += "\"powerFactor\":" + String(powerFactor, 2) + ",";
  json += "\"voltage\":" + String(voltage, 2) + ",";
  json += "\"current\":" + String(current, 2) + ",";
  json += "\"power\":" + String(power, 2) + ",";
  json += "\"energy\":" + String(energy, 2) + ",";
  json += "\"solarVoltage\":" + String(solarVoltage, 2) + ",";
  json += "\"solarCurrent\":" + String(solarCurrent, 3) + ",";
  json += "\"solarPower\":" + String(solarPower, 3) + ",";
  json += "\"batteryVoltage\":" + String(batteryVoltage, 2) + ",";
  json += "\"batteryPercentage\":" + String(batteryPercentage, 1) + ",";
  json += "\"lightIntensity\":" + String(lightIntensity, 1);
  json += "}";

  int httpResponseCode = http.POST(json);

  if (httpResponseCode > 0) {
    Serial.print("Response code: ");
    Serial.println(httpResponseCode);
    String response = http.getString();
    Serial.print("Server response: ");
    Serial.println(response);
  } else {
    Serial.print("Error in POST: ");
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Connected!");
}

void loop() {
  makeRandomData();
  sendData();
  delay(15000); // send every 15 seconds
}
