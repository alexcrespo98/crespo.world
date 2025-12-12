/*
 * ESP32-C6 Plant Moisture Monitoring System
 * 
 * Hardware:
 * - Board: ESP32-C6 XIAO Seeed Studio
 * - Sensors: 
 *   - 5x Songhe Capacitive Soil Moisture Sensors (3.3-5.5V)
 *   - 1x DHT11/DHT22 Temperature & Humidity Sensor (KeyeStudio module)
 * - Relay: 1x relay module
 * 
 * Features:
 * - WiFi connectivity (configurable)
 * - Web server with REST API
 * - Real-time moisture, temperature, and humidity monitoring
 * - Relay control for watering
 * - Status reporting
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ============================================
// CONFIGURATION - CHANGE THESE FOR YOUR SETUP
// ============================================

// WiFi Configuration - CHANGE THESE!
const char* ssid = "YOUR_WIFI_SSID";          // Change to your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";  // Change to your WiFi password

// Hardware Configuration - Adjust pins based on your wiring
const int SENSOR_PINS[] = {0, 1, 2, 3, 4};  // GPIO pins for soil moisture sensors (analog capable)
const int NUM_SENSORS = 5;                   // Number of soil moisture sensors
const int RELAY_PIN = 20;                    // GPIO pin for relay control
const int DHT_PIN = 21;                      // GPIO pin for DHT sensor
const int DHT_TYPE = DHT11;                  // DHT11 or DHT22 (change to DHT22 if using that model)

// Calibration values - ADJUST THESE based on your sensors
// To calibrate:
// 1. Put sensor in dry air and note the ADC value (Serial monitor)
// 2. Put sensor in water and note the ADC value
// 3. Update DRY_VALUE and WET_VALUE below
const int DRY_VALUE = 1489;      // ADC value for dry soil (typical ~1489)
const int WET_VALUE = 3350;      // ADC value for wet soil (typical ~3350)

// Sensor reading thresholds
const int SENSOR_MIN_VALID = 500;   // Below this = disconnected
const int SENSOR_MAX_VALID = 4000;  // Above this = error

// ADC Configuration for ESP32-C6
const int ADC_MAX = 4095;        // 12-bit ADC
const float ADC_VREF = 3.3;      // 3.3V reference

// ============================================
// END OF CONFIGURATION
// ============================================

// Web Server
WebServer server(80);

// DHT Sensor
DHT dht(DHT_PIN, DHT_TYPE);

// Global variables
bool relayState = false;
unsigned long startTime = 0;
int sensorReadings[NUM_SENSORS];
float moisturePercentages[NUM_SENSORS];
bool sensorConnected[NUM_SENSORS];
float temperature = 0.0;
float humidity = 0.0;
bool dhtConnected = false;

// Function prototypes
void setupWiFi();
void setupServer();
void readSensors();
void readDHT();
float convertToMoisture(int adcValue);
void handleRoot();
void handleGetSensors();
void handlePostRelay();
void handleGetStatus();
void handleNotFound();
String getUptimeString();
void printWiFiInstructions();

void setup() {
  // Initialize Serial for debugging
  Serial.begin(115200);
  delay(1000);  // Give serial time to initialize
  Serial.println("\n\n");
  Serial.println("=====================================");
  Serial.println("  ESP32-C6 Plant Monitor");
  Serial.println("  For crespo.world");
  Serial.println("=====================================");
  
  // Check WiFi configuration
  if (strcmp(ssid, "YOUR_WIFI_SSID") == 0) {
    Serial.println("\n⚠️  WARNING: WiFi not configured!");
    printWiFiInstructions();
    // Continue anyway for testing
  }
  
  // Initialize relay pin
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  relayState = false;
  Serial.println("✓ Relay initialized: OFF");
  
  // Initialize sensor pins (ADC pins are input by default)
  Serial.print("✓ Initializing ");
  Serial.print(NUM_SENSORS);
  Serial.println(" soil moisture sensors...");
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(SENSOR_PINS[i], INPUT);
  }
  
  // Initialize DHT sensor
  Serial.println("✓ Initializing DHT temperature/humidity sensor...");
  dht.begin();
  
  // Connect to WiFi
  setupWiFi();
  
  // Setup web server routes
  setupServer();
  
  // Start web server
  server.begin();
  Serial.println("✓ HTTP server started");
  Serial.println("=====================================");
  Serial.print("   Access at: http://");
  Serial.println(WiFi.localIP());
  Serial.println("=====================================\n");
  
  // Record start time
  startTime = millis();
  
  // Do initial sensor read
  readSensors();
  readDHT();
}

void loop() {
  // Handle web server requests
  server.handleClient();
  
  // Read soil sensors periodically (every 2 seconds)
  static unsigned long lastSoilReadTime = 0;
  if (millis() - lastSoilReadTime >= 2000) {
    readSensors();
    lastSoilReadTime = millis();
  }
  
  // Read DHT sensor periodically (every 5 seconds - DHT sensors are slow)
  static unsigned long lastDHTReadTime = 0;
  if (millis() - lastDHTReadTime >= 5000) {
    readDHT();
    lastDHTReadTime = millis();
  }
}

void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  Serial.println("(This may take 10-15 seconds...)");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✓ WiFi connected!");
    Serial.print("  IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("  Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("✗ WiFi connection failed!");
    Serial.println("  Device will continue running but web interface won't work.");
    Serial.println("  Check your WiFi credentials in the code.");
  }
}

void printWiFiInstructions() {
  Serial.println("=====================================");
  Serial.println("  SETUP INSTRUCTIONS");
  Serial.println("=====================================");
  Serial.println("1. Open this file in Arduino IDE");
  Serial.println("2. Find the WiFi configuration section at the top");
  Serial.println("3. Change these lines:");
  Serial.println("   const char* ssid = \"YOUR_WIFI_SSID\";");
  Serial.println("   const char* password = \"YOUR_WIFI_PASSWORD\";");
  Serial.println("4. Upload the sketch again");
  Serial.println("=====================================\n");
}

void setupServer() {
  // CORS headers for all responses
  server.enableCORS(true);
  
  // Route handlers
  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/sensors", HTTP_GET, handleGetSensors);
  server.on("/api/relay", HTTP_POST, handlePostRelay);
  server.on("/api/status", HTTP_GET, handleGetStatus);
  server.onNotFound(handleNotFound);
}

void readSensors() {
  Serial.println("📊 Reading soil sensors:");
  
  for (int i = 0; i < NUM_SENSORS; i++) {
    // Read ADC value (take average of 5 readings for stability)
    int total = 0;
    for (int j = 0; j < 5; j++) {
      total += analogRead(SENSOR_PINS[i]);
      delay(10);
    }
    int rawValue = total / 5;
    sensorReadings[i] = rawValue;
    
    // Check if sensor is connected
    if (rawValue < SENSOR_MIN_VALID || rawValue > SENSOR_MAX_VALID) {
      sensorConnected[i] = false;
      moisturePercentages[i] = -1;
      Serial.print("  Sensor ");
      Serial.print(i + 1);
      Serial.print(" (GPIO");
      Serial.print(SENSOR_PINS[i]);
      Serial.println("): ❌ DISCONNECTED");
    } else {
      sensorConnected[i] = true;
      moisturePercentages[i] = convertToMoisture(rawValue);
      Serial.print("  Sensor ");
      Serial.print(i + 1);
      Serial.print(" (GPIO");
      Serial.print(SENSOR_PINS[i]);
      Serial.print("): ");
      Serial.print(rawValue);
      Serial.print(" → ");
      Serial.print(moisturePercentages[i], 1);
      Serial.print("% ");
      
      // Add visual indicator
      if (moisturePercentages[i] < 30) {
        Serial.println("🌵 DRY");
      } else if (moisturePercentages[i] < 60) {
        Serial.println("🌿 GOOD");
      } else {
        Serial.println("💧 WET");
      }
    }
  }
}

void readDHT() {
  // Read temperature and humidity
  float h = dht.readHumidity();
  float t = dht.readTemperature();  // Celsius
  
  // Check if readings are valid
  if (isnan(h) || isnan(t)) {
    dhtConnected = false;
    Serial.println("🌡️  DHT Sensor: ❌ DISCONNECTED or ERROR");
  } else {
    dhtConnected = true;
    humidity = h;
    temperature = t;
    Serial.print("🌡️  Temperature: ");
    Serial.print(temperature, 1);
    Serial.print("°C (");
    Serial.print(temperature * 9.0 / 5.0 + 32.0, 1);
    Serial.println("°F)");
    Serial.print("💧 Humidity: ");
    Serial.print(humidity, 1);
    Serial.println("%");
  }
  Serial.println();
}

float convertToMoisture(int adcValue) {
  // Convert ADC value to moisture percentage
  // Higher voltage = more moisture for capacitive sensors
  // Map DRY_VALUE (0%) to WET_VALUE (100%)
  
  if (adcValue <= DRY_VALUE) {
    return 0.0;
  } else if (adcValue >= WET_VALUE) {
    return 100.0;
  } else {
    float percentage = ((float)(adcValue - DRY_VALUE) / (float)(WET_VALUE - DRY_VALUE)) * 100.0;
    return constrain(percentage, 0.0, 100.0);
  }
}

void handleRoot() {
  // Serve simple web interface HTML
  String html = R"(
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ESP32 Plant Monitor</title>
  <style>
    body { 
      font-family: monospace; 
      background: #000; 
      color: #0f0; 
      padding: 20px;
      text-align: center;
      max-width: 600px;
      margin: 0 auto;
    }
    h1 { color: #0f0; margin-bottom: 10px; }
    .info { color: #0a0; font-size: 14px; margin-bottom: 20px; }
    .section { 
      border: 2px solid #0f0; 
      padding: 15px; 
      margin: 20px 0;
      background: #001100;
    }
    .sensor { 
      margin: 8px 0; 
      padding: 8px; 
      border: 1px solid #0f0; 
      background: #000;
    }
    .relay-btn {
      background: #000;
      color: #0f0;
      border: 2px solid #0f0;
      padding: 15px 30px;
      font-size: 18px;
      cursor: pointer;
      margin: 10px;
      width: 200px;
    }
    .relay-btn:hover { background: #0f0; color: #000; }
    .relay-on { background: #0f0; color: #000; }
    .env { font-size: 20px; margin: 10px 0; }
  </style>
</head>
<body>
  <h1>🌱 ESP32 Plant Monitor</h1>
  <p class="info">Local interface - For full featured control, visit<br><a href="https://crespo.world/plantwatcher.html" style="color:#0f0">crespo.world/plantwatcher.html</a></p>
  
  <div class="section">
    <h2>Environment</h2>
    <div id="environment"></div>
  </div>
  
  <div class="section">
    <h2>Soil Moisture</h2>
    <div id="sensors"></div>
  </div>
  
  <div class="section">
    <h2>Watering Control</h2>
    <button class="relay-btn" id="relayBtn" onclick="toggleRelay()">Relay: Loading...</button>
  </div>
  
  <script>
    async function loadData() {
      try {
        const res = await fetch('/api/sensors');
        const data = await res.json();
        
        // Environment
        let envHtml = '';
        if (data.temperature !== null && data.temperature !== undefined) {
          const tempC = data.temperature.toFixed(1);
          const tempF = (data.temperature * 9/5 + 32).toFixed(1);
          const hum = data.humidity.toFixed(1);
          envHtml += '<div class="env">🌡️ ' + tempC + '°C (' + tempF + '°F)</div>';
          envHtml += '<div class="env">💧 ' + hum + '% Humidity</div>';
        } else {
          envHtml = '<div style="color:#f00">DHT sensor not connected</div>';
        }
        document.getElementById('environment').innerHTML = envHtml;
        
        // Soil sensors
        let html = '';
        data.sensors.forEach(s => {
          const status = s.connected ? (s.moisture.toFixed(1) + '%') : 'Disconnected';
          const icon = s.connected ? (s.moisture < 30 ? '🌵' : s.moisture < 60 ? '🌿' : '💧') : '❌';
          html += '<div class="sensor">' + icon + ' Sensor ' + s.id + ': ' + status + '</div>';
        });
        document.getElementById('sensors').innerHTML = html;
        
        // Relay state
        const relayBtn = document.getElementById('relayBtn');
        relayBtn.textContent = 'Relay: ' + data.relay.toUpperCase();
        relayBtn.className = data.relay === 'on' ? 'relay-btn relay-on' : 'relay-btn';
      } catch(e) {
        console.error('Failed to load data:', e);
      }
    }
    
    async function toggleRelay() {
      try {
        await fetch('/api/relay', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({state: 'toggle'})
        });
        setTimeout(loadData, 100);
      } catch(e) {
        alert('Failed to toggle relay');
      }
    }
    
    setInterval(loadData, 2000);
    loadData();
  </script>
</body>
</html>
  )";
  
  server.send(200, "text/html", html);
}

void handleGetSensors() {
  // Create JSON response with sensor data
  StaticJsonDocument<1536> doc;
  JsonArray sensors = doc.createNestedArray("sensors");
  
  for (int i = 0; i < NUM_SENSORS; i++) {
    JsonObject sensor = sensors.createNestedObject();
    sensor["id"] = i + 1;
    sensor["pin"] = SENSOR_PINS[i];
    sensor["connected"] = sensorConnected[i];
    sensor["raw"] = sensorReadings[i];
    
    if (sensorConnected[i]) {
      sensor["moisture"] = round(moisturePercentages[i] * 10) / 10.0;  // Round to 1 decimal
    } else {
      sensor["moisture"] = nullptr;
    }
  }
  
  // Add DHT sensor data
  if (dhtConnected) {
    doc["temperature"] = round(temperature * 10) / 10.0;
    doc["temperatureF"] = round((temperature * 9.0 / 5.0 + 32.0) * 10) / 10.0;
    doc["humidity"] = round(humidity * 10) / 10.0;
  } else {
    doc["temperature"] = nullptr;
    doc["temperatureF"] = nullptr;
    doc["humidity"] = nullptr;
  }
  doc["dhtConnected"] = dhtConnected;
  
  doc["relay"] = relayState ? "on" : "off";
  doc["timestamp"] = millis();
  
  String response;
  serializeJson(doc, response);
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
  
  // Serial.println("API: Sent sensor data");  // Commented out to reduce spam
}

void handlePostRelay() {
  // Handle CORS preflight
  if (server.method() == HTTP_OPTIONS) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(200);
    return;
  }
  
  // Parse JSON body
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, server.arg("plain"));
  
  if (error) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }
  
  // Get desired state
  const char* stateStr = doc["state"];
  bool newState = relayState;
  
  if (strcmp(stateStr, "on") == 0) {
    newState = true;
  } else if (strcmp(stateStr, "off") == 0) {
    newState = false;
  } else if (strcmp(stateStr, "toggle") == 0) {
    newState = !relayState;
  } else {
    server.send(400, "application/json", "{\"error\":\"Invalid state. Use 'on', 'off', or 'toggle'\"}");
    return;
  }
  
  // Update relay
  relayState = newState;
  digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
  
  Serial.print("API: Relay turned ");
  Serial.println(relayState ? "ON" : "OFF");
  
  // Send response
  StaticJsonDocument<200> response;
  response["relay"] = relayState ? "on" : "off";
  response["success"] = true;
  
  String responseStr;
  serializeJson(response, responseStr);
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", responseStr);
}

void handleGetStatus() {
  // Create JSON response with device status
  StaticJsonDocument<512> doc;
  
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["ssid"] = WiFi.SSID();
  doc["uptime"] = getUptimeString();
  doc["uptimeMs"] = millis() - startTime;
  doc["relay"] = relayState ? "on" : "off";
  doc["freeHeap"] = ESP.getFreeHeap();
  doc["chipModel"] = ESP.getChipModel();
  
  String response;
  serializeJson(doc, response);
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
  
  Serial.println("API: Sent status data");
}

void handleNotFound() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(404, "application/json", "{\"error\":\"Not found\"}");
}

String getUptimeString() {
  unsigned long uptime = millis() - startTime;
  unsigned long seconds = uptime / 1000;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  unsigned long days = hours / 24;
  
  seconds = seconds % 60;
  minutes = minutes % 60;
  hours = hours % 24;
  
  String result = "";
  if (days > 0) {
    result += String(days) + "d ";
  }
  if (hours > 0 || days > 0) {
    result += String(hours) + "h ";
  }
  if (minutes > 0 || hours > 0 || days > 0) {
    result += String(minutes) + "m ";
  }
  result += String(seconds) + "s";
  
  return result;
}
