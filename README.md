# HOW TO SETUP
Create 4 Virtual Machines (VM) VirtualBox (Attacker, Fail2Ban, Machine Learning, Monitoring):
- OS Debian 12.7.0
- Guided - use entire disk
- All Files in one partition
- No GUI (only check web server, SSH server, and standard system utilities)
- Bridged Adapter + Host-only Adapter

/etc/network/interfaces in the VMs
```bash
# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces (5).

source /etc/network/interfaces.d/*

# Loopback network interface
auto lo
iface lo inet loopback

# Primary network interface (DHCP)
allow-hotplug enp0s3
iface enp0s3 inet dhcp

# Secondary network interface (Static)
auto enp0s8
iface enp0s8 inet static
    address 192.168.67.11/24
```

Windows Network Configuration
<img width="1235" height="741" alt="image" src="https://github.com/user-attachments/assets/66dc6ff3-d5c4-4804-9f25-ffe025645b71" />


----------
Setup VM Victim Fail2Ban
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install fail2ban openssh-server git -y
```

Setup VM Attacker
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install hydra openssh-server git -y
```

Setup VM Monitoring
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install iperf3 tcpdump git -y
```

Test attack with Hydra
```bash
hydra -l root -P <wordlists.txt> - t <thread> <Target IP Address> ssh
```

Setup Fail2bBan
```bash
systemctl start fail2ban
systemctl status fail2ban
fail2ban-client status
```

In the Fail2Ban folder, clone the jail.conf file into jail.local.
Some part of the jail.local script should modified into below:
```bash
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 5
bantime  = 5
findtime = 600
ignoreip = 127.0.0.1 ::1 192.168.67.14 192.168.67.1 
action   = iptables-multiport[name=sshd, port="ssh", protocol="tcp"]
           telegram[name=sshd]
```

Telegram Notification Script: Create the file in /etc/fail2ban/action.d/telegram.conf
```bash
# /etc/fail2ban/action.d/telegram.conf
[Definition]
actionstart =
actionstop =
actioncheck =
actionban = curl -s -X POST "https://api.telegram.org/bot<bot_token>/sendMessage" \
             -d chat_id="<chat_id>" \
             -d text="🚨 [Fail2Ban] <name>: IP <ip> telah diblokir selama <bantime> detik karena percobaan login gagal."
actionunban = curl -s -X POST "https://api.telegram.org/bot<bot_token>/sendMessage" \
               -d chat_id="<chat_id>" \
               -d text="✅ [Fail2Ban] <name>: IP <ip> telah dibuka kembali."

[Init]
bot_token = <BOT_TOKEN>
chat_id = <CHAT_ID>
```
Note that you have to fill the bot token and chat id in order to make this script work.

-----------
Setup VM Machine Learning
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip tcpdump ufw buildessential python3-dev libpcap-dev git
pip install numpy scikit-learn==1.7.1 joblib pandas requests scapy
```

- Put mldetector.service and pcapworker.service as service in Systemd
<br>note that you have to edit lines in the service files such as below:
```bash
#pcapworker.service
User=pros
Group=pros
WorkingDirectory=YOUR_PATH
ExecStart=YOUR_PATH/venv/bin/python YOUR_PATH/PCAPWorker.py

# mldetector.service
ExecStart=YOUR_PATH/venv/bin/python YOUR_PATH/MLDetector.py
Environment="PATH=YOUR_PATH/venv/bin:/usr/bin:/bin"
ExecStart=YOUR_PATH/venv/bin/python YOUR_PATH/MLDetector.py
```

- Execute start-tcpdump.sh in crontab (/tmp/crontab.UOkF0Q/crontab)
```bash
@reboot /your-path/start-tcpdump.sh
```
-------------------



