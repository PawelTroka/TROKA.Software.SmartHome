# Shinobi recovery

The Shinobi service is declared in `docker-compose.yaml` with an immutable
image digest. Its runtime database, camera credentials, administrator account,
and recordings are intentionally excluded from Git.

## State that is not stored in Git

- `/app/homeserver/shinobi/App` — installed Shinobi application state and
  configuration.
- `/app/homeserver/shinobi/Database` — the embedded MariaDB data.
- `/media/storage/private/surveillance/shinobi-videos` — recordings.
- `/app/homeserver/.codex-backups/20260821-shinobi-bootstrap/super-credentials.txt`
  — current superuser and normal administrator credentials; mode `0600`.

Keep these paths in an encrypted, off-host backup. Never copy camera or account
passwords into Compose or this repository.

The 2026-08-21 clean rebuild also left a verified pre-account/monitor backup at
`/app/homeserver/.codex-backups/20260821-shinobi-pre-admin-monitors` containing
the configuration, superuser file, and a consistent compressed MariaDB dump.

## Current monitor inventory

| Monitor ID | Name | Address | Main stream | Transport |
| --- | --- | --- | --- | --- |
| `hallway` | Hallway | `192.168.1.96:554` | `/h264Preview_01_main` | RTSP/TCP |
| `livingroom` | Living room | `10.10.10.109:554` | `/h264Preview_01_main` | RTSP/TCP |

Both monitors record by copying the H.264/AAC source into MP4, use 15-minute
segments with two-day retention, and provide an HLS live view. The same cameras
also expose `/h264Preview_01_sub` at 640x480 when a lower-bandwidth stream is
needed. Runtime credentials were sourced from Home Assistant's Reolink config
entries and are not tracked.

Do not restore the obsolete monitor entries unless the hardware is brought
back online. At the rebuild date the former Wyze cameras at `10.10.10.49` and
`10.10.10.51`, and the front-door Reolink at `10.10.10.101`, had been offline
for months or years. Ring and EZVIZ cloud cameras did not expose a verified
local RTSP stream.

## Restore outline

1. Clone this repository to `/app/homeserver` and restore the ignored Shinobi
   application, database, credential file, and recording paths from the same
   backup generation.
2. Recreate the external `traefik_proxy` network and validate Compose:

   ```sh
   docker compose config --quiet
   ```

3. Start Shinobi and wait for MariaDB/application initialization:

   ```sh
   docker compose up -d shinobi
   docker compose logs --tail=100 shinobi
   ```

4. Sign in at `https://nvr.troka.software/` using the normal administrator from
   the mode-`0600` credential file. Use `/super` only for system administration.
5. Confirm there is one normal administrator and exactly the two intended
   monitors. Verify that each monitor has a live HLS view and a growing MP4
   recording, then restart the container once and repeat the checks.

The clean rebuild was validated after a container restart: both replacement
credentials authenticated, the old exposed credentials failed, one normal
administrator and two monitors persisted, and both cameras resumed live HLS
and recording.
