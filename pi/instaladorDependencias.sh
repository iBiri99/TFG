sudo apt install python3-pip
sudo apt install hostapd
sudo apt install dnsmasq
sudo systemctl unmask hostadp
sudo systemctl disable hostadp
sudo systemctl disable dnsmasq
sudo apt-get install --download-only samba
curl "https://www.raspberryconnect.com/images/hsinstaller/AutoHotspot-Setup.tar.gz" -o AutoHotspot-Setup.tar.gz
tar -xzvf AutoHotspot-Setup.tar.gz
sudo pip3 install Flask
sudo pip3 install flask_wtf
sudo pip3 install wtforms
sudo pip3 install psutil
sudo pip3 install pyinotify
sudo pip3 install configparser
#añadir para que se inicie automaticamente el script en el inicio.:D.
