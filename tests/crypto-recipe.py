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
before=subprocess.check_output(['git','show','0756ab6:debian.cfg'],cwd=root).decode()
after=(root/'debian.cfg').read_text()
# Compare the entire old default configuration after removing only the two
# opt-in clauses, not a handful of strings from its partition recipe.
normalized=after.replace('if [ $swap_size -gt 0 ] && [ ! -f /reinstall-crypto-enabled ]; then', 'if [ $swap_size -gt 0 ]; then')
start=normalized.index('    if [ -f /reinstall-crypto-enabled ]; then')
end=normalized.index('    elif [ -d /sys/firmware/efi ]; then',start)
normalized=normalized[:start]+normalized[end:].replace('    elif [ -d /sys/firmware/efi ]; then','    if [ -d /sys/firmware/efi ]; then',1)
start=normalized.index('    if [ -f /reinstall-crypto-enabled ]; then')
end=normalized.index('    if [ "$elts" = 1 ]; then',start)
normalized=normalized[:start]+normalized[end:]
assert normalized==before
print('PASS entire default configuration unchanged outside three opt-in clauses')
