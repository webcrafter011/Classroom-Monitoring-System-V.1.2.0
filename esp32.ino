#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Ticker.h>

// Wi-Fi credentials
const char *ssid = "sample12";
const char *password = "sample12";

// API endpoint to fetch the latest lecture status
const char *serverUrl = "https://21c5-117-217-104-210.ngrok-free.app/get_latest_lecture_status";

// OLED display configuration
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Create a Ticker object for scrolling
Ticker scrollTicker;

String displayMessage = ""; // Message to scroll (formatted as teacher: subject: lecture time: status: cancellation reason if any)
int scrollPos = 0;          // Horizontal position for scrolling

// Function to fetch the latest lecture status from the server
void fetchLectureStatus() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    int httpResponseCode = http.GET();

    if (httpResponseCode == 200) {
      String response = http.getString();
      Serial.println("Server Response: " + response);

      // Parse JSON response
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, response);
      if (error) {
        Serial.print("JSON parsing failed: ");
        Serial.println(error.c_str());
        return;
      }

      // Get the display message from the JSON response
      displayMessage = doc["display_message"].as<String>();
      Serial.println("Display Message: " + displayMessage);

      // Reset scrolling position (start off-screen to the right)
      scrollPos = SCREEN_WIDTH;
    } else {
      Serial.print("Error in HTTP request: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  } else {
    Serial.println("WiFi not connected");
  }
}

// Function to scroll the text message on the OLED display
void scrollText() {
  display.clearDisplay(); // Clear the display

  // Set text properties
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(scrollPos, 28); // Vertically centered
  display.print(displayMessage);

  // Move text to the left by 1 pixel
  scrollPos--;

  // Calculate approximate width of the text (assuming ~6 pixels per character)
  int textWidth = displayMessage.length() * 6;
  // Reset the scroll position when the text has completely scrolled off the screen
  if (scrollPos < -textWidth) {
    scrollPos = SCREEN_WIDTH;
  }

  display.display(); // Update the OLED display
}

void setup() {
  Serial.begin(115200);

  // Initialize the OLED display
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 allocation failed");
    for (;;)
      ; // Infinite loop if initialization fails
  }

  // Display initial connection status
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Connecting...");
  display.display();

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi Connected!");
  display.display();

  // Fetch the initial lecture status
  fetchLectureStatus();

  // Set up a Ticker to fetch new lecture data every 60 seconds
  Ticker fetchTicker;
  fetchTicker.attach(60, fetchLectureStatus);

  // Set up a Ticker to scroll the text every 100ms for smooth scrolling
  scrollTicker.attach(0.1, scrollText);
}

void loop() {
  // No additional logic needed in loop; Ticker handles timing.
  delay(500);
}
