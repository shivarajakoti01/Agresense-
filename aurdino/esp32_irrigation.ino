#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <TinyGPS++.h>
#include <HardwareSerial.h>

// ---------------- WIFI DETAILS ----------------
const char *ssid = "Shivaraja.ss";
const char *password = "7411132938";

// ---------------- SERVER URL ----------------
// Replace with your live ngrok or local server URL
const char *serverUrl = "http://10.169.20.56:5000/api/sensor";

// ---------------- GPS DETAILS ----------------
const int rxPin = 16; // GPS TX to ESP32 RX2 (GPIO 16)
const int txPin = 17; // GPS RX to ESP32 TX2 (GPIO 17)

TinyGPSPlus gps;
HardwareSerial neogps(2); // Use Hardware Serial2

// ---------------- SENSOR PINS ----------------
const int moisturePin = 34;
const int dhtPin = 4;
const int heatSensorPin = 5;
const int pumpPin = 26; // Onboard LED / Relay control pin

// Pump tracking state machine variables
bool pumpActive = false;
unsigned long pumpStartTime = 0;
const unsigned long pumpCycleDuration = 12000; // 12-second automatic shutoff
const float sufficientMoistureThreshold = 45.0; // Turn off pump if moisture exceeds this percentage

// Calibration constants for your soil moisture sensor
// (Adjust these values based on your Serial Monitor readings)
const int DRY_VALUE = 4095; // Raw sensor reading in dry air (approx. 0%)
const int WET_VALUE = 1500; // Raw sensor reading in water/very wet soil (approx. 100%)

// ---------------- DHT SENSOR ----------------
#define DHTTYPE DHT11
DHT dht(dhtPin, DHTTYPE);

void setup()
{

  Serial.begin(115200);

  // Start GPS Serial
  neogps.begin(9600, SERIAL_8N1, rxPin, txPin);

  // Start DHT
  dht.begin();

  // Heat sensor pin
  pinMode(heatSensorPin, INPUT_PULLUP);

  // Pump pin configuration
  pinMode(pumpPin, OUTPUT);
  digitalWrite(pumpPin, LOW); // Start with pump off

  // ---------------- CONNECT WIFI ----------------
  WiFi.begin(ssid, password);
  Serial.println("\nWiFi connection initiated in background.");
}

void processBackgroundTasks()
{
  // 1. Feed GPS
  while (neogps.available() > 0)
  {
    gps.encode(neogps.read());
  }

  // 2. Check serial command
  if (Serial.available() > 0)
  {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "TRIGGER_PUMP" || cmd == "PUMP_ON")
    {
      Serial.println("\n[EVENT] COMMAND_RECEIVED: PUMP_ON");
      digitalWrite(pumpPin, HIGH);
      pumpActive = true;
      pumpStartTime = millis();
    }
    else if (cmd == "PUMP_OFF")
    {
      Serial.println("\n[EVENT] COMMAND_RECEIVED: PUMP_OFF");
      digitalWrite(pumpPin, LOW);
      pumpActive = false;
    }
  }

  // 3. Auto-off after cycle duration
  if (pumpActive && (millis() - pumpStartTime >= pumpCycleDuration))
  {
    Serial.println("\n[EVENT] PUMP_CYCLE_COMPLETE: PUMP_OFF");
    digitalWrite(pumpPin, LOW);
    pumpActive = false;
  }

  yield();
}

void loop()
{

  // Process waiting events and feed GPS
  processBackgroundTasks();

  // Check WiFi
  if (WiFi.status() == WL_CONNECTED)
  {

    HTTPClient http;

    // ---------------- SOIL MOISTURE ----------------
    int rawMoisture = analogRead(moisturePin);

    // Convert to % using calibrated constants
    float moisturePercent = map(rawMoisture, DRY_VALUE, WET_VALUE, 0, 100);

    // Limit values
    if (moisturePercent < 0)
      moisturePercent = 0;

    if (moisturePercent > 100)
      moisturePercent = 100;

    // Local safety check: If pump is active but soil moisture has reached sufficient level
    if (pumpActive && moisturePercent >= sufficientMoistureThreshold)
    {
      Serial.print("\n[EVENT] [LOCAL] Moisture level (");
      Serial.print(moisturePercent);
      Serial.print("%) exceeds threshold (");
      Serial.print(sufficientMoistureThreshold);
      Serial.println("%). Turning pump OFF.");
      digitalWrite(pumpPin, LOW);
      pumpActive = false;
    }

    // ---------------- TEMPERATURE ----------------
    float temperature = dht.readTemperature();

    // DHT fail protection
    if (isnan(temperature))
    {

      Serial.println("DHT Sensor Error!");

      temperature = 25.0;
    }

    // ---------------- HEAT SENSOR ----------------
    bool heatDetected = !digitalRead(heatSensorPin); // Active-low: LOW (0) means fire/heat detected

    // ---------------- READ GPS LOCATION ----------------
    float latitude = 0.0;
    float longitude = 0.0;
    bool gpsValid = false;
    String locationSource = "none";

    if (gps.location.isValid() && gps.location.age() < 5000)
    {
      latitude = gps.location.lat();
      longitude = gps.location.lng();
      gpsValid = true;
      locationSource = "gps";
    }
    else
    {
      // GPS searching... Attempting IP Geolocation fallback
      static unsigned long lastIpCheck = 0;
      static float cachedLat = 0.0;
      static float cachedLon = 0.0;
      static bool hasCachedIpLoc = false;

      // Query IP-API every 5 minutes if we don't have a cached location yet
      if (!hasCachedIpLoc && (lastIpCheck == 0 || millis() - lastIpCheck > 300000))
      {
        lastIpCheck = millis();
        Serial.println("GPS searching... Querying IP Geolocation fallback...");
        HTTPClient httpLoc;
        httpLoc.begin("http://ip-api.com/json/");
        int httpCode = httpLoc.GET();
        if (httpCode == 200)
        {
          String payload = httpLoc.getString();
          int latIndex = payload.indexOf("\"lat\":");
          int lonIndex = payload.indexOf("\"lon\":");
          if (latIndex != -1 && lonIndex != -1)
          {
            int latEnd = payload.indexOf(",", latIndex);
            int lonEnd = payload.indexOf(",", lonIndex);
            if (latEnd != -1 && lonEnd != -1)
            {
              String latStr = payload.substring(latIndex + 6, latEnd);
              String lonStr = payload.substring(lonIndex + 6, lonEnd);
              cachedLat = latStr.toFloat();
              cachedLon = lonStr.toFloat();
              hasCachedIpLoc = true;
              Serial.print("IP Geolocation successful: ");
              Serial.print(cachedLat, 6);
              Serial.print(", ");
              Serial.println(cachedLon, 6);
            }
          }
        }
        httpLoc.end();
      }

      if (hasCachedIpLoc)
      {
        latitude = cachedLat;
        longitude = cachedLon;
        gpsValid = true; // Use IP coordinates
        locationSource = "ip";
      }
    }

    // ---------------- CREATE JSON ----------------
    String jsonString = "{";
    jsonString += "\"moisture\":" + String(moisturePercent, 2);
    jsonString += ",\"temperature\":" + String(temperature, 2);
    jsonString += ",\"heat_detected\":" + String(heatDetected ? "true" : "false");
    jsonString += ",\"gps_valid\":" + String(gpsValid ? "true" : "false");
    if (gpsValid)
    {
      jsonString += ",\"latitude\":" + String(latitude, 6);
      jsonString += ",\"longitude\":" + String(longitude, 6);
      jsonString += ",\"location_source\":\"" + locationSource + "\"";
    }
    jsonString += ",\"pump_status\":" + String(pumpActive ? "true" : "false");
    jsonString += "}";

    // ---------------- SEND DATA ----------------
    http.begin(serverUrl);
    http.setTimeout(60000); // 60 seconds timeout to allow Render service cold start

    http.addHeader("Content-Type", "application/json");

    int httpResponseCode = http.POST(jsonString);

    // ---------------- PRINT DATA ----------------
    Serial.println("\n------------------------");

    Serial.print("Raw Moisture: ");
    Serial.println(rawMoisture);

    Serial.print("Moisture: ");
    Serial.print(moisturePercent);
    Serial.println("%");

    Serial.print("Temperature: ");
    Serial.print(temperature);
    Serial.println(" C");

    Serial.print("Heat Pin Raw (Pin 5): ");
    Serial.println(digitalRead(heatSensorPin));

    Serial.print("Heat Detected: ");
    Serial.println(heatDetected);

    Serial.print("Pump Status: ");
    Serial.println(pumpActive ? "ON" : "OFF");

    if (gpsValid)
    {
      Serial.print("GPS Location: ");
      Serial.print(latitude, 6);
      Serial.print(", ");
      Serial.println(longitude, 6);
    }
    else
    {
      Serial.println("GPS Location: Searching for Satellite Lock...");
    }

    if (httpResponseCode > 0)
    {
      Serial.print("HTTP Response Code: ");
      Serial.println(httpResponseCode);

      String response = http.getString();
      Serial.print("Server Response: ");
      Serial.println(response);

      // Automatic Pump Trigger from AI Prediction response
      if (response.indexOf("\"water_needed\":true") != -1 || response.indexOf("\"water_needed\": true") != -1)
      {
        Serial.println("\n[EVENT] [AUTO] Server recommends: PUMP_ON");
        digitalWrite(pumpPin, HIGH);
        pumpActive = true;
        pumpStartTime = millis();
      }
      else if (response.indexOf("\"water_needed\":false") != -1 || response.indexOf("\"water_needed\": false") != -1)
      {
        if (pumpActive)
        {
          Serial.println("\n[EVENT] [AUTO] Server recommends: PUMP_OFF (Sufficient Moisture)");
          digitalWrite(pumpPin, LOW);
          pumpActive = false;
        }
      }
    }
    else
    {
      Serial.print("HTTP Error: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  }
  else
  {
    static unsigned long lastReconnectTry = 0;
    if (lastReconnectTry == 0 || millis() - lastReconnectTry > 10000)
    {
      lastReconnectTry = millis();
      Serial.println("WiFi Connecting/Disconnected! Reconnecting...");
      WiFi.reconnect();
    }
  }

  // Non-blocking wait: feed tasks and wait 10 seconds
  unsigned long startWait = millis();
  while (millis() - startWait < 10000)
  {
    processBackgroundTasks();
    delay(5); // Prevent CPU hogging
  }
}