#!/usr/bin/env python3
"""Structural recipe checks; not an installer E2E substitute."""
import pathlib, re, subprocess
root=pathlib.Path(__file__).resolve().parents[1]
for mode in ['efi','bios']:
    text=subprocess.check_output(['sh',str(root/'debian-crypto-recipe.sh'),mode],text=True)
    name,body=text.split('::',1)
    stanzas=[s.strip() for s in body.split('.') if s.strip()]
    assert len(stanzas)==3
    parsed=[]
    for s in stanzas:
        fields=s.split(None,4)
        assert len(fields)==5
        low,priority,maximum=map(int,fields[:3])
        assert low>0 and priority>0
        specs=dict(re.findall(r'([\w$]+)\{\s*([^}]*?)\s*\}',fields[4]))
        parsed.append((fields[3],specs))
    assert parsed[0][1]['method']==('efi' if mode=='efi' else 'biosgrub')
    assert parsed[0][1]['$iflabel']=='gpt'
    assert parsed[1][1]['mountpoint']=='/boot'
    assert '$lvmok' not in parsed[1][1] and '$defaultignore' in parsed[1][1]
    assert parsed[2][1]['mountpoint']=='/' and '$lvmok' in parsed[2][1]
    assert all(p[1]['method']!='swap' for p in parsed)
    print('PASS',mode,'three parsed stanzas, unencrypted boot and LVM root, no swap')
assert subprocess.run(['sh',str(root/'debian-crypto-recipe.sh'),'unsupported'],capture_output=True).returncode!=0
after=(root/'debian.cfg').read_text()
# Helpers hold the complete mature S71 commands; preseed stanzas merely dispatch them.
assert '/preseed-mirror-diagnostic.sh' in (root/'preseed-early.sh').read_text()
assert 'in-target systemctl enable ssh' in (root/'preseed-late.sh').read_text()
assert 'bootstrap-base.postinst' in (root/'partman-early.sh').read_text()
assert 'd-i preseed/early_command string sh /usr/local/lib/reinstall/preseed-early.sh' in after
assert 'd-i preseed/late_command string sh /usr/local/lib/reinstall/preseed-late.sh' in after
assert 'd-i partman/early_command string sh /usr/local/lib/reinstall/partman-early.sh' in after
assert 'if [ -f /reinstall-crypto-enabled ]; then' in (root/'partman-early.sh').read_text()
assert after.count('d-i preseed/late_command string') == 1
assert after.count('d-i preseed/early_command string') == 1
assert 'sh /debian-crypto-gate.sh ||' in (root/'partman-early.sh').read_text()
assert 'partman-auto/method string crypto' in (root/'partman-early.sh').read_text()
print('PASS default partition recipe remains unencrypted and opt-in hook is conditional')
