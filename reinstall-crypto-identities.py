#!/usr/bin/env python3
"""Public identity presentation and on-target final initramfs verification."""
import argparse,base64,hashlib,pathlib,re,subprocess,tempfile,shutil,struct,ipaddress,sys

def public(line):
    if '\n' in line.strip() or '\r' in line.strip(): raise ValueError('Multiline public identity refused')
    fields=line.strip().split()
    if len(fields)<2 or fields[0]!='ssh-ed25519': raise ValueError('Ed25519 public key required')
    raw=base64.b64decode(fields[1],validate=True)
    if len(raw)!=51 or raw[:19]!=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32):
        raise ValueError('Malformed Ed25519 wire key')
    return 'ssh-ed25519 '+fields[1], 'SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')

def label(value):
    try:return str(ipaddress.ip_address(value))
    except ValueError:pass
    if re.fullmatch(r'[0-9.]+',value) or ':' in value:raise ValueError('Invalid IP literal')
    if len(value)>253 or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',value):raise ValueError('Invalid DNS/IP label')
    if any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',x) for x in value.rstrip('.').split('.')):raise ValueError('Invalid DNS label')
    return value.lower()

def choose_host(explicit=None):
    saved=pathlib.Path('/etc/reinstall-unlock/connection-label')
    suggestion=explicit or (saved.read_text().strip() if saved.exists() else '')
    if not suggestion:
        try:
            import json
            for iface in json.loads(run('ip','-j','-4','addr','show')):
                for item in iface.get('addr_info',[]):
                    ip=ipaddress.ip_address(item['local'])
                    if ip.is_global:suggestion=str(ip);break
                if suggestion:break
        except Exception:pass
    if not explicit and sys.stdin.isatty() and sys.stdout.isatty():
        answer=input('SSH connection address (DNS or IP) ['+suggestion+']: ').strip()
        suggestion=answer or suggestion
    if not suggestion:raise ValueError('No public address known; reconnect with PTY and enter actual SSH address')
    host=label(suggestion)
    saved.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    saved.write_text(host+'\n')
    return host

def record(key,host,port):
    return (host if int(port)==22 else '['+host+']:'+str(port))+' '+public(key)[0]

def show(stage,key,host,port):
    if host!='REPLACE_WITH_YOUR_SSH_HOST' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]{0,252}',host):raise ValueError('Invalid host label')
    if not 1<=int(port)<=65535:raise ValueError('Invalid port')
    key,fp=public(key)
    binding=host if int(port)==22 else '['+host+']:'+str(port)
    print(f'[{stage}] {host}:{port}\n  Fingerprint: {fp}\n  Public key: {key}\n  known_hosts: {binding} {key}')
    if host=='REPLACE_WITH_YOUR_SSH_HOST':print('  TEMPLATE ONLY: replace with the actual host in your client; this is not a ready binding.')

def run(*args):return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
def boot_selection(kernel):
    # Narrow Debian BIOS contract: first generated entry, default zero, separate /boot.
    text=pathlib.Path('/boot/grub/grub.cfg').read_text()
    env=run('grub-editenv','/boot/grub/grubenv','list')
    if env.strip():raise ValueError('Nonempty GRUB environment may override next boot')
    defaults=re.findall(r'^\s*set default="([^"\n]+)"',text,re.M)
    if defaults!=['${next_entry}','0']:raise ValueError('Unsupported GRUB default selection')
    entries=re.split(r'^menuentry ',text,flags=re.M)
    if len(entries)<2:raise ValueError('Missing default GRUB entry')
    first=entries[1].split('\n}',1)[0]
    roots=re.findall(r'^\s*search --no-floppy --fs-uuid --set=root (\S+)\s*$',first,re.M)
    if roots!=[run('findmnt','-n','-o','UUID','/boot')]:raise ValueError('GRUB root filesystem does not match verified /boot')
    if re.search(r'^\s*set root=',first,re.M):raise ValueError('GRUB root override refused')
    linux=re.findall(r'^\s*linux\s+(\S+)',first,re.M)
    initrds=re.findall(r'^\s*initrd\s+([^\n]+)',first,re.M)
    if linux!=['/vmlinuz-'+kernel] or initrds!=['/initrd.img-'+kernel]:raise ValueError('GRUB kernel/initrd selection mismatch')
    if run('findmnt','-n','-o','TARGET,FSTYPE','/boot')!='/boot ext4':raise ValueError('Independent ext4 /boot required')
    k=pathlib.Path('/boot/vmlinuz-'+kernel)
    i=pathlib.Path('/boot/initrd.img-'+kernel)
    if not k.is_file() or not i.is_file() or k.is_symlink() or i.is_symlink():raise ValueError('Missing/indirect selected boot artifact')
    if not 0<i.stat().st_size<=192*1024*1024:raise ValueError('Final initrd size outside supported bound')
    return i,hashlib.sha256(text.encode()).hexdigest(),hashlib.sha256(k.read_bytes()).hexdigest()

def verify():
    # Actual configured OpenSSH key, not merely a potentially stale .pub file.
    cfg=run('/usr/sbin/sshd','-T').splitlines()
    paths=[x.split(' ',1)[1] for x in cfg if x.startswith('hostkey ')]
    keypath='/etc/ssh/ssh_host_ed25519_key'
    if keypath not in paths:raise ValueError('Configured OpenSSH Ed25519 identity missing')
    oskey=run('ssh-keygen','-y','-f',keypath)
    if public(oskey)[0]!=public(pathlib.Path(keypath+'.pub').read_text())[0]:raise ValueError('OpenSSH public/private mismatch')
    ports=[int(x.split()[1]) for x in cfg if x.startswith('port ')]
    if len(ports)!=1 or not 1<=ports[0]<=65535:raise ValueError('Ambiguous OpenSSH port')
    osport=ports[0]
    drop='/etc/dropbear/initramfs/dropbear_ed25519_host_key'
    output=run('dropbearkey','-y','-f',drop)
    keys=[x for x in output.splitlines() if x.startswith('ssh-ed25519 ')]
    if len(keys)!=1:raise ValueError('Unexpected Dropbear public output')
    dbkey=keys[0];public(dbkey)
    conf=pathlib.Path('/etc/dropbear/initramfs/dropbear.conf').read_text()
    match=re.search(r'(?:^|[\s\"\x27])-p\s+(\d+)',conf)
    if not match:raise ValueError('Dropbear port not established')
    matches=re.findall(r'(?:^|[\s\"\x27])-p\s+(\d+)',conf)
    if len(matches)!=1 or not 1<=int(matches[0])<=65535:raise ValueError('Ambiguous Dropbear port')
    port=int(matches[0]);host=choose_host(HOST_OVERRIDE)
    # Exactly one installed kernel expected in this supported installer flow.
    kernels=list(pathlib.Path('/lib/modules').iterdir())
    if len(kernels)!=1:raise ValueError('Ambiguous final kernel')
    ram=pathlib.Path('/run/reinstall-identity-ram')
    if run('stat','-f','-c','%T',str(ram))!='tmpfs':raise ValueError('Identity extraction must be tmpfs')
    initrd,grub_digest,kernel_digest=boot_selection(kernels[0].name)
    before=hashlib.sha256(initrd.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='identity-',dir=str(ram)) as td:
        subprocess.run(['unmkinitramfs','/boot/initrd.img-'+kernels[0].name,td+'/tree'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        tree=pathlib.Path(td)/'tree';tree=tree/'main' if (tree/'main').is_dir() else tree
        for a,b in [(pathlib.Path(drop),tree/'etc/dropbear/dropbear_ed25519_host_key'),(pathlib.Path('/usr/local/lib/reinstall/debian-unlock-network.sh'),tree/'scripts/init-premount/reinstall-unlock-network'),(pathlib.Path('/etc/reinstall-unlock/network.conf'),tree/'etc/reinstall-unlock/network.conf'),(pathlib.Path('/etc/dropbear/initramfs/dropbear.conf'),tree/'etc/dropbear/dropbear.conf')]:
            if a.read_bytes()!=b.read_bytes():raise ValueError('Final initrd payload/identity mismatch')
    after=hashlib.sha256(initrd.read_bytes()).hexdigest()
    if before!=after:raise ValueError('Final initrd changed during verification')
    if boot_selection(kernels[0].name)!=(initrd,grub_digest,kernel_digest):raise ValueError('Selected boot configuration changed during verification')
    print('Selected GRUB kernel/initrd: /boot/vmlinuz-'+kernels[0].name+' '+str(initrd))
    print('Verified GRUB SHA256: '+grub_digest+' kernel SHA256: '+kernel_digest)
    print('Verified final initrd SHA256: '+after)
    show('DROPBEAR INITRAMFS SSH',dbkey,host,port)
    show('INSTALLED DEBIAN SSH',oskey,host,osport)
    if port==osport:
        print('COLLISION: sequential identities at same host:port; use separate stage trust files/aliases, NOT a combined trust set.')
    else:
        print('BEGIN COPY (Dropbear, then Debian)')
        print(record(dbkey,host,port))
        print(record(oskey,host,osport))
        print('END COPY')
    print('Retire the separately verified Installer identity when transitioning to Debian; never blindly accept changed keys.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify-target',action='store_true');p.add_argument('--public-file');p.add_argument('--port',type=int,default=22);p.add_argument('--host');a=p.parse_args();HOST_OVERRIDE=a.host
    try:
        if a.verify_target:verify()
        else:show('INSTALLER SSH',pathlib.Path(a.public_file).read_text(),choose_host(a.host),a.port)
    except Exception as e:p.exit(1,'Identity verification failed: '+str(e)+'\n')
