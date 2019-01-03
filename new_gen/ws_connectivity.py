import logging
from time import sleep

import requests
from socketIO_client_nexus import SocketIO, LoggingNamespace, BaseNamespace, ConnectionError
import datetime
import json
import boto
import pigpio

try:
    import thread
except ImportError:
    import _thread as thread
from threading import Thread


class WebServer:
    OP_OK = 0
    OP_ERR = -1

    def __init__(self, operation_configs):
        self.operationConfigs = operation_configs
        self.authenticated = False
        pass

    def authWS(self):
        try:
            time1 = datetime.datetime.now()
            logging.info("Authenticating in WS!")
            self.client = requests.session()

            # Retrieve the CSRF token first
            self.client.get(self.operationConfigs['WS_ENDPOINT'] + 'login')  # sets cookie

            if 'csrftoken' in self.client.cookies:
                self.session_id = self.client.cookies['csrftoken']
            elif '_csrf' in self.client.cookies:
                self.session_id = self.client.cookies['_csrf']
            elif 'sessionId' in self.client.cookies:
                self.session_id = self.client.cookies['sessionId']
            else:
                self.session_id = self.client.cookies['csrf']

            login_data = dict(username='test', password='test1234', csrfmiddlewaretoken=self.session_id, next='/')
            r = self.client.post(self.operationConfigs['AUTH_ENDPOINT'], data=login_data,
                                 headers=dict(Referer=self.operationConfigs['WS_ENDPOINT'] + 'login'))

            time2 = datetime.datetime.now()
            elapsed_time = time2 - time1
            logging.info("Authenticated in WS!! Elapsed time (s): {}\n".format(elapsed_time.total_seconds()))
            self.authenticated = True
            return self.OP_OK
        except Exception as ex:
            logging.exception("Error authenticating with WS!")
            return self.OP_ERR

    def getLastID(self):
        if not self.authenticated:
            logging.warn("You need to authenticate before getting an ID!")
            return 1
        try:
            r = self.client.get(self.operationConfigs['WS_ENDPOINT'] + 'api/fabric/lastID')  # sets cookie
            data = r.json()
            return data['data']['id']
        except:
            return 1


class AWS:
    OP_OK = 0
    OP_ERR = -1

    def __init__(self, operation_configs):
        self.operationConfigs = operation_configs
        pass

    def connectAWSS3(self):
        logging.info("Connecting AWS3...")
        try:
            con = boto.connect_s3(self.operationConfigs['AWS_ACCESS_KEY'], self.operationConfigs['AWS_SECRET_KEY'],
                                  host=self.operationConfigs['REGION_HOST'])
            self.bucket = con.get_bucket(self.operationConfigs['AWS_BUCKET'])
            return self.OP_OK
        except Exception as ex:
            logging.exception('Error connecting to AWS S3!\n')
            return self.OP_ERR


class WebSockets:
    OP_OK = 0
    OP_ERR = -1

    def __init__(self, operation_configs, session_id, configsFile='configs.json'):
        self.operationConfigs = operation_configs
        self.configsFile = configsFile
        self.session_id = session_id
        pass

    def connectWSock(self):
        try:
            socketIO = SocketIO(self.operationConfigs['SOCK_ENDPOINT'], 3000, cookies={'sessionId': self.session_id},
                                wait_for_connection=False)
            socketIO.on('connect', self.on_connect)
            socketIO.on('/devices/updated', self.on_updated)
            socketIO.on('disconnect', self.on_disconnect)
            socketIO.on('reconnect', self.on_reconnect)
            socketIO.wait()
        except ConnectionError:
            logging.warn('Error connecting WebSockets\n')

    def startWSockService(self):
        self.wsockthread = Thread(target=self.connectWSock)
        self.wsockthread.setDaemon(True)
        self.wsockthread.start()

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
                if configs.get('frontledgpio', -1) >= 0:
                    self.operationConfigs['frontledgpio'] = configs['frontledgpio']
                if configs.get('backledgpio', -1) >= 0:
                    self.operationConfigs['backledgpio'] = configs['backledgpio']

                if configs.get('frontledint', -1) >= 0:
                    self.operationConfigs['frontledint'] = configs['frontledint']
                    self.changeLEDInt(self.operationConfigs['frontledgpio'], self.operationConfigs['frontledint'])

                if configs.get('backledint', -1) >= 0:
                    self.operationConfigs['backledint'] = configs['backledint']
                    self.changeLEDInt(self.operationConfigs['backledgpio'], self.operationConfigs['backledint'])

                self.updateJsonFile()
                logging.info("Updated operationConfigs!")
        except ValueError:
            logging.warning("Error parsing configs: " + ValueError)

    def join(self):
        try:
            self.wsockthread.join()
        except:
            pass

    def on_connect(self):
        print('[WebSocket Connected]')

    def on_reconnect(self):
        print('[WebSocket Reconnected]')

    def on_disconnect(self):
        print('[WebSocket Disconnected]')

    def updateJsonFile(self):
        jsonFile = open(self.configsFile, "w+")
        jsonFile.write(json.dumps(self.operationConfigs))
        jsonFile.close()

    @staticmethod
    def changeLEDInt(LED_PIN, realBrightness):
        sleep(0.5)
        try:
            logging.info("Going to set PWM_dutycycle to " + str(realBrightness) + " in GPIO port " + str(LED_PIN))
            pi = pigpio.pi()
            pi.set_PWM_dutycycle(LED_PIN, realBrightness)
        except Exception as ex:
            logging.exception("Error changing LED brightness!")
