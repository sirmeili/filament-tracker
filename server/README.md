# Filament Tracker server

The FastAPI server for Filament Tracker. See the [repository README](../README.md) for the project overview and [AGENTS.md](../AGENTS.md) for the build and test commands.

## Run it

From `server/`, set an admin token and start the server. It creates and migrates its SQLite database in `data/` on startup.

```powershell
$env:ADMIN_TOKEN = "choose-a-long-random-value"
uv run uvicorn filament_tracker.main:create_app --factory
```

The API is under `http://localhost:8000/api/v1`, with interactive docs at `http://localhost:8000/docs`.

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
