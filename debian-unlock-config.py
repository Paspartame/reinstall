#!/usr/bin/env python3
"""Internal target config generator. Reads initrd-network.sh facts, not the host.
Stage 6A only: not connected to the production --encrypt entry point.
"""
import base64
import ipaddress
import pathlib
import re
import shlex
import sys


def generate(target, keys, net, port=2222):
    target, keys, net = map(pathlib.Path, (target, keys, net))
    if target.resolve() == pathlib.Path('/'):
        raise ValueError('Refusing host root')
    if not 1 <= port <= 65535:
        raise ValueError('Invalid unlock port')
    def fact(name):
        return (net / name).read_text().strip()
    mac = fact('mac_addr')
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac):
        raise ValueError('Invalid MAC')
    if fact('ipv4_has_internet') != '1':
        raise ValueError('IPv6-only remote unlock is not verified')
    dhcp, disabled = fact('dhcpv4'), fact('should_disable_dhcpv4')
    if dhcp not in ('0', '1') or disabled not in ('0', '1'):
        raise ValueError('Invalid DHCP facts')
    address, gateway = fact('ipv4_addr'), fact('ipv4_gateway')
    dhcp = '1' if dhcp == '1' and disabled == '0' else '0'
    if address:
        ipaddress.IPv4Interface(address)
    if gateway:
        ipaddress.IPv4Address(gateway)
    if dhcp == '0' and not (address and gateway):
        raise ValueError('Static IPv4 requires address/prefix and gateway')
    lines = []
    for line in keys.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        fields = line.split()
        if len(fields) < 2 or fields[0] not in ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521'):
            raise ValueError('Only plain supported public keys are accepted')
        blob = base64.b64decode(fields[1], validate=True)
        size = int.from_bytes(blob[:4], 'big')
        if blob[4:4+size].decode() != fields[0] or len(blob) <= 4+size:
            raise ValueError('Invalid SSH public key blob')
        lines.append('no-agent-forwarding,no-port-forwarding,no-X11-forwarding,command="/bin/cryptroot-unlock" ' + ' '.join(fields[:2]))
    if not lines:
        raise ValueError('At least one public key is required')
    outputs = {
        'etc/dropbear/initramfs/authorized_keys': '\n'.join(lines)+'\n',
        'etc/dropbear/initramfs/dropbear.conf': f'DROPBEAR_OPTIONS="-p {port} -s -j -k"\n',
        'etc/reinstall-unlock/network.conf': ''.join(f'{k}={shlex.quote(v)}\n' for k,v in {'mac_addr':mac,'dhcpv4':dhcp,'ipv4_addr':address,'ipv4_gateway':gateway}.items()),
    }
    for name, text in outputs.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        path.chmod(0o600)


if __name__ == '__main__':
    try:
        generate(*sys.argv[1:4], int(sys.argv[4]) if len(sys.argv) == 5 else 2222)
    except (ValueError, OSError, TypeError) as exc:
        sys.exit(str(exc))
