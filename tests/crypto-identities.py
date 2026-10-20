import pathlib,importlib.util,base64,struct,hashlib,contextlib,io
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ids',R/'reinstall-crypto-identities.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+bytes(range(32));key='ssh-ed25519 '+base64.b64encode(raw).decode()
assert m.public(key)[1]=='SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
for host,port,binding in [('example.org',22,'example.org'),('example.org',2222,'[example.org]:2222'),('2001:db8::1',2200,'[2001:db8::1]:2200'),('example.org',2223,'[example.org]:2223')]:
 with contextlib.redirect_stdout(io.StringIO()) as o:m.show('STAGE',key,host,port)
 assert 'known_hosts: '+binding+' '+key in o.getvalue()
for bad in ['ssh-ed25519 !!!','ssh-rsa AAAA',key+'\n'+key]:
 try:m.public(bad)
 except ValueError:pass
 else:raise AssertionError('malformed/multiline accepted')
for host in ['evil\nHOST','example.org;touch','[bad]']:
 try:m.show('STAGE',key,host,22)
 except ValueError:pass
 else:raise AssertionError('host accepted')
for bad in ['bad..host','-bad.example','example.org;id','bad\x1b[31m','bad\nHOST']:
 try:m.label(bad)
 except ValueError:pass
 else:raise AssertionError('invalid address accepted')
assert m.label('2001:0db8::1')=='2001:db8::1'
assert m.label('SSH.Example.org')=='ssh.example.org'
print('PUBLIC_IDENTITY_FORMAT_AND_REJECTION_PASS')
