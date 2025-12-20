#!/bin/bash

# RUN THIS SCRIPT IN CRONTAB
while true; do
    if ! pgrep -x "tcpdump" > /dev/null; then
        echo "$(date) - tcpdump not running, starting..." >> /home/pros/pcap/log/tcpdump_watchdog.log
        exec tcpdump i enp0s8 'tcp port 22' \
        -w/YOUR_PATH/pcap/rotated/ssh_%Y%m%d%H%M%S.pcap \
        -G5-W 100-n-s 0-2 root
        > YOUR_PATH/pcap/log/tcpdump.log 2>&1 < /dev/null &
    fi
    sleep 5 # cek tiap 5 detik
done &