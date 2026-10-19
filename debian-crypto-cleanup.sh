#!/bin/sh
# Run after partman/base installation, before installer logs reach the target.
PATH=/usr/local/lib/reinstall/applets:$PATH
export PATH
set +x
set -eu
[ -f /reinstall-crypto-enabled ] || exit 0
[ -z "${DEBCONF_DEBUG-}${DEBCONF_DEBUGFILE-}" ] || exit 1
for path in /var/lib/partman /var/lib/cdebconf; do
    case "$(stat -f -c %T "$path")" in tmpfs|ramfs) ;; *) exit 1;; esac
done
# partman-crypto 134 stores the generated keyfile path in this metadata.
# crypttab has already recorded 'none' for passphrase-backed encrypted volumes.
for metadata in /var/lib/partman/devices/*/*/keyfile; do
    [ -f "$metadata" ] || continue
    IFS= read -r key < "$metadata"
    case "$key" in
        /var/lib/partman/devices/*)
            resolved=$(readlink -f "$key")
            case "$resolved" in /var/lib/partman/devices/*) ;; *) exit 1;; esac
            [ ! -L "$key" ] || exit 1
            rm -f "$key" "$metadata"
            ;;
        *) exit 1;;
    esac
done
unset key resolved
. /usr/share/debconf/confmodule
db_set partman-crypto/passphrase ''
db_set partman-crypto/passphrase-again ''
# Standard cdebconf API; second save rotates a clean passwords.dat-old too.
db_x_save
db_x_save
