# Experimental Debian 13 encrypted reinstall

## Immutable full-checkout distribution

Never download reinstall.sh alone for encrypted mode. Before any later owner-authorized publication, choose a reviewed immutable commit from this feature branch, publish that exact commit to the configured Fork `https://github.com/Paspartame/reinstall.git`, then use:

```sh
git clone https://github.com/Paspartame/reinstall.git
cd reinstall
git checkout --detach <REVIEWED_PUBLISHED_COMMIT>
# Install only on the intended disposable test machine, not the development host:
apt-get update && apt-get install -y python3 busybox-static openssh-client curl cpio gzip
```

Publication has NOT happened in S81. The commit placeholder must be replaced with the actual published hash, never main/latest. Adjacent executable/network/preseed helpers come from the checkout. Legacy optional logviewer/frpc resources still reference upstream main; immutable source routing for those paths remains a release limitation. Do not claim a closed release bundle yet.

**IRREVERSIBLE DISK ERASURE:** the subsequent reinstall command destroys the selected machine's partitions. Verified backups, provider rescue console and separately pinned SSH host identities are required. Open the normal SSH and initramfs unlock ports in provider firewall/security groups. Every encrypted reboot requires manual remote unlock before normal SSH is available.

S81 explicitly rejects encrypted EFI; supported local evidence is BIOS amd64 DHCP only. Static IPv4/gateways are configuration-derived but not provider-tested, IPv6-only is rejected, cloud firewalls/custom routing/provider rescue behavior are not certified. Do not use this on a normal production VPS based solely on QEMU results.

**Local native CLI E2E validated in S80; not VPS-certified.** Fresh guardless root CLI self-reinstall and both same-disk unlock boots passed in disposable BIOS QEMU. No production deployment approved.

```sh
bash reinstall.sh debian 13 --installer --encrypt --ssh-key /path/to/test.pub --unlock-port 2222 --username root
```

Root must be inside the intended installed system; keep verified backups and an independent rescue console. BusyBox must be administrator-installed at /usr/bin/busybox. Pin Installer public identity from trusted console/ttyS0; obtain target Dropbear and normal OS public identities through authenticated Installer before reboot. Do not disable strict checking. Use `TERM=screen sh /installer-screen.sh` for exact installer window1 discovery; ambiguity is refused. Provider rescue/console access is required for failure recovery; a lost LUKS passphrase cannot be recovered.

Supported design target: Debian 13 amd64, explicit `--installer`, a plain supported SSH public key (`--ssh-key` literal or file; mature URL/username resolver retained), and `--unlock-port` (default 2222). Requires a complete adjacent source checkout, Python 3, OpenSSH key tools and trusted distribution `busybox-static`.

Installer SSH uses the configured normal SSH port. Run `/usr/local/sbin/reinstall-luks-passphrase` in an authenticated PTY to submit and confirm the synthetic/test LUKS passphrase. After reboot, initramfs Dropbear uses the unlock port and a distinct host identity; use a pinned key and `ssh -tt` for interactive `cryptroot-unlock`. Normal OS SSH has its own pinned identity. Do not append newline in raw non-TTY mode: the Debian script copies it as a password byte. Never disable SSH host verification.

No production VPS safety claim or deployment approval. Local BIOS native CLI validation does not cover UEFI, other hardware or networks; further deployment review remains necessary. Changes were integrated with Hermes Agent assistance; Git identity is the repository's existing configured identity.
