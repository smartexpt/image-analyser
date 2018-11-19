#import ids
#from PIL import Image
from time import sleep
import datetime
import os
from tracadelas_deteccao import funcao_deteccao_lycra_tracadelas
from detecao_agulha_v02 import funcao_detecao_agulhas
import RPi.GPIO as GPIO
from scipy import misc
#import pymongo
from pymongo import MongoClient
import base64
import pijuice
from pyueye import ueye
import ctypes

class Smartex:
    
    MONGO_PORT = 27017
    OP_OK = 0
    OP_ERR = -1
    CAMERA_RETRYS = 10
    
    def __init__(self, DBNAME, MONGO_HOST, id = '7AKy0GDOEb'):
        self.DBNAME = DBNAME
        self.MONGO_HOST = MONGO_HOST
        
        while self.initCamera() != self.OP_OK and self.CAMERA_RETRYS > 0:
            print('Error in initCamera()')
            sleep(1)
            self.CAMERA_RETRYS -= 1
            
        self.DEVICE_ID = id
    
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
            con = MongoClient(self.MONGO_HOST, self.MONGO_PORT)
            self.db = con[self.DBNAME]
        except:
            print('Error in connectMongoDB!\n')
            pass
##        con = MongoClient(self.MONGO_HOST, self.MONGO_PORT)
##        self.db = con[self.DBNAME]
        
    def operationConfigs(self):
        
        self.deffectDetectionMode = str(raw_input('Deffect detection mode: (on/off)')) or 'on'
        if self.deffectDetectionMode == 'on':
            print('Detection mode: ON')

            self.stopMachineMode = str(raw_input('Stop machine mode: (on/off)')) or 'on'
            if self.stopMachineMode == 'on':
                print('Stop mode: ON')
                self.outputPort = int(raw_input('RPi low voltage GPIO port: (27)')) or 27
            elif self.stopMachineMode == 'off':
                print('Stop mode: OFF')
            else:
                print('Input not recognized, not gonna stop.')

        elif self.deffectDetectionMode == 'off':
            print('Detection mode: OFF')
        else:
            print('Input not recognized, not gonna detect.')
            
    def setSavingDirectory(self, directory='teste_tojo/'):
        self.savingDirectory = directory
        
        if not os.path.exists(self.savingDirectory):
            os.makedirs(self.savingDirectory)
            
    def setSavingDirectoryLastImage(self, directory='teste_tojo/'):
        self.savingDirectoryLastImage = directory
        
        if not os.path.exists(self.savingDirectoryLastImage):
            os.makedirs(self.savingDirectoryLastImage)
            
    # def takeImage(self):
    #     #por try except
    #     try:
    #         img, meta = self.cam.next()  # Get image as a Numpy array
    #         self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    #         self.image = img
    #     except:
    #         self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    #         print('Image not taken at {}!\n'.format(self.imageTimeStamp))
    #         self.image = None
    #         pass
        
    #     return self.image
    
    def saveImage(self):
        try:
            ueye.is_AllocImageMem(self.hcam, self.sensorinfo.nMaxWidth, self.sensorinfo.nMaxHeight,24, self.pccmem, self.memID)
            ueye.is_SetImageMem(self.hcam, self.pccmem, self.memID)
            ueye.is_SetDisplayPos(self.hcam, 100, 100)

            self.nret = ueye.is_FreezeVideo(self.hcam, ueye.IS_WAIT)

            self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
            self.imageName = 'imagem_%s.jpg' % self.imageTimeStamp
            self.imagePath = self.savingDirectory + self.imageName

            self.FileParams = ueye.IMAGE_FILE_PARAMS()
            self.FileParams.pwchFileName = self.imagePath 
            self.FileParams.nFileType = ueye.IS_IMG_BMP
            self.FileParams.ppcImageMem = None
            self.FileParams.pnImageID = None

            self.nret = ueye.is_ImageFile(self.hcam, ueye.IS_IMAGE_FILE_CMD_SAVE, self.FileParams, ueye.sizeof(self.FileParams))
            # print(nret)
            ueye.is_FreeImageMem(self.hcam, self.pccmem, self.memID)
            sleep(.1)
            ueye.is_ExitCamera(self.hcam)

        except:
            print('Image not saved at {}!\n'.format(self.imageTimeStamp))
            pass
        
    # def saveImageLastImage(self, image):
    #     self.imagePathLastImage = self.savingDirectoryLastImage + 'last_image.jpg'
    #     try:
    #         misc.imsave(self.imagePathLastImage, image)
    #     except:
    #         print('Last image not saved at {}!\n'.format(self.imageTimeStamp))
    #         pass
    
    def deffectDetection(self):
                  
        i = 1
        while True:

            print('Taking image # ' + str(i))
            if i!=1:
                self.initCamera()
            self.saveImage()


            with open(self.imagePath, "rb") as imageFile:
                self.b64Img = base64.b64encode(imageFile.read())

            self.fabric = {
                '_id': i,
                'defect': 'None',
                'date': self.imageTimeStamp,
                'imageUrl': 'imgs/' + self.imageName,
                'imageBIN': self.b64Img,
                'deviceID': self.DEVICE_ID,
            }

            if self.deffectDetectionMode == 'on':
                lycraDeffectDetected = funcao_deteccao_lycra_tracadelas(self.imagePath)
                agulhaDeffectDetected = funcao_detecao_agulhas(self.imagePath)

                if agulhaDeffectDetected:
                    self.fabric['defect'] = 'Agulha'
                    print("Defeito agulha!")

                if lycraDeffectDetected[0]:
                    self.fabric['defect'] = lycraDeffectDetected[1]
                    print("Defeito lycra!")

                if self.stopMachineMode == 'on' and (lycraDeffectDetected[0] or agulhaDeffectDetected):
                    
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.outputPort, GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(self.outputPort, GPIO.LOW)
                    sleep(1)
                    GPIO.setup(self.outputPort, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            #por try except
                    
            try:
                self.db['fabrics'].save(self.fabric)
                print ("Sent to DB!!")
            except:
                print('Fabric DB instance not saved in MongoDB at {}!\n'.format(self.imageTimeStamp))
                pass
            
            sleep(1)
            i += 1

if __name__ == "__main__":
    
    DBNAME = 'boilerplate-test'
    MONGO_HOST = '192.168.1.111'
    
    s = Smartex(DBNAME, MONGO_HOST)
    
    s.connectMongoDB()
    
    s.setSavingDirectory()
##    print(s.savingDirectory)
    
    # s.setSavingDirectoryLastImage()
##    print(s.savingDirectoryLastImage)
    
    s.operationConfigs()
    
    s.deffectDetection()