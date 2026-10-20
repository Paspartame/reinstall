#!/usr/bin/env python3
"""Validate and stage crypto initrd payload in a temporary initrd root; never boots or touches disks."""
import argparse
import pathlib
import shutil
import subprocess
import tempfile
import os

FILES = {
    'reinstall-crypto-wizard': 'usr/local/sbin/reinstall-crypto-wizard',
    'reinstall-crypto-identities.py': 'usr/local/lib/reinstall/reinstall-crypto-identities.py',
    'debian-unlock-config.py': 'debian-unlock-config.py',
    'debian-crypto-recipe.sh': 'debian-crypto-recipe.sh',
    'debian-crypto-gate.sh': 'debian-crypto-gate.sh',
    'debian-crypto-cleanup.sh': 'debian-crypto-cleanup.sh',
    'reinstall-luks-passphrase': 'usr/local/sbin/reinstall-luks-passphrase',
    'debian-unlock-hook.sh': 'usr/local/lib/reinstall/debian-unlock-hook.sh',
    'debian-unlock-network.sh': 'usr/local/lib/reinstall/debian-unlock-network.sh',
    'initrd-network.sh': 'usr/local/lib/reinstall/initrd-network.sh',
    'debian-unlock-install.sh': 'usr/local/sbin/debian-unlock-install.sh',
}

def build(repo, root, facts, keys, port=2222, busybox=None):
    repo, root, keys = map(pathlib.Path, (repo, root, keys))
    if not keys.is_file():
        raise ValueError('SSH public key file is required')
    if not root.is_dir() or root.resolve() == pathlib.Path('/'):
        raise ValueError('initrd root must be an existing non-root directory')
    if not 1 <= int(port) <= 65535:
        raise ValueError('invalid port')
    # Validate every dependency and generated config before touching the destination.
    recipe_bios = subprocess.run(['sh', str(repo/'debian-crypto-recipe.sh'), 'bios'], check=True, text=True, capture_output=True).stdout
    recipe_efi = subprocess.run(['sh', str(repo/'debian-crypto-recipe.sh'), 'efi'], check=True, text=True, capture_output=True).stdout
    for src in FILES:
        if not (repo/src).is_file():
            raise ValueError('required payload absent: '+src)
    # Stock Debian Installer BusyBox lacks stat/mkfifo. Reuse its own BusyBox
    # image via applet symlinks in the extracted initrd, never host ELF files.
    # This builder is also unit-tested against an empty disposable root; the
    # composition caller performs the actual installer BusyBox compatibility check.
    import importlib.util
    spec=importlib.util.spec_from_file_location('crypto_runtime',repo/'debian-crypto-runtime.py')
    runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    busybox=runtime.resolve(busybox)
    if busybox is not None:
        if not busybox.is_file(): raise ValueError('static BusyBox path is not a file')
        applets = subprocess.run([str(busybox),'--list'],check=True,text=True,capture_output=True).stdout.split()
        required = ('stat','base64','mkfifo','awk')
        missing = [name for name in required if name not in applets]
        if missing: raise ValueError('static BusyBox applets absent: '+', '.join(missing))
    with tempfile.TemporaryDirectory(prefix='crypto-build-') as td:
        stage = pathlib.Path(td)/'stage'; stage.mkdir()
        # Preserve canonical upstream preseed bytes at the auto-loaded root path.
        shutil.copyfile(repo/'debian.cfg', stage/'preseed.cfg')
        (stage/'preseed.cfg').chmod(0o644)
        helper_dir=stage/'usr/local/lib/reinstall'
        helper_dir.mkdir(parents=True,exist_ok=True)
        for helper in ('preseed-early.sh','preseed-late.sh','partman-early.sh'):
            if not (repo / helper).is_file(): raise ValueError('required preseed helper absent: '+helper)
            shutil.copyfile(repo / helper, helper_dir / helper)
            (helper_dir/helper).chmod(0o755)
        # Validate key syntax using temporary schema facts; no host network data
        # is copied. Live installer facts are rewritten from /dev/netconf later.
        key_copy=pathlib.Path(td)/'key.pub'; shutil.copyfile(keys,key_copy)
        if not key_copy.read_text().strip().startswith(('ssh-ed25519 ','ssh-rsa ','ecdsa-sha2-nistp')):
            raise ValueError('unsupported SSH public key format')
        facts_dir=pathlib.Path(td)/'facts'; facts_dir.mkdir()
        for n,v in {'mac_addr':'02:00:00:00:00:01','ipv4_has_internet':'1','dhcpv4':'1','should_disable_dhcpv4':'0','ipv4_addr':'192.0.2.2/24','ipv4_gateway':'192.0.2.1','ipv4_dns':'192.0.2.53'}.items(): (facts_dir/n).write_text(v+'\n')
        generated=pathlib.Path(td)/'validate'
        subprocess.run(['python3',str(repo/'debian-unlock-config.py'),str(generated),str(key_copy),str(facts_dir),str(port)],check=True)
        for src,dest in FILES.items():
            out=stage/dest; out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(repo/src,out); out.chmod(0o755)
        receiver=stage/'usr/local/sbin/reinstall-luks-receiver'
        shutil.copyfile(stage/'usr/local/sbin/reinstall-luks-passphrase',receiver); receiver.chmod(0o755)
        generated_crypto=generated
        for path in generated_crypto.rglob('*'):
            if path.is_file():
                dst=stage/path.relative_to(generated); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dst); dst.chmod(0o600)
        recipes=stage/'etc/reinstall-crypto'; recipes.mkdir(parents=True,exist_ok=True)
        (recipes/'partman-recipe-bios').write_text(recipe_bios)
        (recipes/'partman-recipe-efi').write_text(recipe_efi)
        if busybox is not None:
            staged_busybox=stage/'usr/local/lib/reinstall/busybox'; staged_busybox.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(busybox,staged_busybox); staged_busybox.chmod(0o755)
            applet_dir=stage/'usr/local/lib/reinstall/applets'; applet_dir.mkdir(parents=True,exist_ok=True)
            for utility in ('stat','base64','mkfifo','awk'):
                (applet_dir/utility).symlink_to('../busybox')
        # Publish staged payload while permitting replacement of the two canonical preseed names and helpers.
        backups = stage/'private-backups'
        backups.mkdir(mode=0o700)
        created = []
        replaced = []
        try:
            for p in list(stage.rglob('*')):
                if backups in p.parents:continue
                if not p.is_file():
                    continue
                out = root/p.relative_to(stage)
                if out.exists() or out.is_symlink():
                    if out.relative_to(root).as_posix() not in ('actualdebian.cfg', 'preseed.cfg', 'debian-crypto-cleanup.sh', 'debian-crypto-gate.sh', 'debian-crypto-recipe.sh', 'usr/local/sbin/reinstall-luks-receiver', 'usr/local/sbin/reinstall-luks-passphrase', 'usr/local/sbin/debian-unlock-install.sh', 'usr/local/lib/reinstall/preseed-early.sh', 'usr/local/lib/reinstall/preseed-late.sh', 'usr/local/lib/reinstall/partman-early.sh', 'usr/local/lib/reinstall/busybox', 'usr/local/lib/reinstall/debian-unlock-network.sh', 'usr/local/lib/reinstall/debian-unlock-hook.sh', 'usr/local/lib/reinstall/initrd-network.sh', 'usr/local/lib/reinstall/applets/awk', 'usr/local/lib/reinstall/applets/base64', 'usr/local/lib/reinstall/applets/mkfifo', 'usr/local/lib/reinstall/applets/stat', 'etc/reinstall-unlock/network.conf', 'etc/reinstall-unlock/authorized_keys', 'etc/reinstall-crypto/partman-recipe-bios', 'etc/reinstall-crypto/partman-recipe-efi', 'etc/dropbear/initramfs/dropbear.conf', 'etc/dropbear/initramfs/authorized_keys'):
                        raise ValueError('refusing to overwrite initrd path: '+str(out.relative_to(root)))
                    if out.is_symlink():raise ValueError('refusing symlink replacement')
                    fd,name=tempfile.mkstemp(prefix='file-',dir=backups);os.close(fd)
                    backup=pathlib.Path(name)
                    shutil.copy2(out,backup); replaced.append((out,backup))
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, out); out.chmod(p.stat().st_mode & 0o777)
                created.append(out)
            marker = root/'reinstall-crypto-enabled'
            if marker.exists() or marker.is_symlink():
                if marker.is_symlink() or not marker.is_file():
                    raise ValueError('refusing non-regular opt-in marker')
                fd,name=tempfile.mkstemp(prefix='marker-',dir=backups);os.close(fd)
                marker_backup=pathlib.Path(name)
                shutil.copyfile(marker,marker_backup); replaced.append((marker,marker_backup))
            marker.write_text('opt-in\n'); marker.chmod(0o600)
            created.append(marker)
        except Exception:
            for out in reversed(created):
                out.unlink(missing_ok=True)
            for out,backup in replaced:
                shutil.copy2(backup,out); backup.unlink(missing_ok=True)
            raise
    return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True); p.add_argument('--initrd-root',required=True)
    p.add_argument('--ssh-key',required=True); p.add_argument('--port',type=int,default=2222); p.add_argument('--static-busybox')
    a=p.parse_args()
    try: print('\n'.join(build(a.repo,a.initrd_root,None,a.ssh_key,a.port,a.static_busybox)))
    except (ValueError,OSError,subprocess.CalledProcessError) as e: p.exit(1,f'crypto staging failed: {e}\n')
