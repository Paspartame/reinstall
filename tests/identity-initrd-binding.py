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
 P('/boot/vmlinuz-fixture').write_text('PUBLIC-KERNEL')
 P('/boot/grub').mkdir()
 grub='set default="${next_entry}"\nset default="0"\nmenuentry \'Debian GNU/Linux\' {\n linux /vmlinuz-fixture root=fixture\n initrd /initrd.img-fixture\n}\n'
 P('/boot/grub/grub.cfg').write_text(grub)
 P('/lib/modules/fixture').mkdir(parents=True);P('/run/reinstall-identity-ram').mkdir(parents=True)
 def run(*a):
  if a[0]=='/usr/sbin/sshd':return 'hostkey /etc/ssh/ssh_host_ed25519_key\nport 22'
  if a[0] in ('ssh-keygen','dropbearkey'):return key
  if a[0]=='stat':return 'tmpfs'
  if a[0]=='grub-editenv':return ''
  if a[0]=='findmnt':return '/boot ext4'
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
  rows=first.split('BEGIN COPY (Dropbear, then Debian)\n')[1].split('\nEND COPY')[0].splitlines()
  assert len(rows)==2 and rows[0].startswith('[example.org]:2222 ssh-ed25519 ') and rows[1].startswith('example.org ssh-ed25519 ')
  P('/etc/dropbear/initramfs/dropbear.conf').write_text('DROPBEAR_OPTIONS="-p 22"')
  collision=render();assert 'COLLISION' in collision and 'BEGIN COPY' not in collision
  P('/etc/dropbear/initramfs/dropbear.conf').write_text('DROPBEAR_OPTIONS="-p 2202"')
  assert '[example.org]:2202 ssh-ed25519 ' in render()
  P('/etc/dropbear/initramfs/dropbear.conf').write_text('DROPBEAR_OPTIONS="-p 2222"')
  P('/boot/initrd.img-fixture').write_text('PUBLIC-CHANGED-NONPAYLOAD-BYTES')
  second=render()
  assert first!=second,'CONFIRMATION BYPASS: full initrd byte change not reflected in verified display'
  for bad in [grub.replace('/initrd.img-fixture','/initrd.img-WRONG'),grub.replace('set default="0"','set default="1"')]:
   P('/boot/grub/grub.cfg').write_text(bad)
   try:render()
   except ValueError:pass
   else:raise AssertionError('wrong GRUB selection accepted')
  P('/boot/grub/grub.cfg').write_text(grub)
  initrd=P('/boot/initrd.img-fixture');saved=initrd.read_bytes();initrd.unlink()
  try:render()
  except ValueError:pass
  else:raise AssertionError('missing selected initrd accepted')
  initrd.write_bytes(saved)
  with patch.object(m.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['unmkinitramfs'])):
   try:render()
   except subprocess.CalledProcessError:pass
   else:raise AssertionError('corrupt extraction accepted')
  with patch.object(m,'run',lambda *a:'ext4' if a[0]=='stat' else run(*a)):
   try:render()
   except ValueError as e:assert 'tmpfs' in str(e)
   else:raise AssertionError('persistent extraction accepted')
  def mutate(a,**kw):
   extract(a,**kw);P('/boot/initrd.img-fixture').write_text('PUBLIC-MID-EXTRACTION-MUTATION')
  with patch.object(m.subprocess,'run',mutate):
   try:render()
   except ValueError as e:assert 'changed during verification' in str(e)
   else:raise AssertionError('mid-extraction mutation accepted')
print('BEHAVIORAL_INITRD_BINDING_PASS (public filesystem/extractor fixture; not installed E2E)')
