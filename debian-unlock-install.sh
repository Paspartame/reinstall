#!/bin/sh
# Run explicitly inside a Debian 13 target after config generation; never host.
set +x
set -eu
. /etc/os-release
[ "$ID" = debian ] && [ "$VERSION_ID" = 13 ]
[ -s /etc/reinstall-unlock/network.conf ]
[ -s /etc/dropbear/initramfs/authorized_keys ]
export DEBIAN_FRONTEND=noninteractive
apt-get install -y cryptsetup-initramfs dropbear-initramfs
# Debian package postinst generates independent keys once, preserving existing ones.
umask 077
: >/root/luks-unlock-hostkey-fingerprints.txt
for key in /etc/dropbear/initramfs/dropbear_*_host_key; do
    [ -f "$key" ] || continue
    dropbearkey -y -f "$key" | sed -n '/^Fingerprint:/p' >>/root/luks-unlock-hostkey-fingerprints.txt
done
[ -s /root/luks-unlock-hostkey-fingerprints.txt ]
install -m 0755 /usr/local/lib/reinstall/debian-unlock-hook.sh /etc/initramfs-tools/hooks/reinstall-unlock
mkdir -p /etc/initramfs-tools/scripts/init-premount
install -m 0755 /usr/local/lib/reinstall/debian-unlock-network.sh /etc/initramfs-tools/scripts/init-premount/reinstall-unlock-network
# Local override preserves Debian lifecycle while adding a network prerequisite.
sed -e 's/^PREREQ="udev"$/PREREQ="udev reinstall-unlock-network"/' -e '/^\[ -x \/sbin\/dropbear \]/i [ ! -e /run/reinstall-unlock-network-failed ] || exit 1' /usr/share/initramfs-tools/scripts/init-premount/dropbear >/etc/initramfs-tools/scripts/init-premount/dropbear
chmod 0755 /etc/initramfs-tools/scripts/init-premount/dropbear
update-initramfs -u -k all
