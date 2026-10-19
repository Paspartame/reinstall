#!/bin/sh
set -eu
for str in $(grep -wo "extra_[^ ]*" /proc/cmdline | sed 's/^extra_//'); do eval "$str"; done
username=${username:-root}
ssh_port=${ssh_port:-22}
web_port=${web_port:-80}

di() {
    echo "d-i $*" >/tmp/selections.cfg
    echo "d-i $*" >>/tmp/selections.cfg.all
    debconf-set-selections /tmp/selections.cfg
    rm -f /tmp/selections.cfg
}
postinst=/var/lib/dpkg/info/bootstrap-base.postinst
cp "$postinst" "$postinst.orig"
: >"$postinst"
swapfile=/target/swapfile
mem=$(grep ^MemTotal: /proc/meminfo | { read -r _ y _; echo "$((y / 1024))"; })
swap_size=$((512 - mem))
if [ "$swap_size" -gt 0 ] && [ ! -f /reinstall-crypto-enabled ]; then
    echo "fallocate -l ${swap_size}M $swapfile; mkswap $swapfile; swapon $swapfile" >>"$postinst"
fi
echo "swapoff -a; rm -f $swapfile" >/usr/lib/finish-install.d/95swapoff
chmod a+x /usr/lib/finish-install.d/95swapoff
echo "rm -rf /target/boot/efi/*; $postinst.orig" >>"$postinst"
xda=$(sh /get-xda.sh)
debconf-set partman-auto/disk "/dev/$xda"
debconf-set grub-installer/bootdev "/dev/$xda"
rm -rf /usr/sbin/fdisk /usr/sbin/sfdisk
ttys=$(sh /ttys.sh console=)
debconf-set debian-installer/add-kernel-opts "$ttys"
if [ -f /reinstall-crypto-enabled ] && [ ! -d /dev/netconf ]; then
    eths=$(ls /sys/class/net | grep -v '^lo$')
else
    eths=$(cd /dev/netconf/ && ls)
fi
if ! sh /can_use_cloud_kernel.sh "$xda" $eths; then
    debconf-set base-installer/kernel/image "$(debconf-get base-installer/kernel/image | sed 's/-cloud//')"
fi
if [ "$(cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null)" = 'Tencent Cloud' ]; then
    for block in /sys/class/block/vd[a-z]; do
        if [ -d "$block" ]; then echo 512 >"$block/queue/max_sectors_kb"; fi
    done
    echo 'KERNEL=="vd*[a-z]", ACTION=="add|change", SUBSYSTEM=="block", RUN+="/bin/sh -c '\''/bin/echo 512 > /sys/%p/queue/max_sectors_kb'\''"' >/etc/udev/rules.d/80-max-sectors-blk.rules
    udevadm control --reload
    udevadm trigger --subsystem-match=block
    udevadm settle
    sleep 1
fi
if [ -f /reinstall-crypto-enabled ]; then
    debconf-set-selections <<'EOF'
d-i partman-auto/method string crypto
d-i partman-auto-crypto/erase_disks boolean false
d-i partman-auto-lvm/guided_size string max
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true
EOF
    sh /debian-crypto-gate.sh || { echo 'Encrypted installation blocked: passphrase handoff failed.' >/dev/console; exit 1; }
elif [ -d /sys/firmware/efi ]; then
    debconf-set partman-auto/expert_recipe "$(debconf-get partman-auto/expert_recipe_efi)"
else
    debconf-set partman-auto/expert_recipe "$(debconf-get partman-auto/expert_recipe_bios)"
fi
: >/bin/os-prober
