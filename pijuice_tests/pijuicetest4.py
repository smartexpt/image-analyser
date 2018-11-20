from time import *
import datetime
import calendar
import sys, getopt
from pijuice import PiJuice

pijuice = PiJuice(1,0x14)

sleep(1)

while True:
    status = pijuice.status.GetStatus()['data']['powerInput']
    print(status)
    
    sleep(2)
    

