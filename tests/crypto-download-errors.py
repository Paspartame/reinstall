import pathlib,subprocess,tempfile,os,json
R=pathlib.Path(__file__).resolve().parents[1];s=(R/'reinstall.sh').read_text();a=s.index('curl() {');b=s.index('\n}\n',a)+3;fn=s[a:b]
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td);binary=p/'curl';binary.write_text('#!/bin/sh\nfor a in "$@"; do [ "$a" != --insecure ] || exit 88; done\nexit "${MOCK_EXIT}"\n');binary.chmod(0o755)
 rows=[]
 for code in (22,60,7):
  env=os.environ.copy();env.update(PATH=str(p)+':'+env['PATH'],MOCK_EXIT=str(code))
  cmd='encrypt=1; confhome=https://example.invalid; is_have_cmd(){ return 0; }; show_url_in_args(){ :; }; sleep(){ :; }; '+fn+'\ncurl -Lo /dev/null https://example.invalid/fail; exit $?'
  r=subprocess.run(['bash','-c',cmd],env=env,capture_output=True);assert r.returncode==code,(code,r.returncode);rows.append({'mock_failure':code,'returned':r.returncode})
 print(json.dumps(rows))
