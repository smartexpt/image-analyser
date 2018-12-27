import pigpio
import time

LED_PIN_frente   = 27
realBrightness_frente  = 128
LED_PIN_tras   = 17
realBrightness_tras  = 128

pi = pigpio.pi()

pi.set_PWM_dutycycle(LED_PIN_frente, realBrightness_frente)
pi.set_PWM_dutycycle(LED_PIN_tras, realBrightness_tras)