import datetime
from Queue import Queue
from threading import Thread
import uuid
import os
import requests
from PIL import Image
from boto.s3.key import Key
import base64
from io import BytesIO
import logging
from ws_connectivity import WebSockets, AWS, WebServer
import numpy as np
import cv2
from scipy import misc

class FabricWorker:

    def __init__(self, maxsize, bucket, client, operation_configs):
        self.client = client
        self.bucket = bucket
        self.operationConfigs = operation_configs
        self.queue = Queue(maxsize=maxsize)
        self.thread = Thread(target=self.upload)
        self.thread.setDaemon(True)
        self.thread.start()

    def add_work(self, obj):
        logging.info("Adding object to worker queue! Queue has now " + str(self.queue.qsize()) + " elements!")
        self.queue.put(obj)

    def upload(self):
        self.img_ant = ""
        while True:
            try:
                obj = self.queue.get()
                image_path = obj["path"]
                fabric = obj["fabric"]
                fabric["mse"] = 100.0
                paths = self.upload_image(image_path)
                try:
                    begin = datetime.datetime.now()
                    im1 = cv2.imread(image_path)
                    gray1 = cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY)
                    im2 = cv2.imread(self.img_ant)
                    gray2 = cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY)
                    m = self.mse(gray1, gray2)
                    #im1 = misc.imresize(misc.imread(image_path), 0.3)  # reading image1
                    #im2 = misc.imresize(misc.imread(self.img_ant), 0.3)  # reading image2
                    #im3 = abs(np.int32(im2) - np.int32(im1))
                    #difavg = np.average(im3)
                    fabric["mse"] = m
                    #fabric["difavg"] = difavg
                    elapsed = datetime.datetime.now() - begin
                    logging.info("MSE of " + str(m) + " - elapsed time (s): {}\n".format(elapsed.total_seconds()))
                except Exception as ex:
                    logging.exception("Error calculating mse for " + image_path + " and " + self.img_ant)
                fabric["imageUrl"] = paths["img_url"]
                fabric["thumbUrl"] = paths["thumb_url"]
                self.upload_fabric(fabric)
                self.queue.task_done()
                try:
                    os.remove(self.img_ant)
                except:
                    pass
                self.img_ant = image_path
            except Exception as ex:
                logging.exception("Error uploading fabric object!")
                aws = AWS(self.operationConfigs)
                webServer = WebServer(self.operationConfigs)
                aws.connectAWSS3()
                webServer.authWS()
                self.bucket = aws.bucket
                self.client = webServer.client
                continue

    def mse(self, imageA, imageB):
        err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
        err /= float(imageA.shape[0] * imageA.shape[1])

        # return the MSE, the lower the error, the more "similar" the two images are
        return err

    def upload_fabric(self, fabric):
        begin = datetime.datetime.now()
        r = self.client.post(self.operationConfigs['FABRIC_ENDPOINT'], data=fabric)
        if(r.status_code != 200):
            raise Exception('Bad response status code!')
        elapsed = datetime.datetime.now() - begin
        logging.info("\nFabric object uploaded - elapsed time (s): {}".format(elapsed.total_seconds()))

    def upload_image(self, image_path):
        if self.operationConfigs['storage'] == "ONLINE":
            return self.upload_aws(image_path)
        else:
            return self.upload_local(image_path)

    def upload_aws(self, image_path):
        begin = datetime.datetime.now()
        fuuid = str(uuid.uuid4())
        k = Key(self.bucket)
        k.key = 'F_' + fuuid + '.png'
        k.set_contents_from_filename(image_path)
        img_url = 'https://' + self.operationConfigs['REGION_HOST'] + '/' + self.operationConfigs[
            'AWS_BUCKET'] + '/' + k.key
        k.set_acl('public-read')

        im = Image.open(image_path)
        im.thumbnail((128, 128), Image.ANTIALIAS)
        head, tail = os.path.split(image_path)
        thumb_path = head + "/T_" + tail
        im.save(thumb_path, "PNG")

        k = Key(self.bucket)
        k.key = "T_" + fuuid + '.png'
        k.set_contents_from_filename(thumb_path)
        thumb_url = 'https://' + self.operationConfigs['REGION_HOST'] + '/' + self.operationConfigs[
            'AWS_BUCKET'] + '/' + k.key
        k.set_acl('public-read')

        paths = {
            'img_url': img_url,
            'thumb_url': thumb_url
        }
        elapsed = datetime.datetime.now() - begin
        logging.info("Image uploaded - elapsed time (s): {}\n".format(elapsed.total_seconds()))

        os.remove(thumb_path)
        return paths

    def upload_local(self, image_path):
        begin = datetime.datetime.now()
        fuuid = str(uuid.uuid4())
        name = 'F_' + fuuid + '.png'

        with open(image_path, "rb") as imageFile:
            b64Img = base64.b64encode(imageFile.read())

        img = {
            name: "data:image/png;base64, " + b64Img
        }
        r = requests.post("http://" + self.operationConfigs['STORAGE_ENDPOINT'] + "/" + name, json=img)

        img_url = self.operationConfigs['WS_ENDPOINT'] + 'fabrics/' + name

        im = Image.open(self.imagePath)
        im.thumbnail((128, 128), Image.ANTIALIAS)

        name = "T_" + fuuid + '.png'
        buff = BytesIO()
        im.save(buff, format="JPEG")
        b64Img = base64.b64encode(buff.getvalue()).decode("utf-8")

        img = {
            name: "data:image/png;base64, " + b64Img
        }
        r = requests.post("http://" + self.operationConfigs['STORAGE_ENDPOINT'] + "/" + name, json=img)

        thumb_url = self.operationConfigs['WS_ENDPOINT'] + 'fabrics/' + name

        paths = {
            'img_url': img_url,
            'thumb_url': thumb_url
        }
        elapsed = datetime.datetime.now() - begin
        logging.info("Image uploaded - elapsed time (s): {}\n".format(elapsed.total_seconds()))


        return paths

    def join(self):
        self.queue.join()
        self.thread.join()