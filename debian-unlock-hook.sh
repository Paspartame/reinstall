#!/bin/sh
# Internal initramfs hook. Standard Debian Dropbear hooks own keys and lifecycle.
set -eu
case "${1-}" in prereqs) echo dropbear; exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_file config /etc/reinstall-unlock/network.conf
copy_file script /usr/local/lib/reinstall/initrd-network.sh /lib/reinstall-initrd-network.sh
copy_exec /usr/sbin/ip /sbin/ip
manual_add_modules virtio_net
# Keep all normal initramfs-tools NIC handling in addition to virtio_net.
auto_add_modules net
# Runtime scripts are installed in /etc/initramfs-tools/scripts by the installer.
