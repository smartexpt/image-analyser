from subprocess import call

def powerOffUSBs():
    call("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/unbind")
    return

##def powerOnUSBs():
##    call("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/bind")
##    return

if __name__ == "__main__":
    powerOffUSBs()
##    powerOnUSBs()