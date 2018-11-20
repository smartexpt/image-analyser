from subprocess import call

def powerOffUSBs():
   call("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/unbind")
   print('Shutted down USB ports.')

def powerOnUSBs():
    call("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/bind")
    print('Booted on USB ports.')

# if __name__ == "__main__":
