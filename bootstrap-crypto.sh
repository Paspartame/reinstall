#!/bin/bash
# Experimental one-command START, not unattended installation.
set -euo pipefail
fail() { printf 'Bootstrap refused: %s\n' "$*" >&2; exit 1; }
revision= key= port=2222 confirm=0
while (($#)); do
    case "$1" in
        --revision) (($#>=2)) || fail 'missing revision'; revision=$2; shift 2 ;;
        --ssh-key) (($#>=2)) || fail 'missing public key'; key=$2; shift 2 ;;
        --unlock-port) (($#>=2)) || fail 'missing port'; port=$2; shift 2 ;;
        --confirm-erase) confirm=1; shift ;;
        *) fail "unknown option: $1" ;;
    esac
done
[[ $revision =~ ^[0-9a-f]{40}$ ]] || fail '--revision must be a full immutable Git SHA'
[[ -n $key && $key != http://* ]] || fail '--ssh-key requires a public key, file, github:USER or HTTPS URL'
[[ $port =~ ^[0-9]+$ && ${#port} -le 5 ]] || fail 'invalid port'
((10#$port>=1 && 10#$port<=65535)) || fail 'invalid port'
if [[ -f $key ]]; then key=$(readlink -f -- "$key"); fi
((EUID==0)) || fail 'root shell required'
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || fail 'only Debian 13 starting OS is supported'
[[ $(uname -m) == x86_64 ]] || fail 'amd64 required'
[[ ! -d /sys/firmware/efi ]] || fail 'UEFI unsupported'
command -v apt-get >/dev/null || fail 'signed Debian APT required'
command -v ip >/dev/null || fail 'iproute2 required on starting OS'
ip -4 route show default | grep -q . || fail 'IPv4 default route required'
[[ -s /boot/grub/grub.cfg ]] || fail 'existing BIOS GRUB required'
# A device-mapper root may be encrypted. Do not stage on unreadable root.
if [[ $(findmnt -n -o SOURCE /) == /dev/mapper/* ]]; then
    mountpoint -q /boot || fail 'mapper root requires a separate unencrypted /boot'
    [[ $(findmnt -n -o FSTYPE /boot) == ext4 ]] || fail '/boot must be ext4'
fi
printf 'EXPERIMENTAL Debian13/amd64/BIOS/IPv4; target disks WILL BE ERASED.\nRevision: %s\n' "$revision"
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
if ((confirm==0)); then
    [[ -r /dev/tty && -w /dev/tty ]] || fail 'TTY required, or explicitly select --confirm-erase'
    printf 'Type ERASE to prepare destructive reinstall: ' >/dev/tty
    IFS= read -r answer </dev/tty || fail 'confirmation unavailable'
    [[ $answer == ERASE ]] || fail 'not confirmed'
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends git ca-certificates python3 busybox-static openssh-client curl cpio gzip xz-utils
umask 077
work=$(mktemp -d /var/tmp/reinstall-crypto.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
# Single immutable tree, verified by real Git; HTTPS certificate checking stays on.
git -c credential.helper= clone --no-checkout https://github.com/Paspartame/reinstall.git "$work/source"
git -C "$work/source" checkout --detach "$revision"
[[ $(git -C "$work/source" rev-parse HEAD) == "$revision" ]] || fail 'revision mismatch'
# Prevent mixing a downloaded bootstrap with another version of itself.
cmp -- "${BASH_SOURCE[0]}" "$work/source/bootstrap-crypto.sh" || fail 'bootstrap and chosen revision differ'
cd "$work/source"
for f in reinstall.sh debian.cfg debian-crypto-build.py debian-crypto-runtime.py debian-unlock-network.sh preseed-early.sh preseed-late.sh reinstall-luks-passphrase reinstall-luks-receiver; do
    [[ -s $f ]] || fail "adjacent helper missing: $f"
done
python3 debian-crypto-runtime.py >/dev/null
# Reuse the production resolver/validator, including github:USER and HTTPS keys.
# No passphrase is accepted by bootstrap or passed as argv/environment.
bash reinstall.sh debian 13 --installer --encrypt --ssh-key "$key" --unlock-port "$port" --username root
printf '\nPREPARED, not installed. Record the Installer PUBLIC identity printed above BEFORE reboot.\n'
printf 'Pin Installer SSH port22 on an independent controller, then reboot this target when ready.\n'
printf 'Use pinned ssh -tt to run /usr/local/sbin/reinstall-luks-passphrase; enter/confirm a NEW secret.\n'
printf 'At /run/reinstall-identity-ready collect target OS22 and Dropbear public keys, verify final initrd, pin separately.\n'
printf 'Only then touch /run/reinstall-identity-continue; unlock each boot over pinned SSH2222 with PTY.\n'
printf 'Full handoff/recovery guide: https://github.com/Paspartame/reinstall/blob/%s/DEBIAN-ENCRYPTION.md\n' "$revision"
