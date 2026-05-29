# Connecting Hardware to AgriSense AI

To connect your physical hardware (like an ESP32, NodeMCU, or Arduino with Wi-Fi) to your web application, your microcontroller needs to read the physical sensors and send that data to the Flask backend via an **HTTP POST request**.

## 1. The API Endpoint

Your Flask backend has a dedicated endpoint specifically for receiving hardware data:
- **URL**: `http://<YOUR_COMPUTER_IP_ADDRESS>:5000/api/sensor`
- **Method**: `POST`
- **Content-Type**: `application/json`

> [!IMPORTANT]
> When testing with hardware, you cannot use `localhost` or `127.0.0.1` in your ESP32 code. You must use the actual IPv4 address of the computer running the Flask server on your local Wi-Fi network (e.g., `192.168.1.100`).

## 2. The Data Format

The backend expects a JSON payload containing `moisture` (as a percentage 0-100) and `temperature` (in Celsius).

```json
{
  "moisture": 45.5,
  "temperature": 28.2
}
```

## 3. Sample ESP32 / Arduino Code

Here is a complete example of how to write the code for an ESP32 using the Arduino IDE. 

### Prerequisites:
Make sure you have the `ArduinoJson` library installed in your Arduino IDE.

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- Configuration ---
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// Replace with the IP address of the computer running the Flask app
const char* serverUrl = "http://192.168.1.100:5000/api/sensor"; 

// Hardware Pins
const int moisturePin = 34; // Analog pin for soil moisture
const int dhtPin = 4;       // Pin for Temperature sensor

void setup() {
  Serial.begin(115200);
  
  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // 1. Read actual sensors (replace with actual sensor library logic)
    int rawMoisture = analogRead(moisturePin); 
    
    // Map raw analog value (e.g., 0-4095 on ESP32) to 0-100%
    // Note: Calibrate these values based on your specific sensor!
    float moisturePercent = map(rawMoisture, 4095, 0, 0, 100); 
    
    // Read temperature (mocked here, use DHT library for real sensor)
    float temperature = 25.5; 

    // 2. Create JSON Payload
    StaticJsonDocument<200> doc;
    doc["moisture"] = moisturePercent;
    doc["temperature"] = temperature;
    
    String jsonString;
    serializeJson(doc, jsonString);

    // 3. Send HTTP POST Request
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode > 0) {
      Serial.print("Data sent successfully. HTTP Response code: ");
      Serial.println(httpResponseCode);
      String response = http.getString();
      Serial.println(response); // The AI Prediction will be returned here!
    } else {
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  }
  
  // Wait 10 seconds before sending the next reading
  delay(10000); 
}
```

## 4. Testing the Connection

1. Connect both your computer (running the Flask app) and the ESP32 to the **same Wi-Fi network**.
2. Find your computer's IP address (open Command Prompt and type `ipconfig`, look for `IPv4 Address`).
3. Update `serverUrl` in the ESP32 code with that IP address.
4. Upload the code to your ESP32.
5. Open the Serial Monitor in the Arduino IDE to watch the ESP32 send data.
6. Open your browser to `http://localhost:5000/dashboard` and watch the live graphs update automatically as the hardware sends real-world data!
