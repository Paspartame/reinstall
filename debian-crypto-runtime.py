#!/usr/bin/env python3
"""Resolve an administrator-installed static BusyBox; no downloads or host writes."""
import pathlib,shutil,struct,subprocess,tempfile,os

def resolve(candidate=None):
    path=pathlib.Path(candidate or shutil.which('busybox') or '/usr/bin/busybox')
    if not path.is_file():
        raise ValueError('Install trusted distro busybox-static and python3 first (Debian: apt install busybox-static python3).')
    data=path.read_bytes()
    if data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',data,18)[0]!=62:
        raise ValueError('Debian 13 encrypted installer requires a static amd64 ELF BusyBox.')
    off=struct.unpack_from('<Q',data,32)[0];size,count=struct.unpack_from('<HH',data,54)
    if size<56 or off+size*count>len(data):raise ValueError('Invalid ELF program headers')
    for i in range(count):
        if struct.unpack_from('<I',data,off+i*size)[0] in (2,3):
            raise ValueError('BusyBox must be static, with no ELF interpreter or dynamic segment; install busybox-static.')
    applets=subprocess.run([str(path),'--list'],check=True,capture_output=True,text=True,timeout=5).stdout.split()
    if not {'stat','mkfifo','base64','awk'}.issubset(applets):raise ValueError('BusyBox lacks required crypto applets')
    with tempfile.TemporaryDirectory(prefix='crypto-runtime-') as d:
        fifo=pathlib.Path(d)/'fifo'
        subprocess.run([str(path),'mkfifo','-m','600',str(fifo)],check=True,timeout=5)
        result=subprocess.run([str(path),'stat','-c','%F',str(fifo)],check=True,capture_output=True,text=True,timeout=5)
        if result.stdout.strip()!='fifo':raise ValueError('Incompatible BusyBox stat/mkfifo')
        if subprocess.run([str(path),'base64','-d'],input=b'UFVCTElD',capture_output=True,check=True,timeout=5).stdout!=b'PUBLIC':raise ValueError('Incompatible base64')
        if subprocess.run([str(path),'awk','{print $2}'],input=b'one two\n',capture_output=True,check=True,timeout=5).stdout!=b'two\n':raise ValueError('Incompatible awk')
    return path.resolve()
if __name__=='__main__':
    import sys
    try:print(resolve(sys.argv[1] if len(sys.argv)>1 else None))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:sys.exit('Crypto runtime unavailable: '+str(exc))
