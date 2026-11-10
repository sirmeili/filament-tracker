# Deploying Rollcall with Docker

Rollcall runs as one container on an x86-64 Linux server with Docker and Docker Compose. The image is `ghcr.io/sirmeili/rollcall`, private, built and published by GitHub Actions on every merge to `main` (tags `latest` and the commit SHA). It holds the server and the built web app, runs as an unprivileged user (uid 10001), and keeps everything it writes on two volumes: the database and the nightly backups.

## What you need

- A Linux server with an x86-64 CPU, Docker Engine and the Compose plugin (`docker compose version` shows v2 or later).
- A GitHub personal access token (classic) with only the `read:packages` scope, to pull the private image. Make it under GitHub › Settings › Developer settings › Personal access tokens. It is used only for `docker login` on the server.
- The server's address on your LAN, and the range of your LAN (for example `192.168.1.0/24`).

## 1. Log in to the registry

On the server, once:

```sh
docker login ghcr.io --username sirmeili
```

Paste the token when asked for the password. Docker keeps it in `~/.docker/config.json`; only the user that runs `docker compose` needs it.

## 2. Get the Compose file and settings

```sh
sudo mkdir -p /opt/rollcall && sudo chown "$USER" /opt/rollcall && cd /opt/rollcall
curl -fsSLO https://raw.githubusercontent.com/sirmeili/rollcall/main/deploy/compose.yaml
curl -fsSL -o .env https://raw.githubusercontent.com/sirmeili/rollcall/main/deploy/.env.example
chmod 600 .env
```

Edit `.env`. At least:

- `TRUSTED_NETWORKS`: your LAN only, such as `192.168.1.0/24`. Bearer tokens (scanners, the phone app, Home Assistant), the API docs and first-start setup work only from here. The default allows every private range, which includes Docker's own networks, so narrow it.
- `SETTINGS_KEY`: recommended. It encrypts the secrets saved in the app (Home Assistant password and token, printer access codes, the tag key constant). Set here, it is not stored on the data volume, so a copy of the volume or a backup does not hold it. Keep a copy somewhere safe, such as a password manager. Generate one with:

  ```sh
  python3 -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
  ```

- `COOKIE_SECURE`: `true` when you sign in through the HTTPS reverse proxy. To sign in over plain HTTP on the LAN (`http://server:8000`), for example before the proxy is ready, set `false`; browsers drop secure cookies over plain HTTP, so signing in would not stick.
- `TZ` and `BAMBU_KDF_SALT`: optional. Setup asks for them if they are not set here.
- Home Assistant and printer settings: optional, and easier to enter in the app later. Use IP addresses, not `.local` names, which the container may not resolve.

## 3. Start it

```sh
docker compose pull
docker compose up -d
docker compose ps        # STATUS shows "healthy" after a few seconds
docker compose logs rollcall | grep "setup code"
```

The last line shows this start's setup code, like `K7QM-X3RD-9PTA`. A new one is made at every start until setup is done.

## 4. First-start setup

From a computer on the LAN, open `http://<server>:8000` (with `COOKIE_SECURE=false`) or the HTTPS address through your proxy, if it is set up and your computer is on the LAN. The web app shows **Set up** instead of sign-in. Enter the setup code, the first Admin's username and password, and the time zone and tag key constant if asked. Setup signs you in and closes for good.

Five wrong codes in 15 minutes lock setup for a while; restarting the container (`docker compose restart`) clears that and makes a new code. If you ever lose every Admin account, reset one from the server:

```sh
docker compose exec rollcall ft-admin reset-password <username>
```

## 5. The reverse proxy

To use the web app away from home, put it behind your HTTPS reverse proxy (Caddy, Nginx Proxy Manager, Traefik or a Cloudflare Tunnel) pointing at `http://<server>:8000`.

- Set `FORWARDED_ALLOW_IPS` in `.env` to the proxy's address as Rollcall sees it, then `docker compose up -d`. Without it, every visitor through the proxy looks like the proxy; if the proxy is on your LAN or in Docker, they would all look local.
  - A proxy on another machine: that machine's LAN address.
  - A proxy in Docker on the same server: its container address, fixed on a network it shares with Rollcall (see [A Cloudflare Tunnel](#a-cloudflare-tunnel) for the steps, which suit any proxy in Docker). Check with `docker compose logs rollcall`, where each request line starts with the address it came from.
- Keep `COOKIE_SECURE=true` once you sign in through the proxy.
- Forward only `/` and `/api/v1`. Rollcall refuses the scanner routes, bearer tokens, `/docs` and setup from outside `TRUSTED_NETWORKS` anyway.

Check it from outside your LAN (for example a phone on mobile data): the web app loads and you can sign in, while `https://<your address>/api/v1/setup` and `/docs` answer 404.

### A Cloudflare Tunnel

With a Cloudflare Tunnel, `cloudflared` is the proxy. Run it in Docker on the same server and give it a fixed address on a network it shares only with Rollcall, so that address can be put in `FORWARDED_ALLOW_IPS`.

Do not trust the address Rollcall sees when the tunnel points at the server's published port (`http://<server>:8000`): that is the gateway of `cloudflared`'s Docker network, such as `172.27.0.1`, and every container on that network arrives from it too, so any of them could claim any visitor address. Nor trust a whole Docker range such as `172.16.0.0/12`.

1. Make the shared network, once (in Portainer: Networks › Add network, driver `bridge`, subnet `172.30.0.0/24`, gateway `172.30.0.1`). Pick another range if this one is in use, and change the addresses below to match.

   ```sh
   docker network create --subnet 172.30.0.0/24 --gateway 172.30.0.1 rollcall-tunnel
   ```

2. Give `cloudflared` a fixed address on it. Keep any networks it already uses for other services:

   ```yaml
   services:
     cloudflared:
       image: cloudflare/cloudflared:<version>
       command: tunnel --no-autoupdate run --token ${token}
       restart: unless-stopped
       networks:
         rollcall-tunnel:
           ipv4_address: 172.30.0.10

   networks:
     rollcall-tunnel:
       external: true
       name: rollcall-tunnel
   ```

3. Add Rollcall to the network. It needs no fixed address. Keep `default` in the list, or the service leaves its own network:

   ```yaml
   services:
     rollcall:
       # ...as in compose.yaml...
       networks:
         - default
         - rollcall-tunnel

   networks:
     rollcall-tunnel:
       external: true
       name: rollcall-tunnel
   ```

4. In the settings, set `FORWARDED_ALLOW_IPS=172.30.0.10` and `COOKIE_SECURE=true`, then restart Rollcall (`docker compose up -d`, or Update the stack in Portainer).
5. In the Cloudflare dashboard (Zero Trust › Networks › Tunnels › the tunnel › Public Hostname), point the hostname at `http://rollcall:8000`. `cloudflared` finds Rollcall by name on the shared network.
6. Recommended: put the hostname behind Cloudflare Access, so only the people you allow reach the sign-in page. Rollcall's own checks still apply behind it.

Then check:

- Open the site through the tunnel; the newest request lines in Rollcall's log start with `172.30.0.10`. If they show another address, the tunnel still goes through the published port (step 5).
- From outside your LAN (a phone on mobile data), `https://<hostname>/api/v1/setup` and `/docs` answer 404 (`{"detail":"Not Found"}`). From the LAN, `http://<server>:8000/api/v1/setup` answers `{"open": false, ...}`.
- Signing in through the `https://` hostname stays signed in after a reload.

With `COOKIE_SECURE=true`, sign in to the web app through the `https://` hostname, at home too: browsers drop the sign-in cookie on `http://<server>:8000`. The phone app, scanners and Home Assistant keep using `http://<server>:8000` on the LAN with their tokens. The name `rollcall` resolves only inside Docker; to use a name on the LAN, add a DNS entry for the server on your router.

## 6. Scanners, the phone app and Home Assistant

- **Phone app and scanners**: on the Devices page, register a scanner and pair the phone with its QR code, using `http://<server>:8000` as the server address. Scanners stay on the LAN.
- **Printers**: add them on the Devices page (or seed them once with `PRINTERS`).
- **Home Assistant**: enter the broker and Home Assistant settings on the Settings page, and make a machine token there for any script or automation that calls the API.

## With Portainer instead

Steps 1 to 4 work the same in Portainer, through its web UI:

- **Registry**: Registries › Add registry › Custom registry, with URL `ghcr.io`, authentication on, username `sirmeili` and the `read:packages` token as the password.
- **Stack**: Stacks › Add stack › Web editor, and paste `deploy/compose.yaml`. Change `env_file: .env` to `env_file: stack.env`: Portainer writes the stack's environment variables to `stack.env`, not `.env`. Add the settings from step 2 under Environment variables (Load variables from .env file accepts a filled-in copy of `.env.example`), then Deploy the stack.
- **Setup code**: Containers › rollcall › Logs, and search for `setup code`.
- **Commands** such as `ft-admin backup` or `ft-admin reset-password <username>`: Containers › rollcall › Console, with `/bin/sh`.
- **Changing a setting**: edit it under the stack's Environment variables, then Update the stack.
- **Updating**: make a backup from the Console, then Stacks › rollcall › Update the stack with Re-pull image turned on.
- **Restoring a backup** needs a shell on the server for the `docker run` command below; stop the stack from Portainer first and start it again afterwards.

## Backups

Every night at 03:00 in the server's time zone, Rollcall copies its database to the backup volume with SQLite's online backup, and keeps the newest 14. Files are named by their UTC time, like `filament-20261110T090000Z.db`. A failed backup is logged and tried again the next night.

```sh
docker compose exec rollcall ls -l /backups          # list them
docker compose exec rollcall ft-admin backup          # make one now, e.g. before an upgrade
docker compose cp rollcall:/backups ./backups-copy    # copy them off the server
```

The backup volume is a Docker volume on the same disk by default. To keep backups on another disk, change `rollcall-backups:/backups` in `compose.yaml` to a path, such as `/mnt/backup/rollcall:/backups`, owned by uid 10001 (`sudo chown 10001:10001 /mnt/backup/rollcall`).

Backups never contain the settings key. With `SETTINGS_KEY` in `.env`, keep `.env` (or the key) safe as well. Without it, the key is `/data/settings.key` on the data volume; copy it once with `docker compose cp rollcall:/data/settings.key ./settings.key` and store it apart from the backups. A backup restored without its key keeps everything except the saved secrets, which the Settings page then asks for again.

### Restoring a backup

```sh
cd /opt/rollcall
docker compose exec rollcall ls /backups      # choose one, e.g. filament-20261110T090000Z.db
docker compose stop rollcall
docker run --rm --user 10001 --entrypoint sh \
  -v rollcall-data:/data -v rollcall-backups:/backups ghcr.io/sirmeili/rollcall:latest \
  -c 'mkdir -p /data/before-restore && mv /data/filament.db* /data/before-restore/ && cp /backups/filament-20261110T090000Z.db /data/filament.db'
docker compose start rollcall
```

The database that was replaced is kept in `/data/before-restore/`. The server upgrades a restored database from an older version on start.

## Updating

```sh
cd /opt/rollcall
docker compose exec rollcall ft-admin backup
docker compose pull
docker compose up -d
```

The server upgrades the database on start. To go back to an earlier image, set `ROLLCALL_TAG` in `.env` to that commit's SHA and run `docker compose up -d`; a database already upgraded by a newer version may need the backup made before the update.

## Logs and health

- `docker compose logs -f rollcall` shows requests, warnings and errors. The setup code appears there while setup is open. Passwords, tokens, access codes and the salt never do.
- `docker compose ps` shows the health check, which asks `/api/v1/health` every 30 seconds. The same address reports the Home Assistant links.

## How the image is built and checked

- `Dockerfile` at the repository root: Node 24 builds the web app (with npm 11.21.2, whose bundled packages have no known advisories), `uv` installs the server's locked dependencies, and the final image is `python:3.12-slim` with Debian's security updates applied when it is built.
- Base images are pinned by digest. To update one, pull the new tag, scan it (for example `docker scout cves --only-severity critical,high <image>`), and change the digest in `Dockerfile`.
- `deploy/test/compose.yaml` is the end-to-end test stack: the image with a Mosquitto broker. GitHub Actions runs `server/tests/deploy/test_compose_stack.py` against it on every pull request (first-start setup, the scan simulator driving Received, Opened and Empty, Home Assistant totals updating on the broker, a backup, and a restart). To run it locally from the repository root:

  ```sh
  docker build -t rollcall:test .
  cd server && FT_COMPOSE_STACK=1 uv run pytest tests/deploy --no-cov
  ```
