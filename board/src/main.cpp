#include <Arduino.h>

#define SOLENOID_PIN 4
#define PULSE_DURATION_MS 100

void setup() {
  Serial.begin(115200);
  pinMode(SOLENOID_PIN, OUTPUT);
  digitalWrite(SOLENOID_PIN, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '1') {
      digitalWrite(SOLENOID_PIN, HIGH);
      delay(PULSE_DURATION_MS);
      digitalWrite(SOLENOID_PIN, LOW);
      delay(PULSE_DURATION_MS);
      digitalWrite(SOLENOID_PIN, HIGH);
      delay(PULSE_DURATION_MS);
      digitalWrite(SOLENOID_PIN, LOW);
      Serial.println("TUK");
    }
  }
}
