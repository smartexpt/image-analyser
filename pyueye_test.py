from pyueye import ueye
import ctypes
import datetime
from time import sleep
import os

timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

directory = '/home/arocha17/SMARTEX_TESTS/image_pyueyetest/grp_{}/'.format(timestamp)

if not os.path.exists(directory):
    os.makedirs(directory)

for i in range(20):

    if i==3:
        print('apontar para a cara AGORA!')
        sleep(6)
        timestamp_cara = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

#INIT
    hcam = ueye.HIDS(0)
    pccmem = ueye.c_mem_p()
    memID = ueye.c_int()
    hWnd = ctypes.c_voidp()
    ueye.is_InitCamera(hcam, hWnd)
    ueye.is_SetDisplayMode(hcam, 0)
    sensorinfo = ueye.SENSORINFO()
    ueye.is_GetSensorInfo(hcam, sensorinfo)

#TAKE PHOTO  
    ueye.is_AllocImageMem(hcam, sensorinfo.nMaxWidth, sensorinfo.nMaxHeight,24, pccmem, memID)
    ueye.is_SetImageMem(hcam, pccmem, memID)
    ueye.is_SetDisplayPos(hcam, 100, 100)

    nret = ueye.is_FreezeVideo(hcam, ueye.IS_WAIT)
    print(nret)

    timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    img_name = "img_" + timestamp + ".jpg"
    img_path = directory + img_name

    FileParams = ueye.IMAGE_FILE_PARAMS()
    FileParams.pwchFileName = img_path
    FileParams.nFileType = ueye.IS_IMG_BMP
    FileParams.ppcImageMem = None
    FileParams.pnImageID = None

    nret = ueye.is_ImageFile(hcam, ueye.IS_IMAGE_FILE_CMD_SAVE, FileParams, ueye.sizeof(FileParams))
    print(nret)
    ueye.is_FreeImageMem(hcam, pccmem, memID)
    sleep(2)
    
#EXIT CAMERA
    ueye.is_ExitCamera(hcam)

print('as imagens sao da minha cara a partir de {}'.format(timestamp_cara))


