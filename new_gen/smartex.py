from time import sleep
import datetime
from tracadelas_deteccao import funcao_deteccao_lycra_tracadelas
from detecao_agulha_v02 import funcao_detecao_agulhas
import RPi.GPIO as GPIO
from pijuice import PiJuice
from pyueye import ueye
import numpy as np
from scipy import misc, ndimage
import ctypes
from control_usb import powerOffUSBs, powerOnUSBs
import logging
import json
import sys

from workers import FabricWorker
from ws_connectivity import WebSockets, AWS, WebServer

reload(sys)
sys.setdefaultencoding('utf-8')


class Smartex:
    OP_OK = 0
    OP_ERR = -1
    pijuice = PiJuice(1, 0x14)

    def __init__(self, configsFile='configs.json'):
        print "Starting..."
        self.configsFile = configsFile
        self.operationConfigs = json.loads(open(configsFile).read())
        print "Configurations loaded from " + configsFile

        logging.basicConfig(filename='smartex_main.log', level=logging.INFO, \
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        logging.getLogger().addHandler(logging.StreamHandler())

        while self.initCamera() != self.OP_OK and self.operationConfigs['CAMERA_RETRYS'] > 0:
            logging.warning('Error in initCamera()')
            self.pijuice.status.SetLedBlink('D2', 2, [255, 0, 0], 50, [255, 0, 0], 50)
            sleep(1)
            self.pijuice.status.SetLedState('D2', [0, 0, 0])
            self.operationConfigs['CAMERA_RETRYS'] -= 1

        self.webServer = WebServer(self.operationConfigs)
        self.aws = AWS(self.operationConfigs)

        self.authEverything()
        self.fabricWorker = FabricWorker(100, self.aws.bucket, self.webServer.client, self.operationConfigs)

        if self.authenticated:
            self.webSockets = WebSockets(self.operationConfigs, self.webServer.session_id)
            self.webSockets.startWSockService()
            self.deffectDetection()
            self.webSockets.join()
            self.fabricWorker.join()
        else:
            logging.warning("You need to authenticate first!")

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
        except Exception as ex:
            logging.exception("Error during camera initialization!")
            return self.OP_ERR

    def updateJsonFile(self):
        jsonFile = open(self.configsFile, "w+")
        jsonFile.write(json.dumps(self.operationConfigs))
        jsonFile.close()

    def saveImage(self):
        ueye.is_AllocImageMem(self.hcam, self.sensorinfo.nMaxWidth, self.sensorinfo.nMaxHeight, 24, self.pccmem,
                              self.memID)
        ueye.is_SetImageMem(self.hcam, self.pccmem, self.memID)
        ueye.is_SetDisplayPos(self.hcam, 100, 100)

        self.nret = ueye.is_FreezeVideo(self.hcam, ueye.IS_WAIT)
        self.rawImageTimeStamp = datetime.datetime.now()
        self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self.imageName = 'imagem_%s.jpg' % self.imageTimeStamp
        self.imagePath = self.operationConfigs['savingDirectory'] + self.imageName
        # self.imagePath = self.operationConfigs['savingDirectory'] + "tmp.jpg"
        self.FileParams = ueye.IMAGE_FILE_PARAMS()
        self.FileParams.pwchFileName = self.imagePath
        self.FileParams.nFileType = ueye.IS_IMG_BMP
        self.FileParams.ppcImageMem = None
        self.FileParams.pnImageID = None

        self.nret = ueye.is_ImageFile(self.hcam, ueye.IS_IMAGE_FILE_CMD_SAVE, self.FileParams,
                                      ueye.sizeof(self.FileParams))

        ueye.is_FreeImageMem(self.hcam, self.pccmem, self.memID)
        sleep(.01)
        ueye.is_ExitCamera(self.hcam)
        self.image = np.uint8(ndimage.imread(self.imagePath, flatten=True))

    def setLEDParams(self, i, j):
        i = (i % 26)
        j = (j % 26)
        valFront = min((i * 10), 255)
        valBack = min((j * 10), 255)
        self.operationConfigs['frontledint'] = valFront
        WebSockets.changeLEDInt(self.operationConfigs['frontledgpio'], self.operationConfigs['frontledint'])
        self.operationConfigs['backledint'] = valBack
        WebSockets.changeLEDInt(self.operationConfigs['backledgpio'], self.operationConfigs['backledint'])

    def deffectDetection(self):
        i = 1
        j = 1
        while True:
            begin = datetime.datetime.now()
            logging.info('Beginning iteration # ' + str(i))
            self.UPSpowerInput = self.pijuice.status.GetStatus()['data']['powerInput']

            if i == 1:
                self.USBpowerOutput = 'OFF'

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
                sleep(1)

            now = datetime.datetime.now()
            elapsed = now - begin

            logging.info("USB ports are up - elapsed time (s): {}".format(elapsed.total_seconds()))

            self.setLEDParams(i-1, j-1)

            if i != 1:
                self.initCamera()

            now_ant = now
            now = datetime.datetime.now()
            elapsed = now - now_ant

            logging.info("Camera is ready - elapsed time (s): {}".format(elapsed.total_seconds()))

            try:
                logging.info('Taking image!')
                self.saveImage()
                now_ant = now
                now = datetime.datetime.now()
                elapsed = now - now_ant
                logging.info("Image taken and saved - elapsed time (s): {}".format(elapsed.total_seconds()))
            except:
                logging.warn("Error taking/saving image! Continuing to next iteration..")
                continue

            defect = 'None'

            if self.operationConfigs['deffectDetectionMode']:
                logging.info("Analyzing images for defect..")
                lycraDeffectDetected = funcao_deteccao_lycra_tracadelas(self.image)
                agulhaDeffectDetected = funcao_detecao_agulhas(self.image)

                if agulhaDeffectDetected:
                    defect = 'Agulha'
                    logging.info("Defeito agulha detectado!")

                if lycraDeffectDetected[0]:
                    defect = lycraDeffectDetected[1]
                    logging.info("Defeito lycra detectado!")

                if self.operationConfigs['stopMachineMode'] and (lycraDeffectDetected[0] or agulhaDeffectDetected):
                    logging.info("Stoping the machine!")
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(self.operationConfigs['outputPort'], GPIO.LOW)
                    sleep(1)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

                now_ant = now
                now = datetime.datetime.now()
                elapsed = now - now_ant
                logging.info("Detection modules finished -elapsed time (s): {}\n".format(elapsed.total_seconds()))

            fabric = {
                '_id': self.lastID + i,
                'defect': defect,
                'date': self.rawImageTimeStamp,
                'imageUrl': "",
                'thumbUrl': "",
                'deviceID': self.operationConfigs['DEVICE_ID'],
                'LEDBack':  self.operationConfigs['backledint'],
                'LEDFront':  self.operationConfigs['frontledint']
            }

            obj = {
                'path': self.imagePath,
                'fabric': fabric
            }
            self.fabricWorker.add_work(obj)

            elapsed = datetime.datetime.now() - begin
            sleep_time = max(self.operationConfigs['interval'] - elapsed.total_seconds(), 0)

            logging.info('Iteration # ' + str(i) + " finished!")
            logging.info("\nTotal elapsed time (s): {}".format(elapsed.total_seconds()))
            logging.info("Will sleep for (s): {}".format(sleep_time))

            sleep(sleep_time)
            i += 1
            if i % 26 == 0:
                j += 1

    def authEverything(self):
        while self.webServer.authWS() != self.OP_OK:
            logging.warning("Reconnecting WebServer!")
        self.lastID = self.webServer.getLastID()

        if self.operationConfigs['storage'] == "ONLINE":
            while self.aws.connectAWSS3() != self.OP_OK:
                logging.warning("Reconnecting AWS!")
        self.authenticated = True


    def blinkLED(self):
        pass
        self.pijuice.status.SetLedBlink('D2', 2, [255, 0, 0], 50, [255, 0, 0], 50)
        sleep(.1)
        self.pijuice.status.SetLedState('D2', [0, 0, 0])

if __name__ == "__main__":
    s = Smartex()