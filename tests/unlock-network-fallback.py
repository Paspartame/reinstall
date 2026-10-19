#!/usr/bin/env python3
import pathlib, subprocess
s=(pathlib.Path(__file__).resolve().parents[1]/'debian-unlock-network.sh').read_text()
s=s[s.index('if [ "$dhcpv4" = 1 ]; then'):s.index('# Standard configure_networking')]
for name,lease,facts,expected in [('dhcp-success',1,1,0),('timeout-static',0,1,0),('timeout-no-facts',0,0,1)]:
 prefix='set -eu; dhcpv4=1; ethx=test0; ready='+str(lease)+'; ipv4_addr='+('192.0.2.2/24' if facts else "''")+'; ipv4_gateway='+('192.0.2.1' if facts else "''")+'; ipconfig(){ return 1; }; ip(){ :; }; is_have_ipv4(){ [ "$ready" = 1 ]; }; add_missing_ipv4_config(){ ready=1; }; '
 r=subprocess.run(['sh','-c',prefix+s]);assert r.returncode==expected,(name,r.returncode)
 print(name,'PASS')
assert '[ -n "$ethx" ] || exit 1' in (pathlib.Path(__file__).resolve().parents[1]/'debian-unlock-network.sh').read_text()
print('MAC lookup fail-closed static assertion only; not live MAC mismatch test')
