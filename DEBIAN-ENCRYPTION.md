# Experimental Debian 13 encrypted reinstall

## One-command Experimental start (Debian 13 / amd64 / BIOS / IPv4)

Replace `YOUR_USER` with your GitHub account holding your PUBLIC SSH key.
This command prompts on /dev/tty before preparing disk erasure. It installs
signed APT dependencies and fetches the whole pinned tree. Keep the matching
private key on an independent controller. It does NOT reboot automatically.

```sh
f=$(mktemp) && curl -fsSL 'https://raw.githubusercontent.com/Paspartame/reinstall/3f857671d9f98c79d5db7733ff6ba9df55bc5a6e/bootstrap-crypto.sh' -o "$f" && bash "$f" --revision 3f857671d9f98c79d5db7733ff6ba9df55bc5a6e --ssh-key github:YOUR_USER --unlock-port 2222; r=$?; rm -f -- "$f"; (exit "$r")
```

A one-line start is not unattended completion: record the printed Installer
identity, reboot deliberately, then follow the Installer SSH/PTY password,
public-key handoff pause/release and per-boot remote unlock instructions in
DEBIAN-ENCRYPTION.md. Never pass a LUKS secret as an option. `--confirm-erase`
is an explicitly selected noninteractive alternative, not a default.


## Scope and verified results

BIOS, amd64, Debian 13 installer, reachable IPv4 only. S86 completed a fresh
real-VPS public CLI encrypted installation and two pinned remote SSH/PTY unlocks
on the same disk, with independent normal-OS audits and different boot IDs.
Synthetic disposable credentials were used. Root is LUKS2 → LVM → ext4, with
independent ext4 `/boot` and no swap. Early DHCP versus the MAC-bound stored static
fallback was not independently identified on the successful boots.

UEFI, IPv6-only and arbitrary providers are unsupported/unproven. Provider cold
power cycle and a complete ordinary unencrypted installation were NOT tested.
This is Experimental, not production certification or a one-click installer.
Each encrypted reboot requires manual unlock. Maintain backups and provider
VNC/rescue. Loss of the LUKS secret means loss of encrypted data.

## Obtain the whole immutable source

Use the whole [Experimental branch](https://github.com/Paspartame/reinstall/tree/feature/debian13-luks-dropbear),
not a standalone `reinstall.sh`: its crypto helpers and preseed must match.
The full candidate tarball is an alternative: verify its accompanying SHA-256
file, unpack it and enter its source directory.

Set `REV` to the reviewed full commit SHA from the publication evidence/source
manifest (not a moving branch name), then run:

```sh
git clone https://github.com/Paspartame/reinstall.git
cd reinstall
git checkout --detach "$REV"
test "$(git rev-parse HEAD)" = "$REV"
```

Compare the manifest and candidate archive checksum delivered with the reviewed
version. Branch publication is not a GitHub Release or a production certification.

## Prepare on the intended disposable target

These package commands assume Debian with signed APT repositories:

```sh
apt-get update
apt-get install -y python3 busybox-static openssh-client curl cpio gzip xz-utils
uname -m
test ! -d /sys/firmware/efi
findmnt /boot
ip -4 route
```

Use a new public SSH key at `/root/reinstall-unlock.pub`. Keep its private key on
an independent controller, and choose a new user-held LUKS secret. Never reuse
the development test secret. Open TCP 22 (Installer and normal OS, distinct
identities) and TCP 2222 (initramfs unlock) in actual provider/host firewalls.
Confirm rescue availability before erasing the target.

**The following erases the target disk and partitions:**

```sh
bash reinstall.sh debian 13 --installer --encrypt --ssh-key /root/reinstall-unlock.pub --unlock-port 2222 --username root
```

Before reboot, record the CLI-printed Installer public host key over the trusted
old-OS SSH session. Store `TARGET ssh-ed25519 ...` in a dedicated
`installer-known-hosts` file on the controller. Reboot the target when ready.
All controller commands below use your actual hostname in place of `TARGET` and
`./unlock-client-key` for the private client identity retained outside the target.

## Installer password and required public-key handoff

```sh
ssh -tt -i ./unlock-client-key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=./installer-known-hosts root@TARGET /usr/local/sbin/reinstall-luks-passphrase
```

Enter and confirm the LUKS secret interactively. Installation continues, then
intentionally waits at the end of late_command. This is a required human step,
not a hang. Through the same pinned Installer SSH, poll for
`/run/reinstall-identity-ready` with bounded checks (for example every 10 seconds
for up to 30 minutes); if absent, inspect installer progress rather than reboot.
At readiness, collect **only public output**:

```sh
cat /target/etc/ssh/ssh_host_ed25519_key.pub
chroot /target dropbearkey -y -f /etc/dropbear/initramfs/dropbear_ed25519_host_key
```

Store normal OS public key as `TARGET ssh-ed25519 ...` in `os-known-hosts`, and
Dropbear public key as `[TARGET]:2222 ssh-ed25519 ...` in `dropbear-known-hosts`.
Keep all three identities separate. Do not export private host keys or use
ssh-keyscan alone as trust. Fingerprint public files with `ssh-keygen -lf`.

Verify the final installed initrd includes the expected identity and network
script **on the target**, without exporting the private key:

```sh
k=$(ls /target/lib/modules | head -n 1)
chroot /target unmkinitramfs /boot/initrd.img-$k /run/identity-check
# unmkinitramfs may extract directly or under main/; inspect its directory layout.
find /target/run/identity-check -name dropbear_ed25519_host_key -o -name reinstall-unlock-network
```

Use `cmp` on-target against `/target/etc/dropbear/initramfs/dropbear_ed25519_host_key`
and `/target/usr/local/lib/reinstall/debian-unlock-network.sh` respectively.
Check target layout, `/target/boot/grub/grub.cfg` and no swap. Remove only the
owned `/target/run/identity-check` extraction. Once keys are pinned and checks
pass, release the pause through authenticated Installer SSH:

```sh
touch /run/reinstall-identity-continue
```

## Unlock and independently verify normal OS

```sh
ssh -tt -i ./unlock-client-key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=./dropbear-known-hosts -p 2222 root@TARGET
ssh -i ./unlock-client-key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=./os-known-hosts root@TARGET
```

Enter the secret at the verified Dropbear prompt. Do not use a raw non-TTY stream
with a trailing newline: that newline can become a password byte. A disconnect
or sender exit 0 is not boot success. Wait for independently authenticated normal
SSH, then inspect:

```sh
cat /etc/debian_version
findmnt /
findmnt /boot
lsblk -f
cat /proc/swaps
test ! -e /swapfile
ip -4 route
pgrep dropbear
cat /proc/sys/kernel/random/boot_id
```

Expect encrypted LVM/ext4 root, ext4 boot, no swap and no initramfs Dropbear.
Reboot the same disk, repeat unlock/audit and compare boot IDs.

## Recovery and limitations

- Stuck at identity pause: gather/verify keys before touching the continue file.
- Unreachable unlock SSH: inspect VNC NIC/DHCP/route and provider TCP2222 rules;
  local VNC unlock can restore normal OS for diagnosis. Never bypass SSH trust.
- GRUB cannot find installer: boot the original Debian entry and recover; inspect
  independent `/boot` staging, not repeated blind reinstalls. Encrypted-mode CLI
  now stages installer artifacts on separate unencrypted `/boot` when present.
- Rescue/new identity: authenticate its public fingerprint via provider console
  before accessing the disk; do not silently replace known_hosts.

Encrypted helpers/preseed come from the adjacent checkout. Optional remote
logviewer is disabled and FRPC refused in encrypted mode; legacy ordinary-mode
behavior is not rewritten. No general provider/network certification is implied.
Development was assisted by Hermes Agent; repository Git identity is unchanged.
