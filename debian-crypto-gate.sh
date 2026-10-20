#!/bin/sh
# Internal partman/early_command integration. Not a public installer entry point.
PATH=/usr/local/lib/reinstall/applets:$PATH
export PATH
# Caller must preserve stdin when backgrounding the receiver (confmodule replies).
set +x
set -eu
[ -f /reinstall-crypto-enabled ] || exit 1
[ "$(cat /etc/default-release)" = trixie ] || exit 1
[ -z "${DEBCONF_DEBUG-}${DEBCONF_DEBUGFILE-}" ] || exit 1
. /usr/share/debconf/confmodule
# Start the receiver with the existing frontend's reply FD, not /dev/null.
exec 6<&0
attempt=0
while :; do
    attempt=$((attempt + 1))
    /usr/local/sbin/reinstall-luks-receiver <&6 &
    receiver=$!
    trap 'kill "$receiver" 2>/dev/null || :; exit 1' HUP INT TERM
    # Only an acknowledged complete two-entry secret advances partman.
    if wait "$receiver"; then break; fi
    # Receiver trap clears partial database values and removes private IPC.
    [ ! -e /run/reinstall-luks ] || exit 1
    [ "$attempt" -lt 3 ] || exit 1
    echo 'Encrypted install: interrupted passphrase interaction; reconnect and run luks-wizard (bounded retry).' >/dev/console
    db_capb backup align
    sleep 1
done
trap - HUP INT TERM
exec 6<&-
# CAPB is shared with partman; never leave escape enabled for unrelated callers.
db_capb backup align
db_fset partman-crypto/passphrase seen true
db_fset partman-crypto/passphrase-again seen true
mode=bios
[ ! -d /sys/firmware/efi ] || mode=efi
[ -x /debian-crypto-recipe.sh ] || exit 1
recipe=$(sh /debian-crypto-recipe.sh "$mode") || exit 1
[ -n "$recipe" ] || exit 1
case "$recipe" in 'reinstall-crypto :'*) ;; *) exit 1;; esac
case "$recipe" in *swap*) exit 1;; esac
printf '%s\n' "$recipe" >/run/reinstall-crypto.recipe
# The live trixie parser is present before partman/early_command.
set +u
. /lib/partman/lib/base.sh
. /lib/partman/lib/recipes.sh
decode_recipe /run/reinstall-crypto.recipe lvm ''
[ "$name" = reinstall-crypto ] || exit 1
case "$scheme" in *'mountpoint{ / }'*) ;; *) exit 1;; esac
[ "$(min_size)" -le 7000 ] || exit 1
db_set partman-auto/expert_recipe ''
db_set partman-auto/expert_recipe_file /run/reinstall-crypto.recipe
db_set partman-auto/choose_recipe reinstall-crypto
db_get pkgsel/include
case " $RET " in
    *' cryptsetup-initramfs '*) ;;
    *) db_set pkgsel/include "${RET:+$RET }cryptsetup-initramfs lvm2 python3";;
esac
db_set partman-auto/method crypto
db_set partman-auto-lvm/guided_size max
db_set partman-auto-crypto/erase_disks false
db_set partman-lvm/confirm true
db_set partman-lvm/confirm_nooverwrite true
# No password value is printed or written to preseed. Partman consumes the DB.
