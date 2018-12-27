###### CONFIGURE THIS ######

# The Pins. Use Broadcom numbers.
LED_PIN   = 27

# Number of color changes per step (more is faster, less is slower).
# You also can use 0.X floats.
STEPS     = 1

###### END ######




import os
import sys
import termios
import tty
import pigpio
import time
from thread import start_new_thread

bright = 255
l = 255.0


brightChanged = False
abort = False
state = True

pi = pigpio.pi()
pi.set_mode(LED_PIN, pigpio.OUTPUT)

def updateColor(color, step):
	color += step
	
	if color > 255:
		return 255
	if color < 0:
		return 0
		
	return color


def setLights(pin, brightness):
	realBrightness = int(int(brightness) * (float(bright) / 255.0))
	pi.set_PWM_dutycycle(pin, realBrightness)


def getCh():
	fd = sys.stdin.fileno()
	old_settings = termios.tcgetattr(fd)
	
	try:
		tty.setraw(fd)
		ch = sys.stdin.read(1)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
		
	return ch


def checkKey():
	global bright
	global brightChanged
	global state
	global abort
	
	while True:
		c = getCh()
		
		if c == '+' and bright < 255 and not brightChanged:
			brightChanged = True
			time.sleep(0.01)
			brightChanged = False
			
			bright = bright + 1
			print ("Current brightness: %d" % bright)
			
		if c == '-' and bright > 0 and not brightChanged:
			brightChanged = True
			time.sleep(0.01)
			brightChanged = False
			
			bright = bright - 1
			print ("Current brightness: %d" % bright)
			
		if c == 'p' and state:
			state = False
			print ("Pausing...")
			
			time.sleep(0.1)
			
			setLights(LED_PIN, 0)
			
		if c == 'r' and not state:
			state = True
			print ("Resuming...")
			
		if c == 'c' and not abort:
			abort = True
			break

start_new_thread(checkKey, ())


print ("+ / - = Increase / Decrease brightness")
print ("p / r = Pause / Resume")
print ("c = Abort Program")


setLights(LED_PIN, l)


while abort == False:
	if state and not brightChanged:
		
		if l > 0:
		    l = updateColor(l, -STEPS)
		    setLights(LED_PIN, l)
		
		elif l < 255:
		    l = updateColor(l, STEPS)
		    setLights(LED_PIN, l)
print ("Aborting...")

setLights(LED_PIN, 0)

time.sleep(0.5)

pi.stop()