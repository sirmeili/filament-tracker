# Deploying RollCall with Docker

RollCall runs as one container on an x86-64 Linux server with Docker and Docker Compose. The image is `ghcr.io/sirmeili/rollcall`, private, built and published by GitHub Actions on every merge to `main` (tags `latest` and the commit SHA). It holds the server and the built web app, runs as an unprivileged user (uid 10001), and keeps everything it writes on two volumes: the database and the nightly backups.

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

- Set `FORWARDED_ALLOW_IPS` in `.env` to the proxy's address as RollCall sees it, then `docker compose up -d`. Without it, every visitor through the proxy looks like the proxy; if the proxy is on your LAN or in Docker, they would all look local.
  - A proxy on another machine: that machine's LAN address.
  - A proxy in Docker on the same server: its container address, fixed on a network it shares with RollCall (see [A Cloudflare Tunnel](#a-cloudflare-tunnel) for the steps, which suit any proxy in Docker). Check with `docker compose logs rollcall`, where each request line starts with the address it came from.
- Keep `COOKIE_SECURE=true` once you sign in through the proxy.
- Forward only `/` and `/api/v1`. RollCall refuses the scanner routes, bearer tokens, `/docs` and setup from outside `TRUSTED_NETWORKS` anyway.

Check it from outside your LAN (for example a phone on mobile data): the web app loads and you can sign in, while `https://<your address>/api/v1/setup` and `/docs` answer 404.

### A Cloudflare Tunnel

With a Cloudflare Tunnel, `cloudflared` is the proxy. Run it in Docker on the same server and give it a fixed address on a network it shares only with RollCall, so that address can be put in `FORWARDED_ALLOW_IPS`.

Do not trust the address RollCall sees when the tunnel points at the server's published port (`http://<server>:8000`): that is the gateway of `cloudflared`'s Docker network, such as `172.27.0.1`, and every container on that network arrives from it too, so any of them could claim any visitor address. Nor trust a whole Docker range such as `172.16.0.0/12`.

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

3. Add RollCall to the network. It needs no fixed address. Keep `default` in the list, or the service leaves its own network:

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

4. In the settings, set `FORWARDED_ALLOW_IPS=172.30.0.10` and `COOKIE_SECURE=true`, then restart RollCall (`docker compose up -d`, or Update the stack in Portainer).
5. In the Cloudflare dashboard (Zero Trust › Networks › Tunnels › the tunnel › Public Hostname), point the hostname at `http://rollcall:8000`. `cloudflared` finds RollCall by name on the shared network.
6. Recommended: put the hostname behind Cloudflare Access, so only the people you allow reach the sign-in page. RollCall's own checks still apply behind it.

Then check:

- Open the site through the tunnel; the newest request lines in RollCall's log start with `172.30.0.10`. If they show another address, the tunnel still goes through the published port (step 5).
- From outside your LAN (a phone on mobile data), `https://<hostname>/api/v1/setup` and `/docs` answer 404 (`{"detail":"Not Found"}`). From the LAN, `http://<server>:8000/api/v1/setup` answers `{"open": false, ...}`.
- Signing in through the `https://` hostname stays signed in after a reload.

With `COOKIE_SECURE=true`, browsers drop the sign-in cookie on `http://<server>:8000`, so sign in through the `https://` hostname. Without the next section, that sends you through Cloudflare even at home. Scanners and Home Assistant keep using `http://<server>:8000` on the LAN with their tokens. The name `rollcall` resolves only inside Docker.

### HTTPS at home with Traefik and split DNS

To reach the same `https://` hostname directly at home, run a reverse proxy on the LAN with a certificate for it, and have your home DNS answer the hostname with the server's LAN address ("split DNS"). Away from home, public DNS still sends it to Cloudflare. The same address then works everywhere, with one sign-in, and home traffic never leaves the house. These steps use Traefik v3 on the same server, with a Let's Encrypt wildcard certificate for every service behind it (`*.example.com`), obtained through Cloudflare's DNS so nothing needs to be open to the internet.

1. In Cloudflare (My Profile › API Tokens › Create Token › *Edit zone DNS*), make an API token for your zone only. Give it to Traefik as the `CF_DNS_API_TOKEN` environment variable (in Portainer, the stack's environment variables), never in a file in a repository.
2. Add to Traefik's compose file (static configuration as command flags):

   ```yaml
   services:
     traefik:
       image: traefik:v3.x          # a current v3 release
       command:
         - --providers.docker
         - --providers.docker.exposedbydefault=false
         - --entrypoints.http.address=:80
         - --entrypoints.https.address=:443
         - --entrypoints.https.http.tls.certresolver=cloudflare
         - --entrypoints.https.http.tls.domains[0].main=example.com
         - --entrypoints.https.http.tls.domains[0].sans=*.example.com
         - --certificatesresolvers.cloudflare.acme.email=you@example.com
         - --certificatesresolvers.cloudflare.acme.storage=/letsencrypt/acme.json
         - --certificatesresolvers.cloudflare.acme.dnschallenge.provider=cloudflare
         - --certificatesresolvers.cloudflare.acme.dnschallenge.resolvers=1.1.1.1:53,1.0.0.1:53
       environment:
         - CF_DNS_API_TOKEN=${CF_DNS_API_TOKEN}
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock:ro
         - letsencrypt:/letsencrypt
       networks:
         rollcall-tunnel:
           ipv4_address: 172.30.0.20

   networks:
     rollcall-tunnel:
       external: true
       name: rollcall-tunnel

   volumes:
     letsencrypt:
   ```

   - Both the service's `letsencrypt:/letsencrypt` line and the top-level `volumes:` block are needed. Without the folder, Traefik logs `open /letsencrypt/acme.json: no such file or directory` and gets no certificate.
   - `exposedbydefault=false` stops Traefik from routing every container (and logging `port is missing` for the ones without a web port). Each service you reach through Traefik then needs the `traefik.enable=true` label.
   - The wildcard covers one level of subdomains. Its private key, in `acme.json`, is valid for all of them: keep the volume private.
3. Add labels to the `rollcall` service:

   ```yaml
       labels:
         - traefik.enable=true
         - traefik.docker.network=rollcall-tunnel
         - traefik.http.routers.rollcall.rule=Host(`rollcall.example.com`)
         - traefik.http.routers.rollcall.entrypoints=https
         - traefik.http.services.rollcall.loadbalancer.server.port=8000
   ```

4. Trust both proxies: `FORWARDED_ALLOW_IPS=172.30.0.10,172.30.0.20`, then restart RollCall.
5. Check Traefik's log for the certificate (errors mention `acme` or `cloudflare`), or its dashboard's HTTP Routers.
6. Only then add the local DNS entry: `rollcall.example.com` → the server's LAN address, as a Host (A) record. On UniFi Network: Settings › Policy Engine › Policy Table › Create New Policy › DNS (9.x), or Settings › Routing › DNS (8.x). Each network's DHCP must hand out the gateway as its DNS server (DNS Server: Auto). Add one entry per service rather than a DNS wildcard, which would also capture subdomains Traefik does not serve.

Then check from the LAN:

- `nslookup rollcall.example.com` answers with the server's LAN address.
- `https://rollcall.example.com` opens with a valid certificate and no Cloudflare Access sign-in, and its request lines in RollCall's log start with `172.30.0.20`.
- `https://rollcall.example.com/api/v1/setup` answers `{"open": false, ...}`: RollCall sees your LAN address through Traefik.

Devices that skip your home DNS (Android's Private DNS, or a browser's secure DNS set to a fixed provider) still work, through Cloudflare. Pair the phone app with the `https://` hostname: at home its scans reach RollCall through Traefik with the phone's LAN address, and away from home its pages come through the tunnel.

### The phone app behind Cloudflare Access

The phone app cannot use Cloudflare Access's sign-in page, so it passes Access with a service token instead. RollCall keeps one token for all phones and hands it to each one on your home network; nobody types it on a phone. RollCall's own sign-in still applies behind it.

1. In Cloudflare Zero Trust, under Access (Service Auth, or Service credentials in newer dashboards) › Service Tokens, create a token, for example "RollCall phones", with the duration you want (a year is the default). Copy the Client ID and the Client Secret: the secret is shown only once.
2. On the RollCall application in Access, add a policy with the action **Service Auth** that includes that service token. Keep your existing Allow policy for people.
3. In RollCall, on the Settings page under Scanners, enter the Client ID and the Client Secret, and Save. The secret is stored encrypted and never shown again.
4. Open the app on each phone once at home. It fetches the token when it opens or comes back to the front and reaches RollCall at home; a phone paired from now on gets it when it pairs.

Then check from a phone on mobile data: the app's pages load (no Access sign-in), and Scan's header shows **Away**. A scan away from home is queued and sent the next time the phone is home: scanning stays on your home network.

To replace the token (or before it expires): make a new one in Cloudflare, add it to the Service Auth policy, save it in RollCall's Settings, and remove the old one from the policy once every phone has been opened at home. A phone that missed the change is let in again the next time it is home. Clearing the two fields in Settings takes the token off the phones the same way.


## 6. Scanners, the phone app and Home Assistant

- **Phone app and scanners**: on the Devices page, register a scanner and pair the phone with its QR code, from home. For the phone, use the `https://` hostname if you set up HTTPS at home (above), so the app works at home and away; otherwise `http://<server>:8000`, which works only at home. Scanners stay on the LAN.
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

Every night at 03:00 in the server's time zone, RollCall copies its database to the backup volume with SQLite's online backup, and keeps the newest 14. Files are named by their UTC time, like `filament-20261110T090000Z.db`. A failed backup is logged and tried again the next night.

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
