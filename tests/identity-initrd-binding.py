import pathlib,importlib.util,tempfile,contextlib,io,types,subprocess
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ids',R/'reinstall-crypto-identities.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
key='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB0sjq5EvCNxMryRttgpTaDmAgsT4c7iPXhbhyZUPG2H'
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);Real=pathlib.Path
 def P(s):
  p=Real(s)
  return p if p.is_relative_to(root) else root/str(s).lstrip('/')
 for p,data in {'/etc/ssh/ssh_host_ed25519_key.pub':key,'/etc/dropbear/initramfs/dropbear_ed25519_host_key':'PUBLIC-FIXTURE','/etc/dropbear/initramfs/dropbear.conf':'DROPBEAR_OPTIONS="-p 2222"','/etc/reinstall-unlock/network.conf':'PUBLIC-NET','/usr/local/lib/reinstall/debian-unlock-network.sh':'PUBLIC-HOOK','/boot/initrd.img-fixture':'PUBLIC-INITRD'}.items():
  f=P(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
 P('/lib/modules/fixture').mkdir(parents=True);P('/run/reinstall-identity-ram').mkdir(parents=True)
 def run(*a):
  if a[0]=='/usr/sbin/sshd':return 'hostkey /etc/ssh/ssh_host_ed25519_key\nport 22'
  if a[0] in ('ssh-keygen','dropbearkey'):return key
  if a[0]=='stat':return 'tmpfs'
  raise AssertionError(a)
 def extract(a,**kw):
  tree=Real(a[2])/'main'
  for src,dst in [('/etc/dropbear/initramfs/dropbear_ed25519_host_key','etc/dropbear/dropbear_ed25519_host_key'),('/etc/dropbear/initramfs/dropbear.conf','etc/dropbear/dropbear.conf'),('/etc/reinstall-unlock/network.conf','etc/reinstall-unlock/network.conf'),('/usr/local/lib/reinstall/debian-unlock-network.sh','scripts/init-premount/reinstall-unlock-network')]:
   f=tree/dst;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(P(src).read_bytes())
 def render():
  with contextlib.redirect_stdout(io.StringIO()) as o:m.verify()
  return o.getvalue()
 m.HOST_OVERRIDE='example.org'
 with patch.object(m,'pathlib',types.SimpleNamespace(Path=P)),patch.object(m,'run',run),patch.object(m.subprocess,'run',extract):
  first=render();assert 'BEGIN COPY' in first
  P('/boot/initrd.img-fixture').write_text('PUBLIC-CHANGED-NONPAYLOAD-BYTES')
  second=render()
  assert first!=second,'CONFIRMATION BYPASS: full initrd byte change not reflected in verified display'
  def mutate(a,**kw):
   extract(a,**kw);P('/boot/initrd.img-fixture').write_text('PUBLIC-MID-EXTRACTION-MUTATION')
  with patch.object(m.subprocess,'run',mutate):
   try:render()
   except ValueError as e:assert 'changed during verification' in str(e)
   else:raise AssertionError('mid-extraction mutation accepted')
print('BEHAVIORAL_INITRD_BINDING_PASS (public filesystem/extractor fixture; not installed E2E)')
