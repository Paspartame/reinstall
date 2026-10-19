# Experimental Debian 13 encrypted reinstall

**Disabled: `--encrypt NOT_YET_USABLE`.** Historical local Fork composition passed two unlock boots; the actual public CLI self-reinstall is not yet validated.

Supported design target: Debian 13 amd64, explicit `--installer`, a plain supported SSH public key (`--ssh-key` literal or file; mature URL/username resolver retained), and `--unlock-port` (default 2222). Requires a complete adjacent source checkout, Python 3, OpenSSH key tools and trusted distribution `busybox-static`.

Installer SSH uses the configured normal SSH port. Run `/usr/local/sbin/reinstall-luks-passphrase` in an authenticated PTY to submit and confirm the synthetic/test LUKS passphrase. After reboot, initramfs Dropbear uses the unlock port and a distinct host identity; use a pinned key and `ssh -tt` for interactive `cryptroot-unlock`. Normal OS SSH has its own pinned identity. Do not append newline in raw non-TTY mode: the Debian script copies it as a password byte. Never disable SSH host verification.

No production VPS safety claim or deployment approval. Feature remains guarded until real native CLI E2E and focused release checks pass. Changes were integrated with Hermes Agent assistance; Git identity is the repository's existing configured identity.
