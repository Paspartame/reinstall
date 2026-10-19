import pathlib,tempfile,importlib.util,unittest.mock as mock,os
R=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('builder',R/'debian-crypto-build.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
# Avoid executable probing in pure transactional test; real runtime tested separately.
with tempfile.TemporaryDirectory() as td:
 t=pathlib.Path(td);root=t/'root';root.mkdir();(root/'preseed.cfg').write_text('ORIGINAL');(root/'preseed.cfg').chmod(0o640);key=t/'key';key.write_text('ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHFxGyrhwyjKO0lC9JhGAdYezycdSPqGManbc+z7yP8z public\n')
 fake=pathlib.Path(os.environ['PUBLIC_BUSYBOX'])
 import sys,types
 runtime=types.SimpleNamespace(resolve=lambda candidate:fake)
 real=m.importlib if hasattr(m,'importlib') else None
 # runtime module loads internally; patch its resolve through exec_module wrapper.
 import importlib.machinery
 orig=importlib.machinery.SourceFileLoader.exec_module
 def load(loader,module):
  orig(loader,module)
  if module.__name__=='crypto_runtime':module.resolve=lambda candidate:fake
 original=m.shutil.copyfile
 counter=[0]
 def fail(src,dst,*args,**kw):
  if pathlib.Path(dst).is_relative_to(root):
   counter[0]+=1
   if counter[0]==5:raise OSError('PUBLIC_INJECTED_FAILURE')
  return original(src,dst,*args,**kw)
 with mock.patch.object(importlib.machinery.SourceFileLoader,'exec_module',load),mock.patch.object(m.shutil,'copyfile',fail):
  try:m.build(R,root,None,key,2222,fake);raise AssertionError('failure not triggered')
  except OSError:pass
 assert (root/'preseed.cfg').read_text()=='ORIGINAL'
 assert (root/'preseed.cfg').stat().st_mode & 0o777==0o640
 with mock.patch.object(importlib.machinery.SourceFileLoader,'exec_module',load):m.build(R,root,None,key,2222,fake)
 assert (root/'reinstall-crypto-enabled').exists()
 assert not list(root.rglob('*backup*'))
print('STAGING_ROLLBACK_AND_SUCCESS_CLEANUP_PASS')
