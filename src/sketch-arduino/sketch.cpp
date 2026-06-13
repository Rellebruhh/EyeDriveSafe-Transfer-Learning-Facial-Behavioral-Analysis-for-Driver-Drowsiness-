
#include <Arduino_RouterBridge.h>
#include <Modulino.h>

// ==================== MODULINO OBJECTS ====================
ModulinoBuzzer buzzer;
ModulinoPixels leds;

// ==================== CONSTANTS ====================
const int NUM_LEDS = 8;

// Buzzer patterns (milliseconds)
const unsigned long WARNING_BEEP_ON  = 200;
const unsigned long WARNING_BEEP_OFF = 800;
const unsigned long ALERT_BEEP_ON    = 100;
const unsigned long ALERT_BEEP_OFF   = 100;

// LED pulse timing for WARNING state (amber breathe)
const unsigned long PULSE_PERIOD = 1500;  // ms for one full pulse cycle

// ==================== STATE ====================
int currentState = 0;          // 0=AWAKE, 1=WARNING, 2=ALERT
int previousState = -1;        // Track transitions for LED updates
unsigned long lastBuzzerToggle = 0;
bool buzzerOn = false;

// ==================== BRIDGE CALLBACK ====================
void set_alert_state(int state) {
    if (state < 0 || state > 2) return;
    currentState = state;
}

// ==================== LED PATTERNS ====================

void setAllLeds(uint8_t r, uint8_t g, uint8_t b, uint8_t brightness) {
    for (int i = 0; i < NUM_LEDS; i++) {
        leds.set(i, r, g, b, brightness);
    }
    leds.show();
}

void clearAllLeds() {
    leds.clear();
    leds.show();
}

void updateLedsAwake() {
    // Solid dim green -- system active, driver alert
    setAllLeds(0, 255, 0, 10);
}

void updateLedsWarning() {
    // Amber/yellow pulsing -- brightness oscillates using sine-like ramp
    unsigned long phase = millis() % PULSE_PERIOD;
    // Triangle wave: ramp up first half, ramp down second half
    uint8_t brightness;
    if (phase < PULSE_PERIOD / 2) {
        brightness = map(phase, 0, PULSE_PERIOD / 2, 5, 40);
    } else {
        brightness = map(phase, PULSE_PERIOD / 2, PULSE_PERIOD, 40, 5);
    }
    setAllLeds(255, 165, 0, brightness);
}

void updateLedsAlert() {
    // Red rapid flash -- 250ms on, 250ms off
    unsigned long phase = millis() % 500;
    if (phase < 250) {
        setAllLeds(255, 0, 0, 50);
    } else {
        clearAllLeds();
    }
}

// ==================== BUZZER PATTERNS ====================

void updateBuzzer() {
    unsigned long now = millis();

    switch (currentState) {
        case 0:  // AWAKE - silent
            if (buzzerOn) {
                buzzer.noTone();
                buzzerOn = false;
            }
            break;

        case 1:  // WARNING - slow intermittent beep (1kHz)
            if (buzzerOn) {
                if (now - lastBuzzerToggle >= WARNING_BEEP_ON) {
                    buzzer.noTone();
                    buzzerOn = false;
                    lastBuzzerToggle = now;
                }
            } else {
                if (now - lastBuzzerToggle >= WARNING_BEEP_OFF) {
                    buzzer.tone(1000, WARNING_BEEP_ON);
                    buzzerOn = true;
                    lastBuzzerToggle = now;
                }
            }
            break;

        case 2:  // ALERT - rapid beep (2kHz)
            if (buzzerOn) {
                if (now - lastBuzzerToggle >= ALERT_BEEP_ON) {
                    buzzer.noTone();
                    buzzerOn = false;
                    lastBuzzerToggle = now;
                }
            } else {
                if (now - lastBuzzerToggle >= ALERT_BEEP_OFF) {
                    buzzer.tone(2000, ALERT_BEEP_ON);
                    buzzerOn = true;
                    lastBuzzerToggle = now;
                }
            }
            break;
    }
}

// ==================== SETUP ====================

void setup() {
    Serial.begin(115200);

    // Initialize Modulino I2C bus
    Modulino.begin();

    // Initialize individual modules
    buzzer.begin();
    leds.begin();

    // Clear LEDs on boot
    clearAllLeds();

    // Startup confirmation: double beep + white flash
    buzzer.tone(1000, 150);
    setAllLeds(255, 255, 255, 30);
    delay(200);
    clearAllLeds();
    delay(100);
    buzzer.tone(1500, 150);
    setAllLeds(255, 255, 255, 30);
    delay(200);
    clearAllLeds();

    // Register Bridge callbacks
    Bridge.begin();
    Bridge.provide("set_alert_state", set_alert_state);

    // Wait for MPU (Python) to connect
    auto start = Bridge.call("linux_started");
    start.result();

    // Connection confirmed: single beep + green flash
    buzzer.tone(2000, 100);
    setAllLeds(0, 255, 0, 30);
    delay(300);

    // Set resting state
    updateLedsAwake();

    Serial.println("==================================================");
    Serial.println("  EYEDRIVESAFE - MCU Ready (Modulino Edition)");
    Serial.println("  Buzzer: Modulino Buzzer (I2C)");
    Serial.println("  LEDs:   Modulino Pixels (I2C, 8x RGB)");
    Serial.println("  Waiting for detections...");
    Serial.println("==================================================");
}

// ==================== LOOP ====================

void loop() {
    // Update buzzer pattern
    updateBuzzer();

    // Update LED pattern
    switch (currentState) {
        case 0:  // AWAKE
            updateLedsAwake();
            break;
        case 1:  // WARNING
            updateLedsWarning();  
            break;
        case 2:  // ALERT
            updateLedsAlert();    
            break;
    }

    previousState = currentState;
}
