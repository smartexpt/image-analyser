from time import *
import datetime
import calendar
import sys, getopt
from pijuice import PiJuice

orig_stdout = sys.stdout
f = open('log_sem_camera.txt', 'w')
sys.stdout = f

pijuice = PiJuice(1,0x14)

lowBatteryVal = 12
lowBattery = False

headerRow = '{}\t{}\t{}'.format('Datetime', 'Charge level (%)', 'Current (mA)')
print(headerRow)

sleep(1)

while not lowBattery:
    charge = pijuice.status.GetChargeLevel()['data']
    ibat = pijuice.status.GetBatteryCurrent()['data']
    currentTime = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    
    dataVal = '{}\t{}\t{}'.format(currentTime, charge, ibat)
    
    if charge >= lowBatteryVal:
        print(dataVal)
        
    else:
        lowBattery = True
        print(dataVal)
        print('LOW BAT, exit')
        break
    
    sleep(2)
    

