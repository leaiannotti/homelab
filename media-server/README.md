# Media Server — Raspberry Pi 8GB (pi-tylos)

## Arquitectura

```
Telegram  ──►  CineBot (Python)  ──►  Radarr / Sonarr
                                       │
                                       ▼
                                   qBittorrent  ──►  /data/downloads/
                                       │
                                       ▼
                                   Plex  ──►  /data/media/movies/
                                               /data/media/tv/

Kodi ── HDMI ──► TV (UI estilo Netflix, control remoto vía CEC)
```

| Servicio | URL | Puerto |
|---|---|---|
| Plex | http://pi-tylos:32400/web | 32400 |
| Radarr | http://pi-tylos:7878 | 7878 |
| Sonarr | http://pi-tylos:8989 | 8989 |
| qBittorrent | http://pi-tylos:8080 | 8080 |
| Prowlarr | http://pi-tylos:9696 | 9696 |
| Open-WebUI (Ollama) | http://pi-tylos:3000 | 3000 |
| Kodi | HDMI | — |

## CineBot — Comandos

| Comando | Acción |
|---|---|
| `/search inception` | Buscar película |
| `/tv breaking bad` | Buscar serie |
| `/person tarantino` | Buscar actor/director |
| `/status` | Cola de descargas |
| `/help` | Ayuda |

### Flujos

**Películas:**
`/search` → elegir resultado → poster + detalles + cast → **Ver Cast** → director + actores con botones → **bio** del actor → **Buscar películas** / **Buscar series** → elegir → **Agregar a Radarr**

**Series:**
`/tv` → elegir resultado → detalles → **Agregar a Sonarr (completa)** o **Temporadas** (elegir T1, T2...) o **Ver Cast** (directores + actores)

**Actor/Director:**
`/person` → elegir persona → bio (fecha, lugar) → **Buscar películas** o **Buscar series** (con paginación "Mostrar más")

## Deploy — Ansible (recomendado)

```bash
cd ansible
# 1. Completar vars/main.yml con tokens
# 2. Ejecutar
ansible-playbook -i ../../inventory/hosts.ini deploy-media-server.yml
```

## Deploy — Manual

```bash
# 1. Datos
sudo mkdir -p /data/{media/{movies,tv},downloads}
sudo chown -R $USER:$USER /data

# 2. Config
cp .env.example .env
# Editar .env con tokens

# 3. Stack
DATA_ROOT=/data docker compose up -d

# 4. Bot
cd bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
sudo systemctl enable --now cinebot  # o venv/bin/python -m bot.main
```

## Post-configuración manual (una sola vez)

1. **Plex claim** — https://plex.tv/claim → poner en `.env` → `docker compose restart plex`
2. **qBittorrent password** — http://pi-tylos:8080 → Tools → Options → Web UI → setear password
3. **Radarr/Sonarr** — ya configurados vía API con qBittorrent como download client
4. **Prowlarr** — http://pi-tylos:9696 → agregar indexers → conectar a Radarr y Sonarr

## Estructura del proyecto

```
media-server/
├── docker-compose.yml       # Plex + Radarr + Sonarr + qBittorrent + Prowlarr
├── .env.example
├── .env                     # credenciales (no commitear)
├── config/                  # volúmenes de config por servicio
├── bot/
│   ├── main.py              # entry point
│   ├── config.py            # carga .env
│   ├── handlers/commands.py # handlers de Telegram
│   └── services/
│       ├── tmdb.py          # API de TMDB
│       ├── radarr.py        # API de Radarr
│       └── sonarr.py        # API de Sonarr
├── ansible/
│   ├── deploy-media-server.yml
│   └── roles/media_server/
└── README.md
```

## Estado actual en pi-tylos

| Componente | Estado |
|---|---|
| Docker stack (5 containers) | ✅ Running |
| CineBot (systemd) | ✅ Running |
| Radarr/Sonarr root folders | ✅ /data/media/* |
| Radarr/Sonarr → qBittorrent | ✅ |
| Plex claim | ✅ |
| TMDB API + Telegram token | ✅ |
| Kodi | ✅ Instalado (conectar HDMI) |
| Prowlarr indexers | 🔲 Pendiente |
