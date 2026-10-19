import pathlib,subprocess,tempfile,json,os,sys
R=pathlib.Path(__file__).resolve().parents[1]
s=(R/'reinstall.sh').read_text();decl=s[:s.index('# 检查 root')]
# Actual option list, getopt, both scans, mature key resolver and normalization.
# This is a bounded parser fixture, NOT complete CLI acceptance.
body=s[s.index('# 整理参数'):s.index('# 检查必须的参数')]
# Narrow host-only calls intercepted after declarations; no top-level host checks.
stubs='''
init_basearch(){ basearch=x86_64; }
init_confhome(){ :; }
init_bootloader_facts(){ :; }
install_pkg(){ :; }
mkdir_clear(){ mkdir -p "$1"; }
get_unix_path(){ printf '%s' "$1"; }
'''
with tempfile.TemporaryDirectory(dir=R.parent) as td:
 p=pathlib.Path(td);key=p/'key.pub';key.write_text('ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHFxGyrhwyjKO0lC9JhGAdYezycdSPqGManbc+z7yP8z public\n')
 script=p/'parser.sh';script.write_text(decl+'\ntmp='+str(p/'work')+'\n'+stubs+body+'\nprintf "KEY=%s\\nPORT=%s\\n" "$ssh_keys" "${unlock_port:-2222}"\n')
 base=['debian','13','--installer','--username','root'];rows=[]
 for name,args,ok in [('encrypt-first',['--encrypt','--ssh-key',str(key)],True),('key-first',['--ssh-key',str(key),'--encrypt'],True),('literal',['--encrypt','--ssh-key',key.read_text().strip()],True),('plain',['--ssh-key',str(key)],True),('missing-file',['--encrypt','--ssh-key',str(p/'missing')],False),('malformed',['--encrypt','--ssh-key','not-key'],False),('invalid-port',['--encrypt','--ssh-key',str(key),'--unlock-port','70000'],False)]:
  r=subprocess.run(['bash',str(script)]+base+args,capture_output=True,text=True,timeout=10)
  assert (r.returncode==0)==ok,(name,r.returncode)
  if ok:assert 'KEY=ssh-ed25519 ' in r.stdout and 'PORT=2222' in r.stdout
  rows.append({'case':name,'exit':r.returncode,'expected_pass':ok})
 print(json.dumps({'scope':'real parser fragment, host calls stubbed; NOT full CLI','cases':rows},indent=2))
