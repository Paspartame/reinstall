#!/bin/sh
set -eu
trap 'rc=$?; echo S73_EARLY_EXIT_$rc >/dev/console' EXIT
touch /tmp/S70_PRESEED_EARLY_COMMAND; echo S70_PRESEED_EARLY_COMMAND >/dev/console; true; \
    for str in $(grep -wo "extra_[^ ]*" /proc/cmdline | sed 's/^extra_//'); do eval "$str"; done; \
    username=${username:-root}; \
    ssh_port=${ssh_port:-22}; \
    web_port=${web_port:-80}; \

    di(){ \
        echo "d-i $*" >/tmp/selections.cfg; \
        echo "d-i $*" >>/tmp/selections.cfg.all; \
        debconf-set-selections /tmp/selections.cfg; \
        rm -f /tmp/selections.cfg; \
    }; \
    if [ -f /reinstall-crypto-enabled ]; then \
        di partman-auto/method string crypto; \
        di partman-auto-crypto/erase_disks boolean false; \
        di partman-auto-lvm/guided_size string max; \
        di partman-lvm/confirm boolean true; \
        di partman-lvm/confirm_nooverwrite boolean true; \
        di pkgsel/include string "cryptsetup-initramfs lvm2 dropbear-initramfs"; \
    fi; \
    # Network readiness belongs to netcfg, not the early preseed hook.
    run_as_service_with_screen() { \
        if ! [ -f /etc/screenrc.bak ]; then \
            cp /etc/screenrc /etc/screenrc.bak; \
        fi; \
        true >/etc/screenrc; \
        if [ -f /reinstall-crypto-enabled ]; then \
            screen -dmS "reinstall-${1##*/}" sh -c 'while true; do pidof ${1##*/} || "$@"; sleep 5; done' _ "$@"; \
        else \
            screen sh -c 'while true; do pidof ${1##*/} || "$@"; sleep 5; done' _ "$@"; \
        fi; \
        cp -f /etc/screenrc.bak /etc/screenrc; \
    }; \

    echo S73_PHASE_SCREEN >/dev/console; \
    chmod +s /usr/bin/screen; \

    if screen -ls root/ >/dev/null 2>&1; then \
        screen -x root/ -X multiuser on; \
        screen -x root/ -X acladd "$username"; \
    elif [ ! -f /reinstall-crypto-enabled ]; then \
        screen -x root/ -X multiuser on; \
        screen -x root/ -X acladd "$username"; \
    fi; \

    echo S73_PHASE_HOLD >/dev/console; \
    echo S73_HOLD_${hold:-UNSET} >/dev/console; \
    if [ "$hold" = 1 ]; then \
        di auto-install/enable boolean false; \
        di debconf/priority select low; \
        di partman/early_command string; \
    else \
        { \
            echo 'Reinstalling...'; \
            echo 'Option 1. View logs:'; \
            echo '    tail -fn+1 /var/log/syslog'; \
            echo 'Option 2. Attach to the installer:'; \
            echo '    TERM=screen screen -x root/ -p 1'; \
            echo 'Option 3. Attach to the root shell if you are not root:'; \
            echo '    TERM=screen screen -x root/ -p 2'; \
        } >>/etc/motd; \
        echo S73_MOTD_DONE >/dev/console; \
        mem=$(grep ^MemTotal: /proc/meminfo | { read -r _ y _; echo "$((y / 1024))"; }); \
        echo S73_MEMORY_DONE >/dev/console; \
        if command -v websocketd && [ "$mem" -ge 400 ] && { [ ! -f /reinstall-crypto-enabled ] || [ -n "${web_path:-}" ]; }; then \
            mkdir -p /tmp/web; \
            echo 'Wrong Path' >/tmp/web/index.html; \
            for _ in {1..10}; do \
                if wget "$confhome/logviewer.html" -O /tmp/web$web_path; then \
                    break; \
                fi; \
                sleep 5; \
            done; \
            run_as_service_with_screen websocketd --port "$web_port" --loglevel=fatal --staticdir=/tmp/web \
                sh -c "if [ \"\$PATH_INFO\" = \"$web_path\" ]; then tail -fn+0 /var/log/syslog | tr '\r' '\n' | grep -Fiv -e password -e token; fi" ; \
        fi; \
    fi; \

    if ! [ "$hold" = 2 ]; then \
        di finish-install/reboot_in_progress note; \
    fi; \

    echo S73_PHASE_USER >/dev/console; \
    mkdir -p /home; \
    chmod 755 /home; \

    if [ "$username" = "root" ]; then \
        uid=0; \
        scope=root; \
        user_home=/; \
        di passwd/root-login boolean true; \
        di passwd/make-user boolean false; \
    else \
        uid=1000; \
        scope=user; \
        user_home=/home/$username; \
        di passwd/root-login boolean false; \
        di passwd/make-user boolean true; \
        di passwd/user-fullname string "$username"; \
        di passwd/username string "$username"; \
    fi; \

    if [ -s /configs/ssh_keys ]; then \
        password_hash_for_initrd=''; \
        password_hash_for_preseed='*'; \
    else \
        password_hash_for_initrd=$(cat /configs/password-linux-sha512); \
        password_hash_for_preseed=$(cat /configs/password-linux-sha512); \
    fi; \

    di passwd/$scope-password-crypted password "$password_hash_for_preseed"; \

    grep -qs ^$username: /etc/passwd || echo "$username:*:$uid:$uid:$username:$user_home:/bin/sh" >>/etc/passwd; \
    grep -qs ^$username: /etc/group || echo "$username:*:$uid:" >>/etc/group; \
    grep -qs ^$username: /etc/shadow || echo "$username:$password_hash_for_initrd:1:0:99999:7:::" >>/etc/shadow; \
    grep -qs ^nogroup: /etc/group || echo "nogroup:*:65534:" >>/etc/group; \
    grep -qs ^sshd: /etc/passwd || echo "sshd:*:100:65534::/run/sshd:/bin/false" >>/etc/passwd; \

    mkdir -p /etc/ssh/; \
    true >/etc/ssh/sshd_config; \

    if [ -s /configs/ssh_keys ]; then \
        ( \
            umask 077; \
            mkdir -p "$user_home/.ssh"; \
            cat /configs/ssh_keys >"$user_home/.ssh/authorized_keys"; \
        ); \
        chown "$username:$username" "$user_home"; \
        chown "$username:$username" "$user_home/.ssh"; \
        chown "$username:$username" "$user_home/.ssh/authorized_keys"; \
        echo "PasswordAuthentication no" >>/etc/ssh/sshd_config; \

        if grep -Eiq 'stretch|buster|bullseye' /etc/default-release; then \
            echo "ChallengeResponseAuthentication no" >>/etc/ssh/sshd_config; \
        fi; \
        echo "KbdInteractiveAuthentication no" >>/etc/ssh/sshd_config; \

    else \
        if [ "$username" = root ]; then \
            echo "PermitRootLogin yes" >>/etc/ssh/sshd_config; \
        fi; \
    fi; \

    if ! [ "$ssh_port" = 22 ]; then \
        echo "Port $ssh_port" >>/etc/ssh/sshd_config; \
    fi; \

    mkdir -p /run/sshd; \
    chmod 0755 /run/sshd; \
    echo S73_PHASE_SSH_KEYS >/dev/console; \
    ssh-keygen -A; \
    run_as_service_with_screen /usr/sbin/sshd -D; \
    echo S73_PHASE_SSH_DONE >/dev/console; \
    if [ -f /reinstall-crypto-enabled ]; then \
        printf 'S74_HOSTKEY ' >/dev/console; \
        cat /etc/ssh/ssh_host_ed25519_key.pub >/dev/console; \
    fi; \

    if ls /configs/frpc.* >/dev/null 2>&1; then \
        url=$(sh /get-frpc-url.sh linux); \
        mkdir -p /usr/local/bin; \
        mkdir -p /usr/local/etc/frpc; \
        for _ in {1..10}; do \
            if wget -O- "$url" | tar xz "*/frpc" -O >/usr/local/bin/frpc; then \
                break; \
            fi; \
            sleep 5; \
        done; \
        chmod a+x /usr/local/bin/frpc; \
        cp /configs/frpc.* /usr/local/etc/frpc/; \
        chmod 600 /usr/local/etc/frpc/*; \
        run_as_service_with_screen /usr/local/bin/frpc -c /usr/local/etc/frpc/frpc.*; \
    fi; \

    if [ -d /cdrom/simple-cdd ]; then \
        anna-install simple-cdd-profiles; \
    fi

# debian 11 initrd 没有 xargs awk
# debian 12 initrd 没有 xargs
# efi 分区大小未改变时，不会被格式化，因此需要手动删除旧系统的 efi 文件
# os-prober 卡太久，因此跳过
