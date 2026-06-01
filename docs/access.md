# Access Model

## SSH

Current SSH aliases:

- `pi-tylos`
- `pi-phobetor`

## Admin users

| Node | Admin user | Sudo | Notes |
|---|---|---|---|
| `pi-tylos` | `leandroian` | yes | Main services node |
| `pi-phobetor` | `leandroian` | yes | Migrated away from direct root login |

## Authentication policy

- SSH public key authentication is enabled.
- Password authentication remains enabled during the early setup phase.
- Direct root SSH login should be disabled.
- Daily administration should be done through normal users with `sudo`.
