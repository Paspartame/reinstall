import pathlib,tempfile,subprocess,os,json
R=pathlib.Path(__file__).resolve().parents[1]
script=(R/'reinstall.sh').read_text();prefix=script[:script.index("trap 'trap_err $LINENO $?' ERR")]
results=[]
with tempfile.TemporaryDirectory() as td:
 t=pathlib.Path(td);repo=t/'repo';repo.mkdir();bin=t/'bin';bin.mkdir()
 def g(*args):return subprocess.check_output(['git','-C',str(repo),'-c','user.name=fixture','-c','user.email=fixture@example.invalid',*args],text=True).strip()
 subprocess.run(['git','init','-q',str(repo)],check=True)
 # Use exact production prefix; replace only continuation with an observable no-mutation sink.
 entry=prefix+'printf "SELECTED %s\n" "$(cat "$(dirname "$0")/helper")"\n'
 (repo/'reinstall.sh').write_text(entry);(repo/'debian-crypto-build.py').write_text('# fixture');(repo/'helper').write_text('first');g('add','.');g('commit','-qm','first');first=g('rev-parse','HEAD');g('branch','main');g('branch','feature/debian13-luks-dropbear')
 (repo/'helper').write_text('helper-only');g('add','.');g('commit','-qm','helper-only');second=g('rev-parse','HEAD');g('branch','-f','main',second)
 realgit=subprocess.check_output(['which','git'],text=True).strip()
 def tool(n,s):p=bin/n;p.write_text('#!/bin/bash\n'+s);p.chmod(0o755)
 tool('apt-get','exit 0\n')
 tool('git',f'args=("$@"); for i in "${{!args[@]}}"; do if [ "${{args[$i]}}" = https://github.com/Paspartame/reinstall.git ]; then args[$i]={repo}; fi; done; exec {realgit} "${{args[@]}}"\n')
 # Production forcibly extends PATH; explicitly bind this boundary only.
 testentry=entry.replace('export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH','export PATH="'+str(bin)+':$PATH"').replace('[ "$EUID" = 0 ]','true').replace('. /etc/os-release','ID=debian; VERSION_ID=13').replace('/var/tmp/reinstall-source.',str(t)+'/reinstall-source.')
 # Repository entry must have exactly same bytes as downloaded fixture.
 (repo/'reinstall.sh').write_text(testentry);g('add','.');g('commit','-qm','fixture-path-boundary');current=g('rev-parse','HEAD');g('branch','-f','main',current);g('branch','-f','feature/debian13-luks-dropbear',current)
 work=t/'work';work.mkdir();download=work/'reinstall.sh';download.write_text(testentry)
 def case(name,env,good,needle):
  e=os.environ.copy();e.update(env)
  p=subprocess.run(['bash',str(download),'debian','13','--installer','--encrypt'],env=e,capture_output=True,text=True,timeout=30)
  assert (p.returncode==0)==good,(name,p.stdout,p.stderr)
  assert needle in p.stdout+p.stderr,(name,p.stdout,p.stderr)
  results.append({'case':name,'exit':p.returncode,'scope':'actual production prefix, isolated local Git and apt/PATH boundary'})
 case('default-main',{},True,'SELECTED helper-only')
 case('explicit-feature',{'REINSTALL_SOURCE_BRANCH':'feature/debian13-luks-dropbear'},True,'SELECTED helper-only')
 case('full-sha',{'REINSTALL_SOURCE_REF':current},True,'SELECTED helper-only')
 (repo/'helper').write_text('latest-helper-only');g('add','.');g('commit','-qm','latest-helper');latest=g('rev-parse','HEAD');g('branch','-f','main',latest)
 case('helper-only-update',{},True,'SELECTED latest-helper-only')
 case('invalid-sha',{'REINSTALL_SOURCE_REF':'BAD'},False,'full Git SHA')
 case('unavailable-sha',{'REINSTALL_SOURCE_REF':'0'*40},False,'unable to read tree')
 case('invalid-branch',{'REINSTALL_SOURCE_BRANCH':'unavailable'},False,'Unsupported')
 g('branch','-D','feature/debian13-luks-dropbear')
 case('unavailable-feature',{'REINSTALL_SOURCE_BRANCH':'feature/debian13-luks-dropbear'},False,'not found')
 download.write_text(testentry+'# stale\n');case('stale-entry',{},False,'Source mismatch')
 print(json.dumps(results,indent=2))
