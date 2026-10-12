# Access Model

## SSH aliases

- `pi-tylos`
- `pi-phobetor`

## Current policy

- Public key authentication is enabled.
- Password authentication remains enabled as fallback during the early setup phase.
- Direct root SSH login should be disabled.
- Daily administration must use normal users with `sudo`.

## Admin users

| Node | Admin user | Notes |
|---|---|---|
| `pi-tylos` | `leandroian` | Main services node |
| `pi-phobetor` | `leandroian` | Infra/lightweight gateway node |

## Current IPs

| Node | IP | Assignment |
|---|---:|---|
| `pi-tylos` | `192.168.1.17` | DHCP lease, not reserved |
| `pi-phobetor` | `192.168.1.18` | DHCP lease, not reserved |
