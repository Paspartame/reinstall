#!/usr/bin/env python3
"""Run official unpacked d-i cdebconf under PRoot, never mock its backend.
Args: initrd root, proot, static busybox. Host swap is NOT disabled: an explicit
proc/swaps fixture is bound only inside this emulation. This is not a VM boot.
"""
import os, sys, pathlib, tempfile, subprocess, shutil, time, pty, select, signal, secrets
repo=pathlib.Path(__file__).resolve().parents[1]
image,proot,bb=map(lambda x:pathlib.Path(x).resolve(),sys.argv[1:4])
count=0

def check(v,label):
    global count
    if not v: raise AssertionError(label)
    count+=1;print('PASS '+label)

def wait(fn):
    end=time.monotonic()+15
    while not fn():
        if time.monotonic()>end: raise AssertionError('state timeout')
        time.sleep(.02)

with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='di-handoff-') as td:
    ram=pathlib.Path(td)
    for n in ['run','db','log','tmp','bin']: (ram/n).mkdir()
    (ram/'swaps').write_text('Filename Type Size Used Priority\n')
    for n in ['templates.dat','questions.dat']:
        source=image/'var/lib/cdebconf'/n
        if source.exists():shutil.copyfile(source,ram/'db'/n)
        else:(ram/'db'/n).touch()
    shutil.copyfile(repo/'reinstall-luks-passphrase',ram/'bin/reinstall-luks-passphrase')
    (ram/'bin/reinstall-luks-passphrase').chmod(0o755)
    (ram/'bin/reinstall-luks-receiver').symlink_to('reinstall-luks-passphrase')
    # d-i's reduced busybox lacks stat/base64; supply official Debian busybox.
    shutil.copyfile(bb,ram/'bin/busybox');(ram/'bin/busybox').chmod(0o755)
    for n in ['stat','base64','stty','mkfifo']: (ram/'bin'/n).symlink_to('busybox')
    (ram/'templates').write_text('Template: partman-crypto/passphrase\nType: password\nDescription: Test\n\nTemplate: partman-crypto/passphrase-again\nType: password\nDescription: Test\n\n')
    base=[str(proot),'-0','-r',str(image),'-w','/','-b','/proc','-b','/dev']
    for source,target in [(ram/'run','/run'),(ram/'db','/var/lib/cdebconf'),(ram/'log','/var/log'),(ram/'tmp','/tmp'),(ram/'bin','/testbin'),(ram/'swaps','/proc/swaps'),(ram,'/test')]:
        base+=['-b',str(source)+':'+target]
    base+=['-b',str(bb)+':/testbin/busybox',
           '-b',str(repo/'reinstall-luks-passphrase')+':/testbin/reinstall-luks-passphrase']
    scenario=os.environ.get('HANDOFF_SCENARIO','success')
    if scenario!='success':
        cf=(image/'usr/share/debconf/confmodule').read_text()
        cf+='''
# Test-only fault injection; all non-fault commands use real cdebconf.
db_set() {
    if [ "$1" = partman-crypto/passphrase-again ] && [ -n "$2" ]; then
        return 10
    fi
    _db_cmd SET "$@"
}
'''
        if scenario=='disconnect':
            cf=cf[:cf.index('# Test-only')]+'''
db_set() {
    _db_cmd SET "$@" || return $?
    if [ "$1" = partman-crypto/passphrase ] && [ -n "$2" ]; then
        # Disconnect protocol FDs after the actual first SET response.
        exec 3>/dev/null 0</dev/null
    fi
}
'''
        (ram/'confmodule').write_text(cf)
        base+=['-b',str(ram/'confmodule')+':/usr/share/debconf/confmodule']
    env=dict(os.environ,PATH='/testbin:/usr/sbin:/usr/bin:/sbin:/bin',DEBIAN_FRONTEND='noninteractive')
    env.pop('DEBIAN_HAS_FRONTEND',None);env.pop('DEBCONF_REDIR',None)
    captures=[]
    def run(args):
        p=subprocess.run(base+args,env=env,capture_output=True,timeout=20)
        captures.extend([p.stdout,p.stderr]);check(p.returncode==0,'installer command');return p
    run(['/usr/lib/cdebconf/debconf-loadtemplate','partman-crypto','/test/templates'])
    (ram/'verify').write_text('''#!/bin/sh
set +x
. /usr/share/debconf/confmodule
db_get partman-crypto/passphrase
a=$RET
db_get partman-crypto/passphrase-again
[ "$a" = "$RET" ] && [ -n "$a" ] || exit 1
db_set partman-crypto/passphrase ''
db_set partman-crypto/passphrase-again ''
unset a RET
''')
    canary='REINSTALL_LUKS_CANARY_'+secrets.token_hex(16)
    # Launch directly WITHOUT a frontend: production re-execs official frontend.
    p=subprocess.Popen(base+['/bin/sh','-x','/testbin/reinstall-luks-receiver'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    ch=ram/'run/reinstall-luks'
    wait(lambda:(ch/'ready').exists() or p.poll() is not None)
    if p.poll() is not None:
        print(p.communicate());raise AssertionError('receiver startup')
    pid,fd=pty.fork()
    if pid==0: os.execvpe(base[0],base+['/bin/sh','-x','/testbin/reinstall-luks-passphrase'],env)
    out=b''
    for marker in [b'Enter LUKS passphrase: ',b'Confirm LUKS passphrase: ']:
        end=time.monotonic()+15
        while marker not in out:
            if time.monotonic()>end:raise AssertionError('PTY prompt timeout')
            if select.select([fd],[],[],.1)[0]:out+=os.read(fd,65536)
        os.write(fd,(canary+'\\quote\" $% 中文'+'\n').encode())
    status=None
    end=time.monotonic()+20
    while status is None:
        if select.select([fd],[],[],.05)[0]:
            try:out+=os.read(fd,65536)
            except OSError:pass
        got,s=os.waitpid(pid,os.WNOHANG)
        if got:status=s
        if time.monotonic()>end:raise AssertionError('helper timeout')
    os.close(fd);captures.append(out)
    stdout,stderr=p.communicate(timeout=20);captures.extend([stdout,stderr])
    check((os.waitstatus_to_exitcode(status)==0)==(scenario=='success'),'helper outcome '+scenario)
    check((p.returncode==0)==(scenario=='success'),'receiver outcome '+scenario)
    if ch.exists(): print('receiver diagnostic:',stderr.replace(canary.encode(),b'[redacted]'))
    check(not ch.exists(),'channel cleanup')
    if scenario!='success':
        verify=". /usr/share/debconf/confmodule\ndb_get partman-crypto/passphrase\n"
        if scenario=='second-set':verify+='[ -z "$RET" ] || exit 1\n'
        verify+="db_set partman-crypto/passphrase ''\ndb_set partman-crypto/passphrase-again ''\n"
        (ram/'verify').write_text(verify)
    run(['/usr/lib/cdebconf/debconf','/bin/sh','/test/verify'])
    # rfc822db rotates a RAM-only passwords.dat-old backup. A second clear/save
    # rotates the already-empty database; no private database format editing.
    (ram/'clear').write_text(". /usr/share/debconf/confmodule\ndb_set partman-crypto/passphrase ''\ndb_set partman-crypto/passphrase-again ''\n")
    run(['/usr/lib/cdebconf/debconf','/bin/sh','/test/clear'])
    check(all(canary.encode() not in c for c in captures),'no output or xtrace leak')
    for folder in [ram/'db',ram/'log',ram/'tmp',ram/'run']:
        for f in folder.rglob('*'):
            if f.is_file():check(canary.encode() not in f.read_bytes(),'post-clear artefact '+str(f.relative_to(ram)))
print('PASS assertions:',count)
