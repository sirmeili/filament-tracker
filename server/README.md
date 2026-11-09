# Filament Tracker server

The FastAPI server for Filament Tracker. See the [repository README](../README.md) for the project overview and [AGENTS.md](../AGENTS.md) for the build and test commands.

## Run it

From `server/`, set an admin token and start the server. It creates and migrates its SQLite database in `data/` on startup.

```powershell
$env:ADMIN_TOKEN = "choose-a-long-random-value"
uv run uvicorn filament_tracker.main:create_app --factory
```

This listens on `127.0.0.1` only, so other machines cannot reach it. For scanners and the phone app, which connect over the LAN, add `--host 0.0.0.0`:

```powershell
uv run uvicorn filament_tracker.main:create_app --factory --host 0.0.0.0
```

Settings can also go in `server/.env`; copy [`.env.example`](.env.example), which lists every one. `.env` is never committed.

If the web app has been built (`npm ci` and `npm run build` in `web/`), it is served at `http://localhost:8000/`; set `WEB_DIR` to serve a build from elsewhere. The API is under `http://localhost:8000/api/v1`, with interactive docs at `http://localhost:8000/docs`. The docs, the scanner routes and bearer tokens (device and admin) work only from the LAN (`TRUSTED_NETWORKS`, by default the private address ranges); from anywhere else they get 404 or 403.

## Accounts

The web app has no default account. Create the first Admin from `server/`; the password is prompted, at least 12 characters:

```powershell
uv run ft-admin create-user frank --role admin
```

Admins add more users through the API (`/api/v1/users`) and, later, the Users page. If every Admin is locked out, `uv run ft-admin reset-password <username>` sets a new password and signs that user out everywhere.

To sign in from PowerShell (the browser app comes later in M2):

```powershell
$body = '{"username": "frank", "password": "your password"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -SessionVariable web `
    -Headers @{ "X-Requested-With" = "filament-tracker" } -ContentType application/json -Body $body
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me -WebSession $web
```

The session cookie is marked Secure. Browsers accept it over plain HTTP on `localhost`, but from another machine on the LAN over plain HTTP set `$env:COOKIE_SECURE = "false"` before starting the server (development only). Requests that change something with the cookie must send the `X-Requested-With: filament-tracker` header. Five failed sign-ins for one username, or twenty from one address, within 15 minutes give HTTP 429.

## Behind a reverse proxy

To reach the web app from outside, put it behind an HTTPS reverse proxy and tell the server the proxy's address, so it trusts the proxy's `X-Forwarded-For` header and no one else's:

```powershell
$env:FORWARDED_ALLOW_IPS = "192.168.1.5"   # the proxy
$env:TRUSTED_NETWORKS = "192.168.1.0/24"   # optional: narrow the LAN
```

uvicorn reads the same `FORWARDED_ALLOW_IPS` variable and applies the same rule, so it needs no extra options. Clients coming through the proxy from the internet can sign in and use the web app, but bearer tokens, scanner routes and the API docs are refused for them. Forward only the web app and `/api/v1` from the proxy anyway.

## Register a scanner

Every scanner, including the simulator, needs its own token. Register one with the admin token; the token in the reply is shown only once.

```powershell
$headers = @{ Authorization = "Bearer $env:ADMIN_TOKEN" }
$device = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/devices `
    -Headers $headers -ContentType application/json -Body '{"id": "simulator", "name": "Simulator"}'
$env:FT_TOKEN = $device.token
$env:FT_DEVICE_ID = "simulator"
```

To revoke it later: `Invoke-RestMethod -Method Delete -Uri http://localhost:8000/api/v1/devices/simulator -Headers $headers`.

On the Devices page, registering a scanner or rotating its token also offers a QR code for the phone app, holding the server address and the token. The address defaults to the one in the browser and can be changed first.

## Tag key constant

Scanners and the phone app read tags with keys derived from each tag's UID and a published constant. The server keeps the constant in `BAMBU_KDF_SALT` (hex) and hands it to a device at `GET /api/v1/devices/provisioning` (device token, LAN only). It is not generated: it is the constant documented by the Bambu Research Group's RFID-Tag-Guide, and it is never committed. Put it in `.env`, then check it against your own dumps, which still hold the real keys:

```powershell
uv run ft-sim check-salt C:\tag-dumps\*.zip
```

It prints how many of each dump's 16 sector keys the constant reproduces, and nothing else.

## Scan simulator

`ft-sim` sends scans exactly as a scanner would. It reads the server from `FT_SERVER` (default `http://localhost:8000`), the token from `FT_TOKEN` and the device ID from `FT_DEVICE_ID`.

Scan your own tags from BambuTagScanner exports (the ZIP from its Export button, or the `.bin` inside it). Keep dumps outside the repo: they contain tag UIDs and keys. The simulator drops the sector trailers, which hold the keys, before sending, and masks the tag UID in file names it prints.

```powershell
uv run ft-sim scan C:\tag-dumps\roll1.zip                      # lookup: what is this spool?
uv run ft-sim scan C:\tag-dumps\roll1.zip --action received    # New
uv run ft-sim scan C:\tag-dumps\*.zip --action received        # several at once
uv run ft-sim scan C:\tag-dumps\roll1.zip --action opened --at 2026-11-01T09:00:00-05:00
```

Without real dumps, generate synthetic tags. A generated file is one spool: scan the same file again to move it through its life.

```powershell
uv run ft-sim generate black.bin
uv run ft-sim generate white-matte.bin --color FFFFFFFF --detailed-type "PLA Matte"
uv run ft-sim scan black.bin --action opened
```

Each scan prints the feedback code, product, spool number (or "new spool"), state, the three soft-key choices and the suggested action. Add `--json` for the full server response, or `--event-id <uuid>` to resend the same event and test retries. Actions: `lookup` (default), `received`, `opened`, `empty`.

## Printers

The server watches each printer in `PRINTERS` over MQTT and keeps the AMS slots and spools up to date. It is a JSON list; `port` is optional (default 8883):

```powershell
$env:PRINTERS = '[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A123456789", "access_code": "12345678"}]'
```

The access code is on the printer's screen under the network settings. Put `PRINTERS` in `.env` rather than typing it into a shared shell: it holds the access code, and `.env` is never committed.

- **Certificate pin**: on the first connection the server stores the SHA-256 fingerprint of the printer's TLS certificate, and from then on talks only to that certificate. If the printer's certificate changes (for example after a firmware update), the printer shows a pin mismatch and an admin forgets the pin from the Devices page.
- **MQTT proxy**: to stay under the printer's connection limit, point `host` and `port` at a proxy such as `bambu-mqtt-proxy`, and use the proxy's alias as `serial` if it renames the printer. The pin is then the proxy's certificate.

## Home Assistant

The server publishes Home Assistant entities through MQTT discovery, under one device, **Filament Tracker**:

- **Total spools** (sealed and open, not used up), **Total open** and **Total sealed**;
- **Low filament**: on while any product's sealed count is at or below its low-stock threshold (set on the Products page; 0 turns it off). Its `products` attribute lists the low products with their name, type, color, sealed count and threshold, and `count` says how many;
- **Spools in review**: the Review page's count.

Entities from an earlier version of the server (such as per-product sensors) are removed automatically.

Set the broker on the **Settings** page (Admin), or in `server/.env`:

```sh
MQTT_URL=mqtt://homeassistant.local:1883   # Home Assistant's address, for the Mosquitto add-on
MQTT_USER=filament-tracker
MQTT_PASSWORD=...
```

- **The MQTT user**: the Mosquitto add-on accepts Home Assistant users (create one under Settings → People, for example `filament-tracker`) or the logins in the add-on's configuration.
- **Updates**: changes reach Home Assistant within about 5 seconds, whatever made them (a scanner, the phone, the web app or the printer).
- **Unavailable**: while the server is stopped or cannot reach the broker, the entities show as unavailable.
- **Home Assistant restarts**: everything is published again when Home Assistant restarts.
- **Status**: `GET /api/v1/health` reports the link as `off`, `connecting`, `connected` or `disconnected`.

The password is never logged or shown, and `MQTT_URL` must not contain it. Use `mqtts://` for a broker with a certificate the server's system trusts.

### Events for automations

With these set (on the Settings page or in `server/.env`), the server also fires Home Assistant events:

```sh
HA_URL=http://homeassistant.local:8123
HA_TOKEN=...   # a long-lived access token: your Home Assistant profile → Security
```

- `filament_tracker_spool_received`, `filament_tracker_spool_opened` and `filament_tracker_spool_emptied`, for every such action from any source, with the spool, product, type, color, new state, source and time in the event data.
- `filament_tracker_low_stock`, once when a product goes low, with its name, type, color, sealed count and threshold.

Only actions after the server starts are fired (a restart replays nothing), within about 5 seconds. An action undone before then is not fired. A failed request is retried three times and then dropped with a warning in the log; `GET /api/v1/health` reports events as `off`, `ready` or `failing`. The token is never logged, and redirects are not followed so it only goes to `HA_URL`.

To see them, open Developer tools → Events in Home Assistant, listen to `filament_tracker_low_stock` (or another), and record an action.

### The Settings page

Admins can set everything above on the **Settings** page, without restarting the server:

- **Where values come from**: each one is labelled **From .env**, **Saved here** or **Default**. A value saved on the page is used instead of the `.env` one; **Use the .env value** goes back to it. An empty value saved on the page turns that setting off, even if `.env` sets it.
- **Passwords and tokens** are stored encrypted and never shown again. Leave the box empty to keep the saved one; **Clear** removes it.
- **Save** applies at once: the server reconnects to the broker and starts sending events with the new values.
- **Test** tries the values in the boxes (saved or not) once, and says only whether it worked: connected, unreachable, refused or an error.

Secrets are encrypted with a key from `SETTINGS_KEY`, or else from `data/settings.key`, which the server creates beside the database on first start. Back the key up with the database, or set `SETTINGS_KEY` instead, so the key is not stored next to the data it protects. A database restored without its key keeps everything except the saved secrets, which the Settings page then asks for again.

**Example automation**: [docs/home-assistant/low-stock-automation.yaml](../docs/home-assistant/low-stock-automation.yaml) adds a low product to the shopping list and notifies your phone. Paste it into a new automation's YAML editor, set your phone's notify action, save, and give it the `Claude` label.

## Check against Home Assistant

`ft-ha check` compares what the server published with what Home Assistant shows. It uses the settings the server uses (a value saved on the Settings page wins over `server/.env`), reading them from the server's database and key without changing either, so the server can keep running.

```powershell
uv run ft-ha check            # add --event to fire one filament_tracker_check event
```

- **Broker**: connects with the MQTT user, then lists the five discovery messages, any old ones still retained, availability, and the published totals and low filament.
- **Home Assistant**: checks the token, then shows each of the five entities and whether it matches what the broker holds. A value changed in the last few seconds may still be on its way; run it again.
- It prints counts and states only, never the broker or Home Assistant address, the user name, the password or the token. It exits with 1 when anything is marked as a problem.

Checklist before a release that changes the Home Assistant link:

1. `ft-ha check` passes with no problems.
2. In Home Assistant, Settings → Devices & services → Devices shows **Filament Tracker** with its five entities.
3. Record an action (a scan, the phone or the web app): the totals change in Home Assistant within about 5 seconds.
4. Stop the server: the entities show as unavailable. Start it: they come back.
5. Restart Home Assistant: the entities come back with their values without restarting the server.
6. Developer tools → Events, listening to `filament_tracker_spool_opened` (and the others): each action fires one event with the spool, product, color and source. `ft-ha check --event` fires `filament_tracker_check`.
7. Set a product's low-stock threshold to its sealed count: `filament_tracker_low_stock` fires once, Low filament turns on and lists it, and the example automation adds it to the shopping list and notifies the phone. Put the threshold back.
8. On the Settings page, **Test** reports both links working; with a wrong password typed in, it reports the broker refused it. **Save** a change and the link reconnects without a restart.

## Fake printer

Test the printer link without a printer: a Mosquitto broker in Docker stands in for the printer's MQTT server, and `ft-fakeprinter` plays the printer on it. Needs Docker and `openssl`; run from `server/` in Git Bash or WSL for the first command.

```sh
./fakeprinter/make-cert.sh                                  # a throwaway certificate, never committed
docker compose -f fakeprinter/compose.yaml up -d --wait     # TLS on 127.0.0.1:8883, user bblp
```

```powershell
$env:FT_ACCESS_CODE = "fake-access-code"
uv run ft-fakeprinter --serial FAKE01 --report tests\printer\reports\pushall.json --then tests\printer\reports\remain-delta.json
```

It publishes the full report, then each `--then` change every 5 seconds (`--interval`), and answers every `pushall` with the full report until stopped with Ctrl+C. Point the server at it with:

```powershell
$env:PRINTERS = '[{"name": "Fake", "host": "127.0.0.1", "serial": "FAKE01", "access_code": "fake-access-code"}]'
```

The integration tests use the same broker: set `FT_FAKE_BROKER=127.0.0.1:8883` before `uv run pytest` to include them (CI does). The broker also listens for plain MQTT on `127.0.0.1:11883` (change it with `FAKE_HA_BROKER_PORT`), standing in for Home Assistant's broker: set `FT_HA_BROKER=127.0.0.1:11883` to include the Home Assistant broker tests. Stop it with `docker compose -f fakeprinter/compose.yaml down`.

## Check a real printer

`ft-printer check` connects to a printer in `PRINTERS` once and prints what each AMS and AMS HT slot reports. It pins the certificate it finds for that connection only and does not touch the database. Stop the server first if the printer is near its MQTT connection limit.

```powershell
uv run ft-printer check --dump C:\tag-dumps\spool.zip --save captures\p1s.jsonl
```

- `--dump` (one or more tag dumps) says whether each tag's tray UID or UID is what a slot reports. Tags are labelled by position and product, and no UID is printed.
- `--save` writes only the AMS parts of each message, with every tray UUID, tag UID and unit serial replaced. `captures/` is ignored by git; check a capture before using it as a test fixture.

Checklist before a release that changes the printer link:

1. `ft-printer check` lists every loaded slot with its material, color and remaining %, and the AMS HT as "AMS HT 1".
2. With a dump of a loaded spool, it reports that the tray UUID equals the tag's tray UID.
3. Start the server: Devices shows the printer Online with its certificate pinned and every slot.
4. A tagged spool loaded without a scan becomes Open, flagged for Review, and Spool detail shows "Loaded in".
5. Remaining % on Spool detail follows the AMS after a print.
6. Forget pin on Devices; the next connection pins the certificate again.
