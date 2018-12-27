from time import sleep
import datetime
import os
from tracadelas_deteccao import funcao_deteccao_lycra_tracadelas
from detecao_agulha_v02 import funcao_detecao_agulhas
import RPi.GPIO as GPIO
from scipy import misc, ndimage
from pijuice import PiJuice
from pyueye import ueye
import ctypes
import sys, getopt
from control_usb import powerOffUSBs, powerOnUSBs
import logging
import json
import boto
from boto.s3.key import Key
import uuid
import requests
from PIL import Image
from socketIO_client_nexus import SocketIO, LoggingNamespace, BaseNamespace, ConnectionError
import sys
import base64
import numpy as np
from io import BytesIO

reload(sys)
sys.setdefaultencoding('utf-8')
from random import randint

try:
    import thread
except ImportError:
    import _thread as thread
import time
from threading import Thread


def on_connect():
    print('[Connected]')


def on_reconnect():
    print('[Reconnected]')


def on_disconnect():
    print('[Disconnected]')


def percent_cb(complete, total):
    percent = (complete / total) * 100.0
    sys.stdout.write('%d\r' % percent)
    sys.stdout.flush()


class Smartex:
    OP_OK = 0
    OP_ERR = -1
    # CAMERA_RETRYS = 10
    pijuice = PiJuice(1, 0x14)

    def __init__(self, configsFile='configs.json'):
        print "Starting..."
        self.configsFile = configsFile
        self.operationConfigs = json.loads(open(configsFile).read())
        print "Configurations loaded from " + configsFile
        while self.initCamera() != self.OP_OK and self.operationConfigs['CAMERA_RETRYS'] > 0:
            logging.warning('Error in initCamera()')
            self.pijuice.status.SetLedBlink('D2', 2, [255, 0, 0], 50, [255, 0, 0], 50)
            sleep(1)
            self.pijuice.status.SetLedState('D2', [0, 0, 0])
            self.operationConfigs['CAMERA_RETRYS'] -= 1

        self.DEVICE_ID = id
        print "Setting up logging configs..."
        # logging.getLogger('socketIO-client-nexus').setLevel(logging.DEBUG)
        logging.basicConfig(filename='smartex_main.log', level=logging.INFO, \
                            format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        logging.getLogger().addHandler(logging.StreamHandler())
        print "Smartex module initiated with success!"

    def updateJsonFile(self):
        jsonFile = open(self.configsFile, "w+")
        jsonFile.write(json.dumps(self.operationConfigs))
        jsonFile.close()

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
            print self.sensorinfo
            return self.OP_OK
        except:
            print "\n\nERR\n\n"
            return self.OP_ERR

    def connectAWSS3(self):
        logging.info("Connecting AWS3...")
        try:
            con = boto.connect_s3(self.operationConfigs['AWS_ACCESS_KEY'], self.operationConfigs['AWS_SECRET_KEY'],
                                  host=self.operationConfigs['REGION_HOST'])
            self.bucket = con.get_bucket(self.operationConfigs['AWS_BUCKET'])
            return True
        except:
            logging.warning('Error in connectAWSS3!\n')
            self.blinkLED()
            return False

    def authWS(self):
        try:
            time1 = datetime.datetime.now()
            logging.info("Authenticating in WS!")
            self.client = requests.session()

            # Retrieve the CSRF token first
            self.client.get('http://192.168.0.102:3000/login')  # sets cookie

            if 'csrftoken' in self.client.cookies:
                self.csrftoken = self.client.cookies['csrftoken']
            elif '_csrf' in self.client.cookies:
                self.csrftoken = self.client.cookies['_csrf']
            elif 'sessionId' in self.client.cookies:
                self.csrftoken = self.client.cookies['sessionId']
            else:
                self.csrftoken = self.client.cookies['csrf']

            login_data = dict(username='test', password='test1234', csrfmiddlewaretoken=self.csrftoken, next='/')
            r = self.client.post(self.operationConfigs['AUTH_ENDPOINT'], data=login_data,
                                 headers=dict(Referer='http://192.168.0.102:3000/login'))

            time2 = datetime.datetime.now()
            elapsed_time = time2 - time1
            logging.info("\nAuthentication status code: {}".format(r.status_code))
            # logging.info("Authentication response headers: {}".format(r.headers))
            # logging.info("Authentication response cookies: {}\n".format(r.cookies))
            logging.info("Authenticated in WS!! Elapsed time (s): {}\n".format(elapsed_time.total_seconds()))
            self.blinkLED()
            return True
        except:
            logging.warning('Error authenticating with WS\n')
            self.blinkLED()
            return False
            pass
        pass

    def getLastID(self):
        r = self.client.get('http://192.168.0.102:3000/api/fabric/lastID')  # sets cookie
        data = r.json()
        print(data['data']['id'])
        self.lastID = data['data']['id']
        pass

    def saveImage(self):
        #try:
        time1 = datetime.datetime.now()
        ueye.is_AllocImageMem(self.hcam, self.sensorinfo.nMaxWidth, self.sensorinfo.nMaxHeight, 24, self.pccmem,
                              self.memID)
        ueye.is_SetImageMem(self.hcam, self.pccmem, self.memID)
        ueye.is_SetDisplayPos(self.hcam, 100, 100)

        self.nret = ueye.is_FreezeVideo(self.hcam, ueye.IS_WAIT)
        self.rawImageTimeStamp = datetime.datetime.now()
        self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self.imageName = 'imagem_%s.jpg' % self.imageTimeStamp
        self.imagePath = self.operationConfigs['savingDirectory'] + self.imageName
        #self.imagePath = self.operationConfigs['savingDirectory'] + "tmp.jpg"
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

        #self.image = np.ones((self.sensorinfo.nMaxHeight.value, self.sensorinfo.nMaxWidth.value), dtype=np.uint8)
        #ueye.is_CopyImageMem(self.hcam, self.pccmem, self.memID, self.image.ctypes.data)

        self.image = np.uint8(ndimage.imread(self.imagePath, flatten=True))

        time2 = datetime.datetime.now()
        elapsed_time = time2 - time1
        logging.info('Saved: {}! Elasped time (s): {}'.format(self.imageName, elapsed_time.total_seconds()))
        #except:
        #    logging.warning('NOT SAVED: {}!\n'.format(self.imageName))
        #    self.blinkLED()
        #    pass

    def uploadImages(self):
        #try:
        if self.operationConfigs['storage'] == "ONLINE":
            logging.info("#upload full res: " + self.imagePath)
            fuuid = str(uuid.uuid4())
            k = Key(self.bucket)
            k.key = 'F_' + fuuid + '.png'
            k.set_contents_from_filename(self.imagePath, cb=percent_cb, num_cb=10)
            self.imgUrl = 'https://' + self.operationConfigs['REGION_HOST'] + '/' + self.operationConfigs[
                'AWS_BUCKET'] + '/' + k.key
            k.set_acl('public-read')

            logging.info("#generate 128*128 thumbnail")
            im = Image.open(self.imagePath)
            im.thumbnail((128, 128), Image.ANTIALIAS)
            head, tail = os.path.split(self.imagePath)
            thumb_path = head + "/T_" + tail
            im.save(thumb_path, "PNG")

            logging.info("#upload thumbnail")
            k = Key(self.bucket)
            k.key = "T_" + fuuid + '.png'
            k.set_contents_from_filename(thumb_path, cb=percent_cb, num_cb=10)
            self.thumbUrl = 'https://' + self.operationConfigs['REGION_HOST'] + '/' + self.operationConfigs[
                'AWS_BUCKET'] + '/' + k.key
            k.set_acl('public-read')
        else:
            time1 = datetime.datetime.now()
            fuuid = str(uuid.uuid4())
            name = 'F_' + fuuid + '.png'
            pil_img = Image.fromarray(self.image)
            buff = BytesIO()
            pil_img.save(buff, format="JPEG")
            #b64Img = base64.b64encode(buff.getvalue()).decode("utf-8")

            with open(self.imagePath, "rb") as imageFile:
                b64Img = base64.b64encode(imageFile.read())

            logging.info("Sending image to local storage!")
            img = {
                name: "data:image/png;base64, " + b64Img
            }
            r = requests.post("http://" + self.operationConfigs['STORAGE_ENDPOINT'] + "/" + name, json=img)

            self.imgUrl = 'http://192.168.0.102:3000/fabrics/' + name

            im = Image.open(self.imagePath)
            im.thumbnail((128, 128), Image.ANTIALIAS)

            logging.info("#upload thumbnail")
            name = "T_" + fuuid + '.png'
            buff = BytesIO()
            im.save(buff, format="JPEG")
            b64Img = base64.b64encode(buff.getvalue()).decode("utf-8")

            img = {
                name: "data:image/png;base64, " + b64Img
            }
            r = requests.post("http://" + self.operationConfigs['STORAGE_ENDPOINT'] + "/" + name, json=img)

            self.thumbUrl = 'http://192.168.0.102:3000/fabrics/' + name

            time2 = datetime.datetime.now()
            elapsed_time = time2 - time1
            logging.info("Sent images to local storage!! Elapsed time (s): {}\n".format(elapsed_time.total_seconds()))
        #except:
        #   logging.warn("Error sendig image to local storage!\n")

    def deffectDetection(self):
        i = 1
        while True:
            begin = datetime.datetime.now()
            logging.info('Iteration # ' + str(i))
            self.UPSpowerInput = self.pijuice.status.GetStatus()['data']['powerInput']

            if i == 1:
                self.USBpowerOutput = 'OFF'

            if self.UPSpowerInput == 'NOT_PRESENT' and self.USBpowerOutput == 'ON':
                logging.warning('UPS not being charged - shutting down camera.\n')
                #powerOffUSBs()
                #self.USBpowerOutput = 'OFF'
                #sleep(1)
                #continue

            elif self.UPSpowerInput == 'NOT_PRESENT' and self.USBpowerOutput == 'OFF':
                logging.warning('UPS not being charged - trying again.\n')
                #sleep(1)
                #continue

            elif self.UPSpowerInput == 'PRESENT' and self.USBpowerOutput == 'OFF':
                logging.info('UPS just started being charged - booting camera.\n')
                powerOnUSBs()
                self.USBpowerOutput = 'ON'
                #sleep(2)

            if i != 1:
                self.initCamera()

            logging.info('Taking image!')
            try:
	    	self.saveImage()
            except:
		continue
	    defect = 'None'

            time1 = datetime.datetime.now()
            if self.operationConfigs['deffectDetectionMode']:
                logging.info("Starting detection modules!")
                lycraDeffectDetected = funcao_deteccao_lycra_tracadelas(self.image)
                agulhaDeffectDetected = funcao_detecao_agulhas(self.image)

                if agulhaDeffectDetected:
                    defect = 'Agulha'
                    logging.info("Defeito agulha!")

                if lycraDeffectDetected[0]:
                    defect = lycraDeffectDetected[1]
                    logging.info("Defeito lycra!")

                if self.operationConfigs['stopMachineMode'] and (lycraDeffectDetected[0] or agulhaDeffectDetected):
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(self.operationConfigs['outputPort'], GPIO.LOW)
                    sleep(1)
                    GPIO.setup(self.operationConfigs['outputPort'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

                time2 = datetime.datetime.now()
                elapsed_time = time2 - time1
                logging.info("Detection modules finished! Elapsed time (s): {}\n".format(elapsed_time.total_seconds()))

            logging.info("Uploading image!")
            try:
	    	self.uploadImages()
	    except:
		continue
            self.fabric = {
                '_id': self.lastID+i,
                'defect': defect,
                'date': self.rawImageTimeStamp,
                'imageUrl': self.imgUrl,
                'thumbUrl': self.thumbUrl,
                'deviceID': self.operationConfigs['DEVICE_ID'],
            }
            # por try except
            try:
                time1 = datetime.datetime.now()
                logging.info("Sending to WS!")
                r = self.client.post(self.operationConfigs['FABRIC_ENDPOINT'], data=self.fabric)
                time2 = datetime.datetime.now()
                elapsed_time = time2 - time1
                logging.info("Fabric post status code: {}".format(r.status_code))
                logging.info("Sent to WS!! Elapsed time (s): {}\n".format(elapsed_time.total_seconds()))
                #self.blinkLED()
            except:
                logging.warning('Error communicating with WS\n')
                self.blinkLED()
                pass

            elapsed = datetime.datetime.now() - begin
            sleep_time = max(self.operationConfigs['interval'] - elapsed.total_seconds(), 0)
            logging.info("\nTotal elapsed time (s): {}".format(elapsed.total_seconds()))
            logging.info("Will sleep for (s): {}".format(sleep_time))
            print(self.operationConfigs['interval'], elapsed.total_seconds())
            sleep(sleep_time)
            i += 1

    def blinkLED(self):
        pass
        self.pijuice.status.SetLedBlink('D2', 2, [255, 0, 0], 50, [255, 0, 0], 50)
        sleep(.1)
        self.pijuice.status.SetLedState('D2', [0, 0, 0])

    def connectWSock(self):
        try:
            socketIO = SocketIO(self.operationConfigs['SOCK_ENDPOINT'], 3000, cookies={'sessionId': s.csrftoken},
                                wait_for_connection=False)
            socketIO.on('connect', on_connect)
            socketIO.on('/devices/updated', self.on_updated)
            socketIO.on('disconnect', on_disconnect)
            socketIO.on('reconnect', on_reconnect)
            socketIO.wait()
        except ConnectionError:
            logging.warning('Error connecting WebSockets\n')

    def on_updated(self, *args):
        try:
            configs = args[0]['data']
            print configs
            print '\n'
            if configs['code'] == self.operationConfigs['DEVICE_ID']:
                if configs.get('stop', -1) >= 0:
                    self.operationConfigs['stopMachineMode'] = (configs['stop'] == 1)
                if configs.get('detection', -1) >= 0:
                    self.operationConfigs['deffectDetectionMode'] = (configs['detection'] == 1)
                if configs.get('gpio', -1) >= 0:
                    self.operationConfigs['outputPort'] = configs['gpio']
                if configs.get('interval', -1) >= 0:
                    self.operationConfigs['interval'] = configs['interval']
                if configs.get('storage', -1) >= 0:
                    self.operationConfigs['storage'] = configs['storage']

                self.updateJsonFile()
                print self.operationConfigs
        except ValueError:
            logging.warning("Error parsing configs: " + ValueError)


if __name__ == "__main__":
    s = Smartex()
    while not s.authWS():
        logging.warning("Reconnecting WS!")

    #while not s.connectAWSS3():
    #    logging.warning("Reconnecting AWS!")

    try:
        s.getLastID()
    except:
        s.lastID = 0

    t1 = Thread(target=s.connectWSock)
    t1.setDaemon(True)
    t1.start()
    s.deffectDetection()
    t1.join()

