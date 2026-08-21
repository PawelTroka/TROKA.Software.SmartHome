# Nextcloud recovery

The production stack is declared in `docker-compose.yaml` and uses immutable
Nextcloud 34.0.3 and MariaDB 10.11.18 image digests. Nextcloud has its own
database service; it no longer uses the shared `mariadb` container.

## State that is not stored in Git

- `/app/homeserver/nextcloud/html` — installed Nextcloud code, configuration,
  and app code. `config/config.php` contains secrets.
- `/app/homeserver/nextcloud/database-10.11` — the dedicated MariaDB data.
- `/app/homeserver/nextcloud/mariadb.env` — database credentials; mode `0600`.
- `/media/storage/shared_data` — user files.
- `/app/homeserver/.env` — Compose credentials and host-specific values.

Keep those paths in an encrypted, off-host backup. Git intentionally ignores
them.

The 2026-08-21 migration left local rollback material on the server:

- `/app/homeserver/.codex-backups/20260821-nextcloud-v22` — full v22 config,
  database dump, and 182 GiB data snapshot.
- `/app/homeserver/.codex-backups/20260821-nextcloud-ladder` — database/config
  checkpoints for every supported major-version step.
- `/app/homeserver/.codex-backups/20260821-nextcloud-final` — final v34
  database/config/app checkpoint after repairs and index creation.
- `/app/homeserver/.codex-backups/20260821-nextcloud-production` — quiescent,
  Compose-ready v34 checkpoint with the production database hostname and
  current image-managed config fragments.
- stopped container `nextcloud-migration-db-10.5` and bind directory
  `/app/homeserver/nextcloud/database-10.5` — pre-v30 database rollback point.

These local copies are not a substitute for an off-host backup.

## Restore outline

1. Clone this repository to `/app/homeserver` and restore the ignored `.env`,
   `nextcloud/mariadb.env`, `nextcloud/html`, `nextcloud/database-10.11`, and
   `/media/storage/shared_data` from the same backup generation.
2. Make the HTML and data trees writable by the official image's `www-data`
   account (UID/GID 33). Keep `mariadb.env` readable only by its owner.
3. Recreate the external `traefik_proxy` network. Production currently uses
   `172.18.0.0/16`; override `TRAEFIK_PROXY_SUBNET` in `.env` if the restored
   network uses another CIDR.
4. Validate configuration with `docker compose config --quiet`.
5. Start and verify the database, then the web and cron services:

   ```sh
   docker compose up -d nextcloud-db
   docker inspect --format '{{.State.Health.Status}}' nextcloud-db
   docker compose up -d nextcloud nextcloud-cron
   ```

6. Validate the restored instance:

   ```sh
   docker compose exec -T -u 33 nextcloud php occ status --output=json
   docker compose exec -T -u 33 nextcloud php occ integrity:check-core
   curl -fsS https://cloud.troka.software/status.php
   ```

The status response must report `maintenance: false`, `needsDbUpgrade: false`,
and version `34.0.3`. CalDAV and CardDAV discovery URLs must redirect to the
HTTPS `/remote.php/dav/` endpoint.

The production migration was also validated with an authenticated WebDAV
`PROPFIND` and file download through the public URL. The downloaded size and
SHA-256 matched the source file. The temporary app password used for that test
was revoked immediately, leaving no authentication token behind.

Never point an older Nextcloud image at a database that has already been
upgraded. A rollback must restore matching config, database, app code, and user
data from one checkpoint.
