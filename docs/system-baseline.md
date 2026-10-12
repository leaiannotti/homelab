# System Baseline

## Base packages

Installed on:

- `pi-tylos`
- `pi-phobetor`

Packages:

- curl
- wget
- git
- htop
- btop
- tmux
- ufw
- ca-certificates
- gnupg
- lsb-release

## Useful checks

### System info

```bash
hostnamectl
uname -a
uptime

### Resources

free -h
df -h
btop

### Services

systemctl status ssh
systemctl list-units --type=service --state=running

### Logs

journalctl -p 3 -xb
journalctl -u ssh --since "1 hour ago"
