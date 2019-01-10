from time import sleep
import numpy as np
from scipy import signal
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import cv2
from skimage.measure import compare_ssim as ssim


def mse(imageA, imageB):
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])

    # return the MSE, the lower the error, the more "similar" the two images are
    return err

def compare_images(imageA, imageB, title="compare"):
    # compute the mean squared error and structural similarity index for the images
    m = mse(imageA, imageB)
    s = ssim(imageA, imageB)

    # setup the figure
    fig = plt.figure(title)
    plt.suptitle("MSE: %.2f, SSIM: %.2f" % (m, s))

    # show first image
    ax = fig.add_subplot(1, 2, 1)
    plt.imshow(imageA, cmap=plt.cm.gray)
    plt.axis("off")

    # show the second image
    ax = fig.add_subplot(1, 2, 2)
    plt.imshow(imageB, cmap=plt.cm.gray)
    plt.axis("off")

    # show the images
    plt.show()

if __name__ == "__main__":
    paths = ["andar1.png", "andar2.png", "parado1.png", "parado2.png"]
    ant = "andar1.png"
    for path in paths:
        im1 = cv2.imread(ant)
        gray1 = cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY)
        im2 = cv2.imread(path)
        gray2 = cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY)
        #plt.imshow(gray1)
        #plt.show()
        #plt.imshow(gray2)
        #plt.show()
        compare_images(gray1, gray2)
        print "Correlating " + ant + " with " + path
        #cor = signal.correlate(gray1, gray2)
        #plt.imshow(cor)
        #plt.show()
        #r = cor[0, 1]
        #print "Correlation = " + str(r)

        ant = path