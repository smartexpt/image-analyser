from time import sleep
import datetime
from scipy import misc, ndimage
import ctypes
import logging
import sys
import os
import time
import threading
import json
from ImageConvert import *
import ArducamSDK

global cfg, handle, Width, Heigth, color_mode, running, save_flag
running = True
save_flag = True
cfg = {}
handle = {}

class Camera:
    OP_OK = 0
    OP_ERR = -1

    def __init__(self, operation_configs, config_file_name='/home/smartex/image-analyser/new_gen/ar0134/AR0134_960p_Mono.json'):
        self.operationConfigs = operation_configs
        self.config_file_name = config_file_name

        if not os.path.exists(config_file_name):
            print("Config file does not exist.")

        while self.initCamera() != self.OP_OK and self.operationConfigs['CAMERA_RETRYS'] > 0:
            logging.warning('Error in initCamera()')
            self.operationConfigs['CAMERA_RETRYS'] -= 1

    def join(self):
        self.ct.join()
        self.rt.join()

    def initCamera(self):
        try:
            if self.camera_initFromFile(self.config_file_name):
                ArducamSDK.Py_ArduCam_setMode(handle, ArducamSDK.CONTINUOUS_MODE)
                cam = Camera({})
                self.ct = threading.Thread(target=cam.backgroundCapture)
                self.rt = threading.Thread(target=cam.saveImage)
                self.ct.start()
                self.rt.start()


            return self.OP_OK
        except Exception as ex:
            logging.exception("Error during camera initialization!")
            return self.OP_ERR

    def capture_thread(self):
        global handle, running

        rtn_val = ArducamSDK.Py_ArduCam_beginCaptureImage(handle)
        if rtn_val != 0:
            print("Error beginning capture, rtn_val = ", rtn_val)
        else:
            logging.info("Capture began, rtn_val = ", rtn_val)


        while running:
            rtn_val = ArducamSDK.Py_ArduCam_captureImage(handle)
            if rtn_val > 255:
                #print("Error capture image, rtn_val = ", rtn_val)
                if rtn_val == ArducamSDK.USB_CAMERA_USB_TASK_ERROR:
                    print("ardu cam USB_CAMERA_USB_TASK_ERROR!!")
            time.sleep(0.01)

    def process_thread(self):
        global handle, running, Width, Height, save_flag, cfg, color_mode
        global COLOR_BayerGB2BGR, COLOR_BayerRG2BGR, COLOR_BayerGR2BGR, COLOR_BayerBG2BGR

        while running:
            if ArducamSDK.Py_ArduCam_availableImage(handle) > 0:
                self.rawImageTimeStamp = datetime.datetime.now()
                self.imageTimeStamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
                self.imageName = 'imagem_%s.jpg' % self.imageTimeStamp
                self.imagePath = "images/" + self.imageName
                rtn_val, data, rtn_cfg = ArducamSDK.Py_ArduCam_readImage(handle)
                datasize = rtn_cfg['u32Size']
                if rtn_val != 0:
                    print("ardu cam read data fail!!")

                if datasize == 0:
                    print("ardu cam read data size = 0!!")

                image = convert_image(data, rtn_cfg, color_mode)
                if save_flag:
                    cv2.imwrite(self.imagePath, image)
                    self.image = np.uint8(ndimage.imread(self.imagePath, flatten=True))

                    self.image = self.crop_end(self.image, 0, 150)
                    save_flag = False
                ArducamSDK.Py_ArduCam_del(handle)

            else:
                time.sleep(0.01)

    def saveImage(self):
        global save_flag
        save_flag = True
        total_wait = 1
        while save_flag and total_wait >= 0:
            sleep(0.01)
            total_wait -= 0.01

        if total_wait > 0:
            return True

        return False

    def crop_end(self, img, cropx, cropy):
        y, x = img.shape
        endx = x - cropx
        endy = y - cropy
        return img[0:endy, 0:endx]

    def configBoard(self, fileNodes):
        global handle
        for i in range(0, len(fileNodes)):
            fileNode = fileNodes[i]
            buffs = []
            command = fileNode[0]
            value = fileNode[1]
            index = fileNode[2]
            buffsize = fileNode[3]
            for j in range(0, len(fileNode[4])):
                buffs.append(int(fileNode[4][j], 16))
            ArducamSDK.Py_ArduCam_setboardConfig(handle, int(command, 16), int(value, 16), int(index, 16),
                                                 int(buffsize, 16), buffs)

    def writeSensorRegs(self, fileNodes):
        global handle
        for i in range(0, len(fileNodes)):
            fileNode = fileNodes[i]
            if fileNode[0] == "DELAY":
                time.sleep(float(fileNode[1]) / 1000)
                continue
            regAddr = int(fileNode[0], 16)
            val = int(fileNode[1], 16)
            ArducamSDK.Py_ArduCam_writeSensorReg(handle, regAddr, val)


    def camera_initFromFile(self, fialeName):
        global cfg, handle, Width, Height, color_mode
        # load config file
        config = json.load(open(fialeName, "r"))

        camera_parameter = config["camera_parameter"]
        Width = int(camera_parameter["SIZE"][0])
        Height = int(camera_parameter["SIZE"][1])

        BitWidth = camera_parameter["BIT_WIDTH"]
        ByteLength = 1
        if BitWidth > 8 and BitWidth <= 16:
            ByteLength = 2

        FmtMode = int(camera_parameter["FORMAT"][0])
        color_mode = (int)(camera_parameter["FORMAT"][1])
        print("color mode", color_mode)

        I2CMode = camera_parameter["I2C_MODE"]
        I2cAddr = int(camera_parameter["I2C_ADDR"], 16)
        TransLvl = int(camera_parameter["TRANS_LVL"])
        cfg = {"u32CameraType": 0x4D091031,
               "u32Width": Width, "u32Height": Height,
               "usbType": 0,
               "u8PixelBytes": ByteLength,
               "u16Vid": 0,
               "u32Size": 0,
               "u8PixelBits": BitWidth,
               "u32I2cAddr": I2cAddr,
               "emI2cMode": I2CMode,
               "emImageFmtMode": FmtMode,
               "u32TransLvl": TransLvl}

        # ArducamSDK.
        # ret,handle,rtn_cfg = ArducamSDK.Py_ArduCam_open(cfg,0)
        ret, handle, rtn_cfg = ArducamSDK.Py_ArduCam_autoopen(cfg)
        if ret == 0:

            # ArducamSDK.Py_ArduCam_writeReg_8_8(handle,0x46,3,0x00)
            usb_version = rtn_cfg['usbType']
            # print("USB VERSION:",usb_version)
            # config board param
            self.configBoard(config["board_parameter"])

            if usb_version == ArducamSDK.USB_1 or usb_version == ArducamSDK.USB_2:
                self.configBoard(config["board_parameter_dev2"])
            if usb_version == ArducamSDK.USB_3:
                self.configBoard(config["board_parameter_dev3_inf3"])
            if usb_version == ArducamSDK.USB_3_2:
                self.configBoard(config["board_parameter_dev3_inf2"])

            self.writeSensorRegs(config["register_parameter"])

            if usb_version == ArducamSDK.USB_3:
                self.writeSensorRegs(config["register_parameter_dev3_inf3"])
            if usb_version == ArducamSDK.USB_3_2:
                self.writeSensorRegs(config["register_parameter_dev3_inf2"])

            rtn_val, datas = ArducamSDK.Py_ArduCam_readUserData(handle, 0x400 - 16, 16)
            print("Serial: %c%c%c%c-%c%c%c%c-%c%c%c%c" % (datas[0], datas[1], datas[2], datas[3],
                                                          datas[4], datas[5], datas[6], datas[7],
                                                          datas[8], datas[9], datas[10], datas[11]))
            return True
        else:
            print("open fail,rtn_val = ", ret)
            return False



