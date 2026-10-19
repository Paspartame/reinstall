#!/bin/sh
set -eu
true; \
    for str in $(grep -wo "extra_[^ ]*" /proc/cmdline | sed 's/^extra_//'); do eval "$str"; done; \
    username=${username:-root}; \
    ssh_port=${ssh_port:-22}; \
    web_port=${web_port:-80}; \

    if [ -f /reinstall-crypto-enabled ] && [ ! -d /dev/netconf ]; then
        iface=$(ip -4 route show default | awk 'NR==1 {print $5}')
        [ -n "$iface" ] || exit 1
        netbase=/dev/netconf/$iface
        mkdir -p "$netbase"
        cat /sys/class/net/$iface/address >"$netbase/mac_addr"
        printf '1\n' >"$netbase/ipv4_has_internet"
        printf '1\n' >"$netbase/dhcpv4"
        printf '0\n' >"$netbase/should_disable_dhcpv4"
        ip -4 addr show dev "$iface" | awk '/inet / {print $2;exit}' >"$netbase/ipv4_addr"
        ip -4 route show default | awk 'NR==1 {print $3}' >"$netbase/ipv4_gateway"
    fi
    if [ -f /reinstall-crypto-enabled ]; then \
        unlock_port=${unlock_port:-2222}; \
        netconf=$(find /dev/netconf -mindepth 2 -maxdepth 2 -name ipv4_has_internet -print | head -n 1); \
        [ -n "$netconf" ] || { echo 'Encrypted install blocked: network facts missing.' >/dev/console; exit 1; }; \
        netdir=${netconf%/*}; \
        mkdir -p /target/etc/reinstall-unlock /target/etc/dropbear/initramfs /tmp/reinstall-net-facts /target/etc/initramfs-tools/hooks /target/etc/initramfs-tools/scripts/init-premount /target/usr/local/lib/reinstall; \
        install -m 0600 /configs/ssh_keys /target/etc/dropbear/initramfs/authorized_keys; \
        install -m 0755 /usr/local/lib/reinstall/debian-unlock-hook.sh /target/etc/initramfs-tools/hooks/reinstall-unlock; \
        for f in mac_addr ipv4_has_internet dhcpv4 should_disable_dhcpv4 ipv4_addr ipv4_gateway; do cp "$netdir/$f" "/tmp/reinstall-net-facts/$f"; done; \
        chroot /target env -u DEBIAN_HAS_FRONTEND -u DEBCONF_REDIR -u DEBCONF_FRONTEND DEBIAN_FRONTEND=noninteractive apt-get install -y python3; \
        cp /debian-unlock-config.py /target/usr/local/lib/reinstall/; \
        cp /configs/ssh_keys /target/etc/reinstall-unlock/setup.pub; \
        cp -r /tmp/reinstall-net-facts /target/etc/reinstall-unlock/setup-facts; \
        chroot /target python3 /usr/local/lib/reinstall/debian-unlock-config.py /run/reinstall-generated /etc/reinstall-unlock/setup.pub /etc/reinstall-unlock/setup-facts "$unlock_port" || { echo 'Encrypted install blocked: invalid SSH/network config.' >/dev/console; exit 1; }; \
        for helper in debian-unlock-hook.sh debian-unlock-network.sh initrd-network.sh; do install -m 0755 "/usr/local/lib/reinstall/$helper" "/target/usr/local/lib/reinstall/$helper"; done; \
        cp -r /target/run/reinstall-generated/etc/. /target/etc/; \
        rm -rf /target/run/reinstall-generated; \
        cp /debian-unlock-install.sh /target/usr/local/sbin/debian-unlock-install.sh; \
        chroot /target env -u DEBIAN_HAS_FRONTEND -u DEBCONF_REDIR -u DEBCONF_FRONTEND DEBIAN_FRONTEND=noninteractive /usr/local/sbin/debian-unlock-install.sh || { echo 'Encrypted install blocked: target unlock initramfs setup failed.' >/dev/console; exit 1; }; \
        rm -rf /tmp/reinstall-net-facts /target/etc/reinstall-unlock/setup.pub /target/etc/reinstall-unlock/setup-facts; \
    fi; \

    if [ -f /reinstall-crypto-enabled ]; then \
        if ! sh /debian-crypto-cleanup.sh; then \
            echo 'Encrypted installation blocked: secret cleanup failed.' >/dev/console; \
            while :; do sleep 60; done; \
        fi; \
    fi; \
    if [ "${elts:-0}" = 1 ]; then sed -i "s|deb\.freexian\.com/extended-lts|$deb_mirror|" /target/etc/apt/sources.list; fi; \

    if [ "${link_grub_dir:-0}" = 1 ]; then ln -s grub /target/boot/grub2; fi; \

    in-target systemctl enable ssh; \

    if [ "$username" = root ]; then \
        user_home=/root; \
    else \
        user_home=/home/$username; \
    fi; \

    if [ -s /configs/ssh_keys ]; then \
        ( \
            umask 077; \
            mkdir -p "/target/$user_home/.ssh"; \
            cat /configs/ssh_keys >"/target/$user_home/.ssh/authorized_keys"; \
        ); \
        in-target passwd -d -l "$username"; \
        in-target chown "$username:$username" "$user_home"; \
        in-target chown "$username:$username" "$user_home/.ssh"; \
        in-target chown "$username:$username" "$user_home/.ssh/authorized_keys"; \

        echo "PasswordAuthentication no" >/target/etc/ssh/sshd_config.d/01-passwordauthentication.conf || \
            sed -Ei "s|^#? *PasswordAuthentication .*|PasswordAuthentication no|i" /target/etc/ssh/sshd_config; \

    else \
        if [ "$username" = root ]; then \
            echo "PermitRootLogin yes" >/target/etc/ssh/sshd_config.d/01-permitrootlogin.conf || \
                sed -Ei "s|^#? *PermitRootLogin .*|PermitRootLogin yes|i" /target/etc/ssh/sshd_config; \
        fi; \
    fi; \

    if ! [ "$ssh_port" = 22 ]; then \
        echo "Port $ssh_port" >/target/etc/ssh/sshd_config.d/01-port.conf || \
            sed -Ei "s|^#? *Port .*|Port $ssh_port|i" /target/etc/ssh/sshd_config; \
    fi; \

    if ! [ "$username" = root ]; then \
        printf '%s\n' "$username ALL=(ALL) NOPASSWD:ALL" >"/target/etc/sudoers.d/99-$username"; \
        chmod 0440 "/target/etc/sudoers.d/99-$username"; \
    fi; \

    if ls /configs/frpc.* >/dev/null 2>&1; then \
        mkdir -p /target/usr/local/bin; \
        mkdir -p /target/usr/local/etc/frpc; \
        cp /usr/local/bin/frpc /target/usr/local/bin/; \
        cp /usr/local/etc/frpc/frpc.* /target/usr/local/etc/frpc/frpc.toml; \
        cp /frpc.service /target/etc/systemd/system/; \
        in-target chmod ug+x /usr/local/bin/frpc; \
        if (. /target/etc/os-release && [ "$ID" = debian ] && [ "$VERSION_ID" -le 10 ]); then \
            sed -i 's/^\[X-Service-Old\]$/[Service]/' /target/etc/systemd/system/frpc.service; \
            in-target useradd --system --no-create-home --home-dir /nonexistent --shell /sbin/nologin frpc; \
            in-target chown root:frpc /usr/local/etc/frpc/frpc.toml; \
            in-target chmod 640 /usr/local/etc/frpc/frpc.toml; \
        else \
            sed -i 's/^\[X-Service-New\]$/[Service]/' /target/etc/systemd/system/frpc.service; \
            in-target chown root:root /usr/local/etc/frpc/frpc.toml; \
            in-target chmod 600 /usr/local/etc/frpc/frpc.toml; \
        fi; \
        in-target systemctl enable frpc; \
    fi; \

    cp /fix-eth-name.sh /target/; \
    cp /fix-eth-name.service /target/etc/systemd/system/; \
    in-target systemctl enable fix-eth-name; \

    if [ "$(cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null)" = 'Tencent Cloud' ]; then \
        echo 'KERNEL=="vd*[a-z]", ACTION=="add|change", SUBSYSTEM=="block", RUN+="/bin/sh -c '\''/bin/echo 512 > /sys/%p/queue/max_sectors_kb'\''"' >/target/etc/udev/rules.d/80-max-sectors-blk.rules; \
        in-target update-initramfs -u -k all; \
    fi
