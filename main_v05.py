from time import sleep
import datetime
import os
from tracadelas_deteccao import funcao_deteccao_lycra_tracadelas
from detecao_agulha_v02 import funcao_detecao_agulhas
import RPi.GPIO as GPIO
from scipy import misc
from pymongo import MongoClient
import base64
from pijuice import PiJuice
from pyueye import ueye
import ctypes
import sys, getopt
from control_usb import powerOffUSBs, powerOnUSBs
import logging
import json

class Smartex:
    
    # MONGO_PORT = 27017
    OP_OK = 0
    OP_ERR = -1
    # CAMERA_RETRYS = 10
    pijuice = PiJuice(1,0x14)
    
    def __init__(self, configsFile = 'image-analyser/configs.json'):
        self.operationConfigs = json.loads(open(configsFile).read())
        
        while self.initCamera() != self.OP_OK and self.operationConfigs['CAMERA_RETRYS'] > 0:
            logging.warning('Error in initCamera()')
            self.pijuice.status.SetLedBlink('D2', 2, [255,0,0], 50, [255, 0, 0], 50)
            sleep(1)
            self.operationConfigs['CAMERA_RETRYS'] -= 1
            
        self.DEVICE_ID = id
        logging.basicConfig(filename='smartex_main.log', level=logging.DEBUG,\
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    def initCamera(self):
        try:
            self.hcam = ueye.HIDS(0)
            self.pccmem = ueye.c_mem_p()
            self.memID = ueye.c_int()
            self.hWnd = ctypes.c_voidp()
            ueye.is_InitCamera(self.hcam, self.hWnd)
            ueye.is_SetDisplayMode(self.hcam, 0)
            self.sensorinfo = ueye.SENSORINFO()
            ueye.is_GetSensorInfo(self.hcam, self.sensorinfo)
            
            return self.OP_OK
        except:
            return self.OP_ERR
            
    def connectMongoDB(self):
        try:
            con = MongoClient(self.operationConfigs['MONGO_HOST'], self.operationConfigs['MONGO_PORT'])
            self.db = con[self.operationConfigs['DBNAME']]
            self.pijuice.status.SetLedBlink('D2', 2, [0,0,255], 50, [0, 0, 255], 50)
            sleep(.01)
        except:
            logging.warning('Error in connectMongoDB!\n')
            self.pijuice.status.SetLedBlink('D2', 2, [255,0,0], 50, [255, 0, 0], 50)
            sleep(.01)
            pass
    
    def saveImage(self):
        try:
            time1 = datetime.datetime.now()
            ueye.is_AllocImageMem(self.hcam, self.sensorinfo.nMaxWidth, self.sensorinfo.nMaxHeight,24, self.pccmem, self.memID)
            ueye.is_SetImageMem(self.hcam, self.pccmem, self.memID)
            ueye.is_SetDisplayPos(self.hcam, 100, 100)

            self.nret = ueye.is_FreezeVideo(self.hcam, ueye.IS_WAIT)

            self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
            self.imageName = 'imagem_%s.jpg' % self.imageTimeStamp
            self.imagePath = self.operationConfigs['savingDirectory'] + self.imageName

            self.FileParams = ueye.IMAGE_FILE_PARAMS()
            self.FileParams.pwchFileName = self.imagePath 
            self.FileParams.nFileType = ueye.IS_IMG_BMP
            self.FileParams.ppcImageMem = None
            self.FileParams.pnImageID = None

            self.nret = ueye.is_ImageFile(self.hcam, ueye.IS_IMAGE_FILE_CMD_SAVE, self.FileParams, ueye.sizeof(self.FileParams))
            ueye.is_FreeImageMem(self.hcam, self.pccmem, self.memID)
            sleep(.01)
            ueye.is_ExitCamera(self.hcam)
            
            time2 = datetime.datetime.now()
            elapsed_time = time2 - time1
            logging.info('Saved: {}! Elasped time (ms): {}'.format(self.imageName, elapsed_time.microseconds/1000))
            self.pijuice.status.SetLedBlink('D2', 2, [0,255,0], 50, [0, 255, 0], 50)
            sleep(.01)
        except:
            logging.warning('NOT SAVED: {}!\n'.format(self.imageName))
            self.pijuice.status.SetLedBlink('D2', 2, [255,0,0], 50, [255, 0, 0], 50)
            sleep(.01)
            pass
        
    def deffectDetection(self):
                  
        i = 1
        while True:

            self.UPSpowerInput = self.pijuice.status.GetStatus()['data']['powerInput']
            
            if i == 1:
                self.USBpowerOutput = 'ON'

            if self.UPSpowerInput == 'NOT_PRESENT' and self.USBpowerOutput == 'ON':
                logging.warning('UPS not being charged - shutting down camera.\n')
                powerOffUSBs()
                self.USBpowerOutput = 'OFF'
                sleep(1)
                continue

            elif self.UPSpowerInput == 'NOT_PRESENT' and self.USBpowerOutput == 'OFF':
                logging.warning('UPS not being charged - trying again.\n')
                sleep(1)
                continue

            elif self.UPSpowerInput == 'PRESENT' and self.USBpowerOutput == 'OFF':
                logging.info('UPS just started being charged - booting camera.\n')
                powerOnUSBs()
                self.USBpowerOutput = 'ON'
                sleep(5)

            if i != 1:
                self.initCamera()

            logging.info('Taking image # ' + str(i))
            self.saveImage()


            with open(self.imagePath, "rb") as imageFile:
                self.b64Img = base64.b64encode(imageFile.read())

            self.fabric = {
                '_id': i,
                'defect': 'None',
                'date': self.imageTimeStamp,
                'imageUrl': 'imgs/' + self.imageName,
                'imageBIN': self.b64Img,
                'deviceID': self.operationConfigs['DEVICE_ID'],
            }

            if self.operationConfigs['deffectDetectionMode']:
                lycraDeffectDetected = funcao_deteccao_lycra_tracadelas(self.imagePath)
                agulhaDeffectDetected = funcao_detecao_agulhas(self.imagePath)

                if agulhaDeffectDetected:
                    self.fabric['defect'] = 'Agulha'
                    logging.info("Defeito agulha!")

                if lycraDeffectDetected[0]:
                    self.fabric['defect'] = lycraDeffectDetected[1]
                    logging.info("Defeito lycra!")

                if self.operationConfigs['stopMachineMode'] and (lycraDeffectDetected[0] or agulhaDeffectDetected):
                    
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(self.operationConfigs['outputPort'], GPIO.LOW)
                    sleep(1)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            #por try except
                    
            try:
                time1 = datetime.datetime.now()
                self.db['fabrics'].save(self.fabric)
                time2 = datetime.datetime.now()
                elapsed_time = time2 - time1
                logging.info ("Sent to DB!! Elapsed time (ms): {}\n".format(elapsed_time.microseconds/1000))
                self.pijuice.status.SetLedBlink('D2', 2, [0,0,255], 50, [0, 0, 255], 50)
                sleep(.01)
            except:
                logging.warning('Fabric DB instance not saved in MongoDB\n')
                self.pijuice.status.SetLedBlink('D2', 2, [255,0,0], 50, [255, 0, 0], 50)
                sleep(.01)
                pass
            
            sleep(1)
            i += 1

if __name__ == "__main__":
    
    s = Smartex()
    
    s.connectMongoDB()

    s.deffectDetection()