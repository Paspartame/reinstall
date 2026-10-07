#!/usr/bin/env python3
"""PTY + real FIFO integration. Only paths/UID are adapted in a RAM copy.
Supply Debian cdebconf source root as argv[1]; its actual shell confmodule
functions are generated exactly as client/confmodule.build does. The mock
frontend records values only in Python memory and implements CAPB parsing.
"""
import os, pathlib, tempfile, subprocess, threading, time, pty, select, signal, uuid, re, sys
REPO = pathlib.Path(__file__).resolve().parents[1]
SOURCE = pathlib.Path(sys.argv[1])
CANARY = 'REINSTALL_LUKS_CANARY_' + uuid.uuid4().hex
checks = 0

def check(ok, label):
    global checks
    if not ok:
        raise AssertionError(label)
    checks += 1
    print('PASS', label)

def wait_for(fn):
    end = time.monotonic() + 8
    while time.monotonic() < end:
        if fn(): return
        time.sleep(.01)
    raise AssertionError('condition timeout')

with tempfile.TemporaryDirectory(prefix='luks-test-', dir='/dev/shm') as tmp:
    root = pathlib.Path(tmp)
    # Never install test overrides into production files.
    conf = (SOURCE / 'src/client/confmodule.in').read_text()
    conf = re.sub(r'REPEAT:.*', '\n'.join(
        'db_'+name+' () { _db_cmd "'+name.upper()+'" "$@"; }'
        for name in ['set','get','capb','fset']), conf)
    cf = root / 'confmodule'; cf.write_text(conf)
    swaps = root / 'swaps'; swaps.write_text('Filename Type Size Used Priority\n')
    text = (REPO / 'reinstall-luks-passphrase').read_text()
    text = text.replace('/proc/swaps', str(swaps)).replace('/var/lib/cdebconf', str(root))
    text = text.replace('ROOT=/run', 'ROOT='+str(root)).replace('OWNER=0', 'OWNER='+str(os.getuid()))
    text = text.replace('. /usr/share/debconf/confmodule', '. '+str(cf))
    for name in ['reinstall-luks-passphrase','reinstall-luks-receiver']:
        (root / name).write_text(text)
    channel = root / 'reinstall-luks'
    captures = []
    samples = []
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(subprocess.run(['ps','auxww'],capture_output=True).stdout)
            stop.wait(.03)
    sampler = threading.Thread(target=sample); sampler.start()

    def start_receiver(fail_second=False):
        values = {}; errors = []
        env = os.environ.copy()
        env.update(DEBIAN_HAS_FRONTEND='1', DEBCONF_USE_CDEBCONF='1')
        env.pop('DEBCONF_REDIR',None)
        # cdebconf supplies stdout's original destination on descriptor 5.
        p = subprocess.Popen(['/bin/sh','-c','exec 5>&2; exec /bin/sh -x "$1"','receiver',str(root/'reinstall-luks-receiver')],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        def backend():
            escaped = False
            try:
                for raw in p.stdout:
                    line = raw.decode().strip()
                    if escaped:
                        line = re.sub(r'\\(.)',lambda m:'\n' if m[1]=='n' else m[1],line)
                    fields = line.split(None,2)
                    cmd = fields[0]; reply = '0 ok'
                    if cmd == 'CAPB': escaped = True
                    elif cmd == 'SET':
                        key = fields[1]; value = fields[2] if len(fields)>2 else ''
                        if fail_second and key.endswith('-again') and value:
                            reply = '10 injected failure'
                        else: values[key] = value
                    elif cmd == 'GET': reply = '0 '+values.get(fields[1],'')
                    else: reply = '20 unsupported'
                    p.stdin.write((reply+'\n').encode()); p.stdin.flush()
            except (BrokenPipeError, ValueError): pass
            except Exception as e: errors.append(type(e).__name__)
        t=threading.Thread(target=backend);t.start()
        wait_for(lambda: ((channel/'ready').exists() and (channel/'pid').read_text().strip()==str(p.pid)) or p.poll() is not None)
        if p.poll() is not None:
            print(p.stderr.read().decode())
        check(p.poll() is None, 'receiver ready')
        return p,t,values,errors

    def helper(first=None, second=None):
        pid,fd=pty.fork()
        if pid==0:
            os.execv('/bin/sh',['/bin/sh','-x',str(root/'reinstall-luks-passphrase')])
        output=b''
        def until(marker):
            nonlocal output
            end=time.monotonic()+8
            while marker not in output:
                if time.monotonic()>end: raise AssertionError('PTY prompt timeout')
                if select.select([fd],[],[],.1)[0]:
                    try: part=os.read(fd,65536)
                    except OSError: break
                    if not part: break
                    output+=part
        if first is not None:
            until(b'Enter LUKS passphrase: ')
            os.write(fd,first.encode()+b'\n')
            until(b'Confirm LUKS passphrase: ')
            os.write(fd,second.encode()+b'\n')
        until(b'NEVER-A-REAL-MARKER') if False else None
        end=time.monotonic()+10
        status=None
        while time.monotonic()<end:
            if select.select([fd],[],[],.05)[0]:
                try: output+=os.read(fd,65536)
                except OSError: pass
            done,s=os.waitpid(pid,os.WNOHANG)
            if done: status=s;break
        if status is None:
            os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
            raise AssertionError('helper timeout')
        os.close(fd);captures.append(output)
        return os.waitstatus_to_exitcode(status),output

    def finish(p,t,values,errors,success):
        p.wait(timeout=8);t.join(timeout=2)
        captures.append(p.stderr.read())
        check(not errors,'backend no exceptions')
        check((p.returncode==0)==success,'receiver exit status')
        check(not channel.exists(),'FIFO ready status cleanup')

    try:
        cases=['ascii','a b',"a'b",'a"b','a$b','a%b',r'a\b','中文🔑','a'*1024,'mix 空格 \\ $ % " end',CANARY]
        for i,value in enumerate(cases):
            p,t,values,errors=start_receiver()
            rc,out=helper(value,value)
            check(rc==0,'PTY success '+str(i))
            check(value.encode() not in out,'no terminal echo '+str(i))
            finish(p,t,values,errors,True)
            check(values.get('partman-crypto/passphrase')==value and values.get('partman-crypto/passphrase-again')==value,'both keys exact '+str(i))
            values.clear()
        for i,(a,b) in enumerate([('',''),(' secret',' secret'),('secret ','secret '),('\tsecret','\tsecret'),('secret\t','secret\t'),('one','two'),('\u00a0secret','\u00a0secret')]):
            p,t,values,errors=start_receiver()
            rc,out=helper(a,b)
            check(rc!=0,'PTY reject '+str(i))
            check(not any(values.values()),'reject no partial keys')
            p.terminate();finish(p,t,values,errors,False)
        p,t,values,errors=start_receiver(True)
        rc,out=helper(CANARY,CANARY)
        check(rc!=0,'second SET failure reaches helper')
        finish(p,t,values,errors,False)
        check(not any(values.values()),'second SET rollback')
        rc,out=helper();check(rc!=0,'absent receiver rejected')
        for malformed in ['no-ready','no-fifo','wrong-fifo']:
            channel.mkdir(mode=0o700)
            (channel/'pid').write_text(str(os.getpid())+'\n')
            if malformed!='no-ready':(channel/'ready').touch()
            if malformed=='wrong-fifo':(channel/'passphrase.fifo').touch()
            rc,out=helper();check(rc!=0,malformed+' rejected')
            for f in channel.iterdir():f.unlink()
            channel.rmdir()
        p,t,values,errors=start_receiver();p.terminate();finish(p,t,values,errors,False)
        # SIGKILL cannot run a shell trap. The next receiver must safely reclaim
        # its dead PID's private channel, without treating stale ready as live.
        p,t,values,errors=start_receiver();p.kill();p.wait();t.join()
        captures.append(p.stderr.read())
        rc,out=helper();check(rc!=0,'stale ready dead receiver rejected')
        p,t,values,errors=start_receiver();rc,out=helper('restart','restart')
        check(rc==0,'channel restart');finish(p,t,values,errors,True);values.clear()
    finally:
        stop.set();sampler.join()
    check(all(CANARY.encode() not in c for c in captures),'canary absent stdout stderr PTY')
    check(all(CANARY.encode() not in s for s in samples),'canary absent ps argv')
    for base in [root,REPO,pathlib.Path('/tmp')]:
        for f in base.rglob('*'):
            try:
                if f.is_file() and not f.is_symlink():
                    check(CANARY.encode() not in f.read_bytes(),'artifact scan '+str(f.relative_to(base)))
            except PermissionError: pass
    check(not pathlib.Path('/run/reinstall-luks').exists(),'production RAM path untouched')
print('ALL PASS:',checks,'assertions')
