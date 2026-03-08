# Deployment Guide (Home Server)

This document explains how to deploy `shoes-storage` on a home server.

Use placeholders and replace them with your own values:
- `<SERVER_USER>`
- `<APP_DIR>`
- `<DOMAIN_OR_IP>`
- `<APP_PORT>` (internal app port, e.g. `8001`)
- `<PUBLIC_PORT>` (external port, e.g. `8081`)

## 1. Prerequisites

On the server, install:
- `python3`
- `python3-venv`
- `git`
- `nginx` (optional, recommended)

## 2. Copy project

```bash
sudo -u <SERVER_USER> mkdir -p <APP_DIR>
sudo -u <SERVER_USER> git clone <REPO_URL> <APP_DIR>
cd <APP_DIR>
```

If you deploy by copying files instead of git, place the project at `<APP_DIR>`.

## 3. Environment config

Create `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```env
OPENROUTER_API_KEY=<YOUR_OPENROUTER_API_KEY>
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
SITE_URL=http://<DOMAIN_OR_IP>:<PUBLIC_PORT>
SITE_NAME=Shoes Storage
PORT=<APP_PORT>
```

Notes:
- `PORT` is used by `server.py`.
- `SITE_URL` should match the real public URL users open.

## 4. First run (manual smoke test)

```bash
cd <APP_DIR>
python3 server.py
```

Open:
- `http://<DOMAIN_OR_IP>:<APP_PORT>` (direct)

Stop with `Ctrl+C` after smoke test.

## 5. Run as systemd service (recommended)

Create unit file:

```bash
sudo tee /etc/systemd/system/shoes-storage.service > /dev/null <<'UNIT'
[Unit]
Description=Shoes Storage Service
After=network.target

[Service]
Type=simple
User=<SERVER_USER>
WorkingDirectory=<APP_DIR>
EnvironmentFile=<APP_DIR>/.env
ExecStart=/usr/bin/python3 <APP_DIR>/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable shoes-storage
sudo systemctl start shoes-storage
sudo systemctl status shoes-storage
```

Logs:

```bash
journalctl -u shoes-storage -f
```

## 6. Nginx reverse proxy (port 80 already occupied)

You said another service already uses port `80`. You have 2 practical options.

### Option A: expose this app on another public port (fastest)

Create Nginx server on `<PUBLIC_PORT>` (example `8081`):

```nginx
server {
    listen <PUBLIC_PORT>;
    server_name <DOMAIN_OR_IP>;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:<APP_PORT>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable config and reload Nginx.

Then use:
- `http://<DOMAIN_OR_IP>:<PUBLIC_PORT>`

### Option B: keep public port 80 but route by host/path

Only possible if you control the existing Nginx on `80`.

Examples:
- dedicated host: `shoes.<your-domain>`
- path prefix on existing host: `/shoes/`

If this is needed, merge proxy rules into existing 80/443 config instead of creating a new listener.

## 7. Firewall

Open only required ports:
- internal app port `<APP_PORT>` should stay private (localhost only preferred)
- public port `<PUBLIC_PORT>` if using Option A

Example with UFW:

```bash
sudo ufw allow <PUBLIC_PORT>/tcp
sudo ufw status
```

## 8. Update procedure

```bash
cd <APP_DIR>
git pull
sudo systemctl restart shoes-storage
sudo systemctl status shoes-storage
```

## 9. Health checks

```bash
curl -sS http://127.0.0.1:<APP_PORT>/api/health
curl -sS http://127.0.0.1:<APP_PORT>/api/config
```

Expected:
- `/api/health` -> `{ "ok": true, ... }`
- `/api/config` -> `openrouter_enabled: true` when API key is configured

## 10. Data and backup

SQLite DB file:
- `<APP_DIR>/data/shoes.db`

Backup example:

```bash
cp <APP_DIR>/data/shoes.db <APP_DIR>/data/shoes-$(date +%F).db.bak
```

Restore by replacing `shoes.db` while service is stopped.

## 11. Common issues

- `PermissionError` on bind: selected `PORT` is busy or blocked. Change `PORT`.
- AI not working: check `OPENROUTER_API_KEY` and outbound internet access.
- Large photo uploads failing via Nginx: increase `client_max_body_size`.
- Tab UI works but stale styles/scripts loaded: hard refresh browser cache.
