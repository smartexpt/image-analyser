#!/bin/sh
# launcher.sh
# navigate to home directory, then to this directory, then execute python script, then back home
cd /home/smartex/image-analyser/new_gen
pigpiod
sleep 2
sudo -i -u smartex python /home/smartex/image-analyser/new_gen/smartex.py
cd /
