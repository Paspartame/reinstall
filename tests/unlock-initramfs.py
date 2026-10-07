#!/usr/bin/env python3
"""Inspect two real unpacked initramfs builds; no private key output."""
import pathlib,sys
first,second=map(pathlib.Path,sys.argv[1:])
for root in (first,second):
    for path in ['usr/sbin/dropbear','usr/bin/cryptroot-unlock','scripts/local-top/cryptroot','scripts/init-bottom/dropbear','etc/reinstall-unlock/network.conf','usr/lib/reinstall-initrd-network.sh']:
        assert (root/path).is_file(),path
    assert list(root.rglob('virtio_net.ko*'))
    keys=list(root.glob('root-*/.ssh/authorized_keys')); assert len(keys)==1
    auth=keys[0].read_text()
    assert 'command="/bin/cryptroot-unlock"' in auth
    assert 'no-agent-forwarding,no-port-forwarding,no-X11-forwarding' in auth
    assert 'no-pty' not in auth
    order=(root/'scripts/init-premount/ORDER').read_text()
    assert order.index('/reinstall-unlock-network') < order.index('/dropbear')
    assert '-p 2222 -s -j -k' in (root/'etc/dropbear/dropbear.conf').read_text()
    assert not list(root.rglob('ssh_host_*_key'))
    for p in root.rglob('*'):
        if p.is_file() and not p.is_symlink():
            assert b'REINSTALL_LUKS_CANARY_' not in p.read_bytes(),str(p)
a={p.name:p.read_bytes() for p in (first/'etc/dropbear').glob('*host_key')}
b={p.name:p.read_bytes() for p in (second/'etc/dropbear').glob('*host_key')}
assert a and a==b
print('PASS unpacked content, forced-command/TTY, NIC, hook order, key stability, no OpenSSH private key or LUKS canary')
