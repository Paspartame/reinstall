#!/usr/bin/env python3
"""Offline generator regression; never configures host networking."""
import pathlib, tempfile, subprocess, sys
R=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp); net=p/'net';net.mkdir();keys=p/'keys'
 keys.write_text('ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHqXyZY+eRrSmBWbYR5sj1amFeJEByENSPUgGdsKmLjN test\n')
 facts={'mac_addr':'52:54:00:12:34:56','ethx':'ens3','dhcpv4':'1','should_disable_dhcpv4':'0','ipv4_addr':'192.0.2.10/24','ipv4_gateway':'192.0.2.1','ipv6_addr':'2001:db8::10/64','ipv6_gateway':'fe80::1','ipv4_has_internet':'1'}
 for k,v in facts.items():(net/k).write_text(v+'\n')
 def run(ok=True):
  r=subprocess.run([sys.executable,str(R/'debian-unlock-config.py'),str(p/'root'),str(keys),str(net)],capture_output=True,text=True)
  assert (r.returncode==0)==ok,r.stderr
 run();root=p/'root'
 auth=(root/'etc/dropbear/initramfs/authorized_keys').read_text()
 assert auth.startswith('no-agent-forwarding,no-port-forwarding,no-X11-forwarding,command="/bin/cryptroot-unlock" ssh-ed25519 ')
 assert 'no-pty' not in auth
 conf=(root/'etc/reinstall-unlock/network.conf').read_text();assert 'dhcpv4=1' in conf and '52:54:00:12:34:56' in conf
 (net/'should_disable_dhcpv4').write_text('1');run()
 assert "dhcpv4=0" in (root/'etc/reinstall-unlock/network.conf').read_text()
 (net/'ipv4_has_internet').write_text('0');run(False)
 (net/'ipv4_has_internet').write_text('1');(net/'ipv4_addr').write_text('bad');run(False)
 keys.write_text('command="evil" ssh-ed25519 AAAA\n');run(False)
 print('PASS DHCP, static IPv4, dual-stack IPv4 preservation, IPv6-only rejection, forced command, TTY and invalid input')
