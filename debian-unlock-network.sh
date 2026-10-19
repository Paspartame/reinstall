#!/bin/sh
# Internal initramfs early IPv4; uses installer facts, never probes host config.
# shellcheck disable=SC2154,SC2034
# Config assigns network facts; library consumes the opt-in flag.
set -eu
case "${1-}" in prereqs) echo udev; exit 0;; esac
# Failure must block Dropbear, not fall back to unrelated DHCP interfaces.
trap 'touch /run/reinstall-unlock-network-failed' EXIT
. /etc/reinstall-unlock/network.conf
set -- "$mac_addr" "$ipv4_addr" "$ipv4_gateway" '' '' false ''
REINSTALL_NETWORK_LIBRARY_ONLY=1
. /lib/reinstall-initrd-network.sh
ethx=''
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    ethx=$(get_ethx) && break
    sleep 1
done
[ -n "$ethx" ] || exit 1
ip link set dev lo up
ip link set dev "$ethx" up
if [ "$dhcpv4" = 1 ]; then
    # klibc DHCP may time out even where normal Debian DHCP succeeds.
    # Stored facts are validated by the installer and MAC-bound above.
    ipconfig -t 30 -c dhcp -d "$ethx" || true
fi
if ! is_have_ipv4; then
    [ -n "$ipv4_addr" ] && [ -n "$ipv4_gateway" ] || exit 1
    # Preserve a complete DHCP lease; otherwise use the recorded complete pair.
    ip -4 addr flush scope global dev "$ethx"
    ip -4 route flush dev "$ethx"
    add_missing_ipv4_config
fi
is_have_ipv4 || exit 1
# Standard configure_networking detects this and avoids a second DHCP attempt.
printf 'DEVICE=%s\n' "$ethx" >"/run/net-$ethx.conf"
printf 'DEVICE=%s\n' "$ethx" >>/conf/param.conf
rm -f /run/reinstall-unlock-network-failed
trap - EXIT
