#!/usr/bin/env python3
"""Offline CLI builder contract using public fixture inputs and disposable roots."""
import pathlib, subprocess, tempfile
repo=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='s64-crypto-test-') as td:
    td=pathlib.Path(td); private=td/'key'; subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(private)],check=True); key=td/'key.pub'
    root=td/'initrd'; root.mkdir()
    cmd=['python3',str(repo/'debian-crypto-build.py'),'--repo',str(repo),'--initrd-root',str(root),'--ssh-key',str(key)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    expected=['reinstall-crypto-enabled','etc/reinstall-crypto/partman-recipe-bios','etc/reinstall-crypto/partman-recipe-efi','usr/local/sbin/debian-unlock-install.sh','usr/local/lib/reinstall/debian-unlock-hook.sh','usr/local/lib/reinstall/debian-unlock-network.sh','usr/local/sbin/reinstall-luks-passphrase','usr/local/sbin/reinstall-luks-receiver','debian-crypto-gate.sh','debian-crypto-cleanup.sh']
    assert all((root/x).is_file() for x in expected)
    assert (root/'etc/dropbear/initramfs/authorized_keys').is_file()
    assert 'ssh-ed25519' in (root/'etc/dropbear/initramfs/authorized_keys').read_text()
    assert (root/'reinstall-crypto-enabled').read_text()=='opt-in\n'
    assert (root/'preseed.cfg').is_file()
    assert all((root/'usr/local/lib/reinstall'/name).is_file() for name in ('preseed-early.sh','preseed-late.sh','partman-early.sh'))
    assert not (root/'actualdebian.cfg').exists(), 'one canonical initrd preseed only'
    assert (root/'preseed.cfg').read_bytes()==(repo/'debian.cfg').read_bytes()
    print('PASS: initrd builder stages required recipes, public-key data, helpers, scripts, and marker')
    broken=td/'broken'; broken.mkdir()
    bad=td/'bad.pub'; bad.write_text('not a valid public key\n')
    badcmd=['python3',str(repo/'debian-crypto-build.py'),'--repo',str(repo),'--initrd-root',str(broken),'--ssh-key',str(bad)]
    r=subprocess.run(badcmd,capture_output=True,text=True)
    assert r.returncode!=0 and not list(broken.iterdir()), 'invalid key must fail before publishing'
    print('PASS: invalid key fails before publishing any file')
