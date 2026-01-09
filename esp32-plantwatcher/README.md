# ESP32-C6 Plant Moisture Monitor

A complete plant monitoring system using ESP32-C6 with soil moisture sensors, temperature/humidity monitoring, and relay control for automated watering.

## 🔧 Hardware Requirements

### Microcontroller
- **ESP32-C6 XIAO** (Seeed Studio)
  - Built-in WiFi
  - 12-bit ADC (0-4095)
  - 3.3V logic

### Sensors
- **5x Capacitive Soil Moisture Sensors** (Songhe or similar)
  - Input voltage: 3.3-5.5V (works with 3.3V ESP32)
  - Analog output (higher voltage = more moisture)
  - Corrosion resistant
  
- **1x DHT11 or DHT22** Temperature & Humidity Sensor (KeyeStudio module)
  - DHT11: ±2°C, ±5% RH (cheaper, good enough for plants)
  - DHT22: ±0.5°C, ±2% RH (more accurate)
  - 3-pin module with pull-up resistor included

### Relay Module
- **1x Relay Module** (5V or 3.3V compatible)
  - Controls watering pump/valve
  - Active HIGH or LOW (code uses HIGH = ON)

## 📐 Wiring Diagram

```
ESP32-C6 XIAO Pin Assignments:
┌─────────────────────────────────────┐
│                                     │
│  GPIO 0  → Soil Sensor 1 (Analog)  │
│  GPIO 1  → Soil Sensor 2 (Analog)  │
│  GPIO 2  → Soil Sensor 3 (Analog)  │
│  GPIO 3  → Soil Sensor 4 (Analog)  │
│  GPIO 4  → Soil Sensor 5 (Analog)  │
│                                     │
│  GPIO 20 → Relay Control (Digital) │
│  GPIO 21 → DHT Data Pin (Digital)  │
│                                     │
│  3.3V    → Sensor VCC (all)        │
│  GND     → Sensor GND (all)        │
│                                     │
└─────────────────────────────────────┘
```

### Soil Moisture Sensor Wiring (x5)
```
Sensor    →  ESP32-C6
─────────────────────
VCC       →  3.3V
GND       →  GND
AOUT      →  GPIO 0/1/2/3/4
```

### DHT Sensor Wiring (KeyeStudio Module)
```
DHT Module  →  ESP32-C6
─────────────────────────
VCC (+)     →  3.3V
GND (-)     →  GND
DATA (S)    →  GPIO 21
```

### Relay Module Wiring
```
Relay     →  ESP32-C6     →  Load (Pump/Valve)
────────────────────────────────────────────────
VCC       →  3.3V or 5V
GND       →  GND
IN        →  GPIO 20
COM       →  Power Source (+)
NO        →  Pump/Valve (+)
```

⚠️ **Important:** For high-power loads, use an external power supply. Don't power pumps directly from ESP32!

## 📚 Software Requirements

### Arduino IDE Setup

1. **Install Arduino IDE 2.x**
   - Download from: https://www.arduino.cc/en/software

2. **Add ESP32 Board Support**
   - Open Arduino IDE
   - Go to File → Preferences
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to Tools → Board → Boards Manager
   - Search for "esp32" and install "esp32 by Espressif Systems"

3. **Select Board**
   - Tools → Board → esp32 → "XIAO_ESP32C6"
   - Tools → Port → Select your COM port

### Required Libraries

Install these via Arduino IDE Library Manager (Sketch → Include Library → Manage Libraries):

1. **WiFi** (built-in with ESP32 core)
2. **WebServer** (built-in with ESP32 core)
3. **ArduinoJson** by Benoit Blanchon
   - Search: "ArduinoJson"
   - Install version 6.x or later
4. **DHT sensor library** by Adafruit
   - Search: "DHT sensor library"
   - Also install dependencies: "Adafruit Unified Sensor"

## ⚙️ Configuration

### 1. WiFi Setup

Open `esp32-plantwatcher.ino` and edit these lines at the top:

```cpp
// CHANGE THESE!
const char* ssid = "YOUR_WIFI_SSID";          // Your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";  // Your WiFi password
```

### 2. DHT Sensor Type

If using DHT22 instead of DHT11:

```cpp
const int DHT_TYPE = DHT22;  // Change from DHT11 to DHT22
```

### 3. Pin Configuration (Optional)

If you need to use different pins, edit:

```cpp
const int SENSOR_PINS[] = {0, 1, 2, 3, 4};  // Soil sensors
const int RELAY_PIN = 20;                    // Relay
const int DHT_PIN = 21;                      // DHT sensor
```

### 4. Sensor Calibration

For accurate moisture readings:

```cpp
const int DRY_VALUE = 1489;  // Adjust after dry calibration
const int WET_VALUE = 3350;  // Adjust after wet calibration
```

See **Calibration Procedure** below.

## 📤 Upload Instructions

1. Connect ESP32-C6 to computer via USB-C cable
2. Select correct board and port in Arduino IDE
3. Click Upload button (→)
4. Wait for compilation and upload
5. Open Serial Monitor (Tools → Serial Monitor, 115200 baud)
6. Watch for IP address to appear

Example output:
```
=====================================
  ESP32-C6 Plant Monitor
  For crespo.world
=====================================
✓ Relay initialized: OFF
✓ Initializing 5 soil moisture sensors...
✓ Initializing DHT temperature/humidity sensor...
Connecting to WiFi: YourNetwork
.........
✓ WiFi connected!
  IP address: 192.168.1.150
  Signal strength: -45 dBm
✓ HTTP server started
=====================================
   Access at: http://192.168.1.150
=====================================
```

**Write down the IP address!** You'll need it to access the web interface.

## 🌐 Web Interface Access

### Option 1: Local ESP32 Interface (Simple)

1. Open web browser on same WiFi network
2. Navigate to: `http://[ESP32-IP-ADDRESS]`
   - Example: `http://192.168.1.150`
3. You'll see a basic interface showing:
   - Soil moisture readings
   - Temperature and humidity
   - Relay control button

### Option 2: Full Web Interface (Recommended)

1. Open `plantwatcher.html` in a web browser
   - Can be from the repository folder
   - Or host it on crespo.world later
2. Enter the ESP32 IP address in the configuration
3. Click "Connect"
4. Full-featured interface with graphs and better UX

## 🔬 Calibration Procedure

For accurate moisture percentage readings:

### Step 1: Dry Calibration

1. Leave sensor in dry air (don't touch sensor plates)
2. Open Serial Monitor (115200 baud)
3. Wait for sensor readings to appear
4. Note the "raw" ADC value (typically ~1400-1600)
5. Update `DRY_VALUE` in code:
   ```cpp
   const int DRY_VALUE = 1489;  // Use your value
   ```

### Step 2: Wet Calibration

1. Submerge sensor in water (only the sensor part, not electronics!)
2. Wait for readings to stabilize
3. Note the "raw" ADC value (typically ~3200-3500)
4. Update `WET_VALUE` in code:
   ```cpp
   const int WET_VALUE = 3350;  // Use your value
   ```

### Step 3: Re-upload

Upload the sketch again with calibrated values. Now your readings will show:
- 0% = Dry air
- 100% = Submerged in water
- Typical soil range: 30-70%

## 🌱 Usage Guidelines

### Moisture Levels

- **🌵 0-30% (DRY)**: Water your plants!
- **🌿 30-60% (GOOD)**: Optimal moisture for most plants
- **💧 60-100% (WET)**: May be overwatered

*Note: Different plants have different needs. Succulents prefer drier soil (20-40%), while ferns like it wetter (50-70%).*

### Relay/Watering Control

- **Manual Mode**: Use web interface to turn relay ON/OFF
- **Automatic Mode**: Add logic in code (future feature)
  ```cpp
  // Example auto-watering logic (add to loop())
  if (moisturePercentages[0] < 30 && sensorConnected[0]) {
    digitalWrite(RELAY_PIN, HIGH);  // Turn on pump
    delay(5000);                    // Water for 5 seconds
    digitalWrite(RELAY_PIN, LOW);   // Turn off
  }
  ```

## 🔍 Troubleshooting

### WiFi Won't Connect

- ✅ Check SSID and password (case-sensitive!)
- ✅ Make sure WiFi is 2.4 GHz (ESP32-C6 doesn't support 5 GHz)
- ✅ Move closer to router
- ✅ Check Serial Monitor for error messages

### Sensor Shows "DISCONNECTED"

- ✅ Check wiring (VCC, GND, AOUT)
- ✅ Verify sensor is powered (should have LED on)
- ✅ Try different GPIO pin
- ✅ Check ADC value in Serial Monitor (should be 500-4000)

### DHT Sensor Not Working

- ✅ Check wiring (VCC to 3.3V, not 5V for some modules)
- ✅ Verify DHT_TYPE matches your sensor (DHT11 vs DHT22)
- ✅ Try different GPIO pin
- ✅ Check if module has pull-up resistor (most do)

### Relay Not Switching

- ✅ Check relay module LED (should light up)
- ✅ Verify relay pin connection
- ✅ Check if relay needs 5V signal (ESP32 outputs 3.3V)
  - Solution: Use a relay module designed for 3.3V logic
- ✅ Measure voltage on relay input pin with multimeter

### Web Interface Can't Connect

- ✅ Make sure you're on the same WiFi network
- ✅ Check IP address is correct (use Serial Monitor)
- ✅ Try pinging the ESP32: `ping 192.168.1.150`
- ✅ Disable any VPN or firewall temporarily
- ✅ Check browser console for CORS errors

### Readings are Unstable

- ✅ Add capacitor (100nF) between sensor VCC and GND
- ✅ Keep sensor wires short (<30cm)
- ✅ Route sensor wires away from power wires
- ✅ Increase averaging samples in code (line with `total += analogRead`)

## 🔐 Security Notes

- Default setup has no authentication
- Only use on trusted local networks
- Don't expose ESP32 directly to internet
- Consider adding basic authentication for production use

## 📊 API Reference

### GET /api/sensors

Returns current sensor readings:

```json
{
  "sensors": [
    {"id": 1, "pin": 0, "connected": true, "raw": 2450, "moisture": 45.3},
    {"id": 2, "pin": 1, "connected": false, "raw": 234, "moisture": null},
    ...
  ],
  "temperature": 22.5,
  "temperatureF": 72.5,
  "humidity": 55.0,
  "dhtConnected": true,
  "relay": "off",
  "timestamp": 123456
}
```

### POST /api/relay

Control relay state:

```json
{"state": "on"}      // Turn on
{"state": "off"}     // Turn off
{"state": "toggle"}  // Toggle current state
```

Response:
```json
{"relay": "on", "success": true}
```

### GET /api/status

Device status information:

```json
{
  "ip": "192.168.1.150",
  "rssi": -45,
  "ssid": "YourNetwork",
  "uptime": "1h 23m 45s",
  "uptimeMs": 5025000,
  "relay": "off",
  "freeHeap": 234567,
  "chipModel": "ESP32-C6"
}
```

## 🚀 Next Steps

1. ✅ Get basic system working
2. ✅ Calibrate sensors
3. ⬜ Add automatic watering schedule
4. ⬜ Add data logging (SD card or cloud)
5. ⬜ Implement push notifications
6. ⬜ Add multiple plant profiles
7. ⬜ Create mobile app

## 📝 License

Part of the crespo.world project.

## 🙏 Credits

Created for plant monitoring by @alexcrespo98
