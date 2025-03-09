#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Ticker.h>

// Wi-Fi credentials
const char *ssid = "sample12";
const char *password = "sample12";

// API endpoint to fetch lecture status (updated API)
const char *serverUrl = "https://21c5-117-217-104-210.ngrok-free.app/api/timetable_status";

// OLED display configuration
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Create a Ticker object for scrolling
Ticker scrollTicker;

String displayMessage = ""; // Message to scroll
int scrollPos = 0;          // Horizontal position for scrolling

// Function to fetch the latest lecture status from the server
void fetchLectureStatus() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        int httpResponseCode = http.GET();

        if (httpResponseCode == 200) {
            String response = http.getString();
            Serial.println("Server Response: " + response); // Debugging output

            // Parse JSON response (assuming the response is an array)
            DynamicJsonDocument doc(2048);
            DeserializationError error = deserializeJson(doc, response);
            if (error) {
                Serial.print("JSON parsing failed: ");
                Serial.println(error.c_str());
                return;
            }

            // Get the first lecture from the JSON array
            JsonObject latestLecture = doc[0];
            const char *subject_name = latestLecture["subject_name"];
            const char *lecture_status = latestLecture["lecture_status"];
            const char *cancellation_reason = latestLecture["cancellation_reason"]; // May be null

            // Build the display message. If the lecture is canceled, append the cancellation reason.
            displayMessage = String(subject_name) + ": " + lecture_status;
            if (strcmp(lecture_status, "Canceled") == 0) {
                // Use the provided cancellation reason or default message if empty
                if (cancellation_reason && strlen(cancellation_reason) > 0) {
                    displayMessage += ": " + String(cancellation_reason);
                } else {
                    displayMessage += ": No specific reason provided";
                }
            }
            
            Serial.println("Display Message: " + displayMessage);

            // Reset scrolling position
            scrollPos = SCREEN_WIDTH; // Start the text off-screen to the right
        } else {
            Serial.print("Error in HTTP request: ");
            Serial.println(httpResponseCode);
        }

        http.end();
    } else {
        Serial.println("WiFi not connected");
    }
}

// Function to scroll the text message
void scrollText() {
    display.clearDisplay(); // Clear the display

    // Draw the message at the current scroll position
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(scrollPos, 28); // Vertical center
    display.print(displayMessage);

    // Move text to the left by 1 pixel
    scrollPos--;

    // Reset position to create continuous scrolling if the text has fully scrolled off-screen
    int textWidth = displayMessage.length() * 6; // Approximate width of each character (6 pixels)
    if (scrollPos < -textWidth) {
        scrollPos = SCREEN_WIDTH; // Reset to the start position on the right
    }

    display.display(); // Update the OLED display
}

// Setup function
void setup() {
    Serial.begin(115200);

    // Initialize the OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println("SSD1306 allocation failed");
        for (;;)
            ; // Infinite loop if initialization fails
    }

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

    // Fetch the initial lecture status and start scrolling
    fetchLectureStatus();

    // Set up a Ticker to fetch new data every 60 seconds
    Ticker fetchTicker;
    fetchTicker.attach(60, fetchLectureStatus);

    // Set up a Ticker to scroll text every 100ms for smooth scrolling
    scrollTicker.attach(0.1, scrollText);
}

// Loop function
void loop() {
    // No need for additional logic here, as Ticker handles the timing
    delay(500); // Small delay to avoid CPU overuse
}
