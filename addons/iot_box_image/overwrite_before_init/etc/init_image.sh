#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail
# set -o xtrace

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__file="${__dir}/$(basename "${BASH_SOURCE[0]}")"
__base="$(basename ${__file} .sh)"

# Recommends: antiword, graphviz, ghostscript, python-gevent, poppler-utils
export DEBIAN_FRONTEND=noninteractive

# single-user mode, appropriate for chroot environment
# explicitly setting the runlevel prevents warnings after installing packages
export RUNLEVEL=1

# Unset lang variables to prevent locale settings leaking from host
unset "${!LC_@}"
unset "${!LANG@}"

# set locale to en_US
echo "set locale to en_US"
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
dpkg-reconfigure locales

# Aliases
echo  "alias ll='ls -al'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias nwos='sudo systemctl stop nwos; sudo -u nwos /usr/bin/python3 /home/pi/nwos/nwos-bin --config /home/pi/nwos.conf'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias nwos_logs='less -R +F /var/log/nwos/nwos-server.log'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias nwos_conf='cat /home/pi/nwos.conf'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias install='sudo chroot /root_bypass_ramdisks/'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias blackbox='ls /dev/serial/by-path/'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias nano='sudo -u nwos nano -l'" | tee -a /home/pi/.bashrc
echo  "alias vim='sudo -u nwos vim -u /home/pi/.vimrc'" | tee -a /home/pi/.bashrc
echo  "alias nwos_luxe='printf \" ______\n< Luxe >\n ------\n        \\   ^__^\n         \\  (oo)\\_______\n            (__)\\       )\\/\\ \n                ||----w |\n                ||     ||\n\"'" | tee -a ~/.bashrc /home/pi/.bashrc
echo  "alias nwos_start='sudo systemctl start nwos'" >> /home/pi/.bashrc
echo  "alias nwos_stop='sudo systemctl stop nwos'" >> /home/pi/.bashrc
echo  "alias nwos_restart='sudo systemctl restart nwos'" >> /home/pi/.bashrc
echo "
nwos_help() {
  echo '-------------------------------'
  echo ' Welcome to NWOS IoT Box tools'
  echo '-------------------------------'
  echo ''
  echo 'nwos                  Starts/Restarts NWOS server manually (not through nwos.service)'
  echo 'nwos_logs             Displays NWOS server logs in real time'
  echo 'nwos_conf             Displays NWOS configuration file content'
  echo 'install               Bypasses ramdisks to allow package installation'
  echo 'blackbox              Lists all serial connected devices'
  echo 'nwos_start            Starts NWOS service'
  echo 'nwos_stop             Stops NWOS service'
  echo 'nwos_restart          Restarts NWOS service'
  echo 'nwos_dev <branch>     Resets NWOS on the specified branch from nwos-dev repository'
  echo 'nwos_origin <branch>  Resets NWOS on the specified branch from the nwos repository'
  echo 'devtools              Enables/Disables specific functions for development (more help with devtools help)'
  echo ''
  echo 'NWOS IoT online help: <https://www.nwos.com/documentation/latest/applications/general/iot.html>'
}

nwos_dev() {
  if [ -z \"\$1\" ]; then
    nwos_help
    return
  fi
  pwd=\$(pwd)
  cd /home/pi/nwos
  sudo -u nwos git remote add dev https://github.com/nwos-dev/nwos.git
  sudo -u nwos git fetch dev \$1 --depth=1 --prune
  sudo -u nwos git reset --hard FETCH_HEAD
  sudo -u nwos git branch -m \$1
  sudo chroot /root_bypass_ramdisks /bin/bash -c \"export DEBIAN_FRONTEND=noninteractive && xargs apt-get -y -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" install < /home/pi/nwos/addons/iot_box_image/configuration/packages.txt\"
  sudo -u nwos pip3 install -r /home/pi/nwos/addons/iot_box_image/configuration/requirements.txt --break-system-package
  cd \$pwd
}

nwos_origin() {
  if [ -z \"\$1\" ]; then
    nwos_help
    return
  fi
  pwd=\$(pwd)
  cd /home/pi/nwos
  sudo -u nwos git remote set-url origin https://github.com/nwos/nwos.git  # ensure nwos repository
  sudo -u nwos git fetch origin \$1 --depth=1 --prune
  sudo -u nwos git reset --hard FETCH_HEAD
  sudo -u nwos git branch -m \$1
  sudo chroot /root_bypass_ramdisks /bin/bash -c \"export DEBIAN_FRONTEND=noninteractive && xargs apt-get -y -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" install < /home/pi/nwos/addons/iot_box_image/configuration/packages.txt\"
  sudo -u nwos pip3 install -r /home/pi/nwos/addons/iot_box_image/configuration/requirements.txt --break-system-package
  cd \$pwd
}

pip() {
  if [[ -z \"\$1\" || -z \"\$2\" ]]; then
    nwos_help
    return 1
  fi
  additional_arg=\"\"
  if [ \"\$1\" == \"install\" ]; then
    additional_arg=\"--user\"
  fi
  pip3 \"\$1\" \"\$2\" --break-system-package \$additional_arg
}

devtools() {
  help_message() {
    echo 'Usage: devtools <enable/disable> <general/actions> [action name]'
    echo ''
    echo 'Only provide an action name if you want to enable/disable a specific device action.'
    echo 'If no action name is provided, all actions will be enabled/disabled.'
    echo 'To enable/disable multiple actions, enclose them in quotes separated by commas.'
  }
  case \"\$1\" in
    enable|disable)
      case \"\$2\" in
        general|actions|longpolling)
          if ! grep -q '^\[devtools\]' /home/pi/nwos.conf; then
            sudo -u nwos bash -c \"printf '\n[devtools]\n' >> /home/pi/nwos.conf\"
          fi
          if [ \"\$1\" == \"disable\" ]; then
            value=\"\${3:-*}\" # Default to '*' if no action name is provided
            devtools enable \"\$2\" # Remove action/general/longpolling from conf to avoid duplicate keys
            sudo sed -i \"/^\[devtools\]/a\\\\\$2 = \$value\" /home/pi/nwos.conf
          elif [ \"\$1\" == \"enable\" ]; then
            sudo sed -i \"/\[devtools\]/,/\[/{/\$2 =/d}\" /home/pi/nwos.conf
          fi
          ;;
        *)
          help_message
          return 1
          ;;
      esac
      ;;
    *)
      help_message
      return 1
      ;;
  esac
}
" | tee -a ~/.bashrc /home/pi/.bashrc

# Change default hostname from 'raspberrypi' to 'iotbox'
echo iotbox | tee /etc/hostname
sed -i 's/\braspberrypi/iotbox/g' /etc/hosts

apt-get update

# At the first start it is necessary to configure a password
# This will be modified by a unique password on the first start of NWOS
password="$(openssl rand -base64 12)"
echo "pi:${password}" | chpasswd
echo TrustedUserCAKeys /etc/ssh/ca.pub >> /etc/ssh/sshd_config

# Prevent Wi-Fi blocking
apt-get -y remove rfkill

echo "Acquire::Retries "16";" > /etc/apt/apt.conf.d/99acquire-retries
# KEEP OWN CONFIG FILES DURING PACKAGE CONFIGURATION
# http://serverfault.com/questions/259226/automatically-keep-current-version-of-config-files-when-apt-get-install
xargs apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install < /home/pi/nwos/addons/iot_box_image/configuration/packages.txt
apt-get -y autoremove

apt-get clean
localepurge
rm -rfv /usr/share/doc

# Remove the default nginx website, we have our own config in /etc/nginx/conf.d/
rm /etc/nginx/sites-enabled/default

pip3 install -r /home/pi/nwos/addons/iot_box_image/configuration/requirements.txt --break-system-package

# Create NWOS user for nwos service and disable password login
adduser --disabled-password --gecos "" --shell /usr/sbin/nologin nwos

# nwos user doesn't need to type its password to run sudo commands
cp /etc/sudoers.d/010_pi-nopasswd /etc/sudoers.d/010_nwos-nopasswd
sed -i 's/pi/nwos/g' /etc/sudoers.d/010_nwos-nopasswd

# copy the nwos.conf file to the overwrite directory
mv -v "/home/pi/nwos/addons/iot_box_image/configuration/nwos.conf" "/home/pi/"
chown nwos:nwos "/home/pi/nwos.conf"

groupadd usbusers
usermod -a -G usbusers nwos
usermod -a -G video nwos
usermod -a -G render nwos
usermod -a -G lp nwos
usermod -a -G input nwos
usermod -a -G dialout nwos
usermod -a -G pi nwos
mkdir -v /var/log/nwos
chown nwos:nwos /var/log/nwos
chown nwos:nwos -R /home/pi/nwos/

# logrotate is very picky when it comes to file permissions
chown -R root:root /etc/logrotate.d/
chmod -R 644 /etc/logrotate.d/
chown root:root /etc/logrotate.conf
chmod 644 /etc/logrotate.conf

update-rc.d -f hostapd remove
update-rc.d -f nginx remove
update-rc.d -f dnsmasq remove

systemctl enable ramdisks.service
systemctl disable dphys-swapfile.service
systemctl enable ssh
systemctl set-default graphical.target
systemctl disable getty@tty1.service
systemctl disable systemd-timesyncd.service
systemctl unmask hostapd.service
systemctl disable hostapd.service
systemctl disable cups-browsed.service
systemctl enable labwc.service
systemctl enable nwos.service
systemctl enable nwos-led-manager.service
systemctl enable nwos-ngrok.service

# create dirs for ramdisks
create_ramdisk_dir () {
    mkdir -v "${1}_ram"
}

create_ramdisk_dir "/var"
create_ramdisk_dir "/etc"
create_ramdisk_dir "/tmp"
mkdir -v /root_bypass_ramdisks

echo ""
echo "--- DEFAULT PASSWORD: ${password} ---"
echo ""
