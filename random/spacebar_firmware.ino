#include <Keyboard.h>

// Teyleten Robot Type-C Pro Micro (ATmega32U4, 5V/16MHz)
// Wiring:
// - Momentary normally-open switch leg 1 -> pin 2
// - Momentary normally-open switch leg 2 -> GND
// INPUT_PULLUP is enabled, so no external resistor is needed.
//
// LED wiring:
// - LED anode (+) -> 330 ohm resistor -> pin 9
// - LED cathode (-) -> GND
// LED blinks at 2 Hz while the timer is idle (ready to start).
// LED goes solid while the timer is running.

const uint8_t BUTTON_PIN = 2;
const uint8_t LED_PIN    = 9;

// 20ms keeps bounce suppression while preserving minimum press-to-keystroke latency.
const unsigned long DEBOUNCE_MS     = 20;
const unsigned long BLINK_INTERVAL_MS = 250; // 2 Hz blink

bool buttonPressed    = false;
bool waitingForRelease = false;
unsigned long debounceUntil = 0;

// Tracks whether the timer on the page is running.
// Toggled on every spacebar send (press 1 = start, press 2 = stop, ...).
bool timerRunning = false;

bool ledState = false;
unsigned long lastBlinkToggle = 0;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Keyboard.begin();
}

void loop() {
  const unsigned long now = millis();
  const bool isPressed = (digitalRead(BUTTON_PIN) == LOW);

  // Fast-path press detection: send space immediately on the first LOW edge.
  // Then lock out additional edges for DEBOUNCE_MS.
  if (!waitingForRelease && !buttonPressed && isPressed) {
    // Keep explicit press/release to minimize and control key-down timing on the edge.
    Keyboard.press(' ');
    Keyboard.release(' ');

    timerRunning = !timerRunning;

    buttonPressed     = true;
    waitingForRelease = true;
    debounceUntil     = now + DEBOUNCE_MS;

    // Update LED immediately so solid/off feedback is instant on press.
    if (timerRunning) {
      digitalWrite(LED_PIN, HIGH);
      ledState = true;
    }
    return;
  }

  // Keep ignoring bounce while debounce lockout is active.
  if (now < debounceUntil) {
    return;
  }

  // Rearm only after a stable release (HIGH) after lockout.
  if (waitingForRelease && !isPressed) {
    buttonPressed     = false;
    waitingForRelease = false;
  }

  // Non-blocking LED update — never adds latency to the button path.
  if (timerRunning) {
    // Solid on while running.
    if (!ledState) {
      digitalWrite(LED_PIN, HIGH);
      ledState = true;
    }
  } else {
    // Blink at 2 Hz while idle/ready.
    if (now - lastBlinkToggle >= BLINK_INTERVAL_MS) {
      lastBlinkToggle = now;
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    }
  }
}
