#!/usr/bin/env python3
"""Execute real MAC-selection and fallback branches with deterministic mocks."""
import pathlib, subprocess
source=(pathlib.Path(__file__).resolve().parents[1]/'debian-unlock-network.sh').read_text()
s=source[source.index("ethx=''\n"):source.index('# Standard configure_networking')]
for name,lease,facts,mac,expected in [('dhcp-success',1,2,1,0),('timeout-static',0,2,1,0),('missing-facts',0,0,1,1),('partial-facts',0,1,1,1),('address-no-route',2,2,1,0),('mac-mismatch',0,2,0,1)]:
 prefix='set -eu; dhcpv4=1; state='+str(lease)+'; ipv4_addr='+('192.0.2.2/24' if facts else "''")+'; ipv4_gateway='+('192.0.2.1' if facts==2 else "''")+'; '
 prefix+='get_ethx(){ '+('echo test0;' if mac else 'return 1;')+' }; sleep(){ :; }; ipconfig(){ '+('state=1; return 0;' if lease==1 else 'return 1;')+' }; '
 prefix+='ip(){ :; }; is_have_ipv4(){ [ "$state" = 1 ]; }; add_missing_ipv4_config(){ state=1; }; '
 r=subprocess.run(['sh','-c',prefix+s]);assert r.returncode==expected,(name,r.returncode)
 print(name,'PASS')
