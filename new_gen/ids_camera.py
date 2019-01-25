from time import sleep
import datetime
from pyueye import ueye
import numpy as np
from scipy import misc, ndimage
import ctypes
import logging

class Camera:
    OP_OK = 0
    OP_ERR = -1
    def __init__(self, operation_configs):
        self.operationConfigs = operation_configs

        while self.initCamera() != self.OP_OK and self.operationConfigs['CAMERA_RETRYS'] > 0:
            logging.warning('Error in initCamera()')
            self.operationConfigs['CAMERA_RETRYS'] -= 1

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
            auto_res = ueye.is_SetAutoParameter(self.hcam, ueye.IS_SET_ENABLE_AUTO_SHUTTER, ctypes.c_double(1), ctypes.c_double(1))
            try:
                auto_res = ueye.GetExposureRange()
                print auto_res
            except Exception as Ex:
                print Ex
                pass
            print auto_res
            return self.OP_OK
        except Exception as ex:
            logging.exception("Error during camera initialization!")
            return self.OP_ERR

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
        #sleep(.01)
        #ueye.is_ExitCamera(self.hcam)
        self.image = np.uint8(ndimage.imread(self.imagePath, flatten=True))
        self.image = self.crop_end(self.image, 0, 100)

    def crop_end(self, img, cropx, cropy):
        y, x = img.shape
        endx = x - cropx
        endy = y - cropy
        return img[0:endy, 0:endx]