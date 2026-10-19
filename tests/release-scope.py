import pathlib,subprocess,tempfile
R=pathlib.Path(__file__).resolve().parents[1];s=(R/'reinstall.sh').read_text()
a=s.index('    if [ "$distro" = debian ] && [ "$releasever" = 13 ]; then',s.index('mod_initrd_debian_kali()'))
b=s.index('    # hack 1',a)
with tempfile.TemporaryDirectory() as td:
 r=subprocess.run(['bash','-c','set -e; distro=debian; releasever=13; encrypt=0; initrd_dir='+td+'; confhome_local=/MISSING; error_and_exit(){ exit 99; }; '+s[a:b]],capture_output=True)
 assert r.returncode==0,'ordinary Debian13 incorrectly requires local crypto helpers'
assert 'if [ "${encrypt:-0}" = 1 ]; then\n            command curl' in s,'encrypted HTTPS must not use insecure transport'
print('RELEASE_SCOPE_TLS_PASS')
