#!/bin/sh
# Internal partman/early_command integration. Not a public installer entry point.
# Caller must preserve stdin when backgrounding the receiver (confmodule replies).
set +x
set -eu
[ -f /reinstall-crypto-enabled ] || exit 1
[ "$(cat /etc/default-release)" = trixie ] || exit 1
[ -z "${DEBCONF_DEBUG-}${DEBCONF_DEBUGFILE-}" ] || exit 1
. /usr/share/debconf/confmodule
# Start the receiver with the existing frontend's reply FD, not /dev/null.
exec 6<&0
/usr/local/sbin/reinstall-luks-receiver <&6 &
receiver=$!
trap 'kill "$receiver" 2>/dev/null || :; exit 1' HUP INT TERM
# An authenticated installer administrator runs the helper independently.
# The receiver exits zero only after the helper has acknowledged its OK status.
wait "$receiver" || exit 1
trap - HUP INT TERM
exec 6<&-
# CAPB is shared with partman; never leave escape enabled for unrelated callers.
db_capb backup align
db_fset partman-crypto/passphrase seen true
db_fset partman-crypto/passphrase-again seen true
mode=bios
[ ! -d /sys/firmware/efi ] || mode=efi
recipe=$(sh /debian-crypto-recipe.sh "$mode" | tr '\n' ' ')
db_set partman-auto/expert_recipe "$recipe"
db_get pkgsel/include
case " $RET " in
    *' cryptsetup-initramfs '*) ;;
    *) db_set pkgsel/include "${RET:+$RET }cryptsetup-initramfs lvm2";;
esac
db_set partman-auto/method crypto
db_set partman-auto-lvm/guided_size max
db_set partman-auto-crypto/erase_disks false
db_set partman-lvm/confirm true
db_set partman-lvm/confirm_nooverwrite true
# No password value is printed or written to preseed. Partman consumes the DB.
