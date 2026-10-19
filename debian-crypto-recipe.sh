#!/bin/sh
# Internal-only recipe generator, based on trixie partman-auto 177.
# No disk operations. The production --encrypt entry point remains disabled.
set -eu
[ "$#" = 1 ] || exit 2
case "$1" in
    efi)
        printf '%s\n' 'reinstall-crypto :' \
            '106 1 106 free $iflabel{ gpt } $reusemethod{ } method{ efi } format{ } .'
        ;;
    bios)
        printf '%s\n' 'reinstall-crypto :' \
            '1 1 1 free $iflabel{ gpt } method{ biosgrub } .'
        ;;
    *) exit 2;;
esac
# auto_lvm_prepare handles the enclosing crypto PV. Do not invent a nested
# crypto stanza: $lvmok marks logical volumes, $defaultignore keeps /boot out.
printf '%s\n' \
    '768 768 768 ext4 $defaultignore{ } method{ format } format{ } use_filesystem{ } filesystem{ ext4 } mountpoint{ /boot } .' \
    '1024 10000 -1 ext4 $lvmok{ } method{ format } format{ } use_filesystem{ } filesystem{ ext4 } mountpoint{ / } .'
