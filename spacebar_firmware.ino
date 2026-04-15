#include <Keyboard.h>

// Teyleten Robot Type-C Pro Micro (ATmega32U4, 5V/16MHz)
// Wiring:
// - Momentary normally-open switch leg 1 -> pin 2
// - Momentary normally-open switch leg 2 -> GND
// INPUT_PULLUP is enabled, so no external resistor is needed.

const uint8_t BUTTON_PIN = 2;
const unsigned long DEBOUNCE_MS = 20;

bool buttonPressed = false;
bool waitingForRelease = false;
unsigned long debounceUntil = 0;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Keyboard.begin();
}

void loop() {
  const unsigned long now = millis();
  const bool isPressed = (digitalRead(BUTTON_PIN) == LOW);

  // Fast-path press detection: send space immediately on the first LOW edge.
  // Then lock out additional edges for DEBOUNCE_MS.
  if (!waitingForRelease && !buttonPressed && isPressed) {
    Keyboard.press(' ');
    Keyboard.release(' ');

    buttonPressed = true;
    waitingForRelease = true;
    debounceUntil = now + DEBOUNCE_MS;
    return;
  }

  // Keep ignoring bounce while debounce lockout is active.
  if (now < debounceUntil) {
    return;
  }

  // Rearm only after a stable release (HIGH) after lockout.
  if (waitingForRelease && !isPressed) {
    buttonPressed = false;
    waitingForRelease = false;
  }
}
