#!/usr/bin/env python3
"""Public identity presentation and on-target final initramfs verification."""
import argparse,base64,hashlib,pathlib,re,subprocess,tempfile,shutil,struct

def public(line):
    if '\n' in line.strip() or '\r' in line.strip(): raise ValueError('Multiline public identity refused')
    fields=line.strip().split()
    if len(fields)<2 or fields[0]!='ssh-ed25519': raise ValueError('Ed25519 public key required')
    raw=base64.b64decode(fields[1],validate=True)
    if len(raw)!=51 or raw[:19]!=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32):
        raise ValueError('Malformed Ed25519 wire key')
    return 'ssh-ed25519 '+fields[1], 'SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')

def show(stage,key,host,port):
    if host!='REPLACE_WITH_YOUR_SSH_HOST' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]{0,252}',host):raise ValueError('Invalid host label')
    if not 1<=int(port)<=65535:raise ValueError('Invalid port')
    key,fp=public(key)
    binding=host if int(port)==22 else '['+host+']:'+str(port)
    print(f'[{stage}] {host}:{port}\n  Fingerprint: {fp}\n  Public key: {key}\n  known_hosts: {binding} {key}')
    if host=='REPLACE_WITH_YOUR_SSH_HOST':print('  TEMPLATE ONLY: replace with the actual host in your client; this is not a ready binding.')

def run(*args):return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
def verify():
    # Actual configured OpenSSH key, not merely a potentially stale .pub file.
    cfg=run('/usr/sbin/sshd','-T').splitlines()
    paths=[x.split(' ',1)[1] for x in cfg if x.startswith('hostkey ')]
    keypath='/etc/ssh/ssh_host_ed25519_key'
    if keypath not in paths:raise ValueError('Configured OpenSSH Ed25519 identity missing')
    oskey=run('ssh-keygen','-y','-f',keypath)
    if public(oskey)[0]!=public(pathlib.Path(keypath+'.pub').read_text())[0]:raise ValueError('OpenSSH public/private mismatch')
    osport=int(next(x.split()[1] for x in cfg if x.startswith('port ')))
    drop='/etc/dropbear/initramfs/dropbear_ed25519_host_key'
    output=run('dropbearkey','-y','-f',drop)
    keys=[x for x in output.splitlines() if x.startswith('ssh-ed25519 ')]
    if len(keys)!=1:raise ValueError('Unexpected Dropbear public output')
    dbkey=keys[0];public(dbkey)
    conf=pathlib.Path('/etc/dropbear/initramfs/dropbear.conf').read_text()
    match=re.search(r'(?:^|[\s\"\x27])-p\s+(\d+)',conf)
    if not match:raise ValueError('Dropbear port not established')
    port=int(match[1]);host='REPLACE_WITH_YOUR_SSH_HOST'
    # Exactly one installed kernel expected in this supported installer flow.
    kernels=list(pathlib.Path('/lib/modules').iterdir())
    if len(kernels)!=1:raise ValueError('Ambiguous final kernel')
    ram=pathlib.Path('/run/reinstall-identity-ram')
    if run('stat','-f','-c','%T',str(ram))!='tmpfs':raise ValueError('Identity extraction must be tmpfs')
    with tempfile.TemporaryDirectory(prefix='identity-',dir=str(ram)) as td:
        subprocess.run(['unmkinitramfs','/boot/initrd.img-'+kernels[0].name,td+'/tree'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        tree=pathlib.Path(td)/'tree';tree=tree/'main' if (tree/'main').is_dir() else tree
        for a,b in [(pathlib.Path(drop),tree/'etc/dropbear/dropbear_ed25519_host_key'),(pathlib.Path('/usr/local/lib/reinstall/debian-unlock-network.sh'),tree/'scripts/init-premount/reinstall-unlock-network'),(pathlib.Path('/etc/reinstall-unlock/network.conf'),tree/'etc/reinstall-unlock/network.conf')]:
            if a.read_bytes()!=b.read_bytes():raise ValueError('Final initrd payload/identity mismatch')
    show('DROPBEAR INITRAMFS SSH',dbkey,host,port)
    show('INSTALLED DEBIAN SSH',oskey,host,osport)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify-target',action='store_true');p.add_argument('--public-file');p.add_argument('--port',type=int,default=22);a=p.parse_args()
    try:
        if a.verify_target:verify()
        else:show('INSTALLER SSH',pathlib.Path(a.public_file).read_text(),'REPLACE_WITH_YOUR_SSH_HOST',a.port)
    except Exception as e:p.exit(1,'Identity verification failed: '+str(e)+'\n')
