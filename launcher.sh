#!/bin/sh
# launcher.sh
# navigate to home directory, then to this directory, then execute python script, then back home

cd /
cd home/smartex/
echo 'lycralycra' | sudo -i -u smartex python image-analyser/main_v05.py
cd /
