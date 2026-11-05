# Filament Tracker server

The FastAPI server for Filament Tracker. See the [repository README](../README.md) for the project overview and [AGENTS.md](../AGENTS.md) for the build and test commands.

## Run it

From `server/`, set an admin token and start the server. It creates and migrates its SQLite database in `data/` on startup.

```powershell
$env:ADMIN_TOKEN = "choose-a-long-random-value"
uv run uvicorn filament_tracker.main:create_app --factory
```

The API is under `http://localhost:8000/api/v1`, with interactive docs at `http://localhost:8000/docs`. The docs, the scanner routes and bearer tokens (device and admin) work only from the LAN (`TRUSTED_NETWORKS`, by default the private address ranges); from anywhere else they get 404 or 403.

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

The session cookie is marked Secure, so over plain HTTP set `$env:COOKIE_SECURE = "false"` before starting the server (development only). Requests that change something with the cookie must send the `X-Requested-With: filament-tracker` header. Five failed sign-ins for one username, or twenty from one address, within 15 minutes give HTTP 429.

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
