#!/usr/bin/env bash
set -Eeuo pipefail

# Consistent local recovery copy for the standalone MariaDB container. This is
# deliberately stored on the healthier root filesystem, not the nearly-full
# mergerfs media pool. Off-host replication is still required for disaster
# recovery.
backup_root=${MARIADB_BACKUP_DIR:-/app/homeserver/.automatic-backups/mariadb}
retention_days=${MARIADB_BACKUP_RETENTION_DAYS:-14}

if [[ "$backup_root" != "/app/homeserver/.automatic-backups/mariadb" ]]; then
  printf 'Refusing unexpected backup destination: %s\n' "$backup_root" >&2
  exit 2
fi

install -d -m 0700 -- "$backup_root"
exec 9>"$backup_root/.backup.lock"
flock -n 9 || exit 0

timestamp=$(date --utc +%Y%m%dT%H%M%SZ)
final="$backup_root/mariadb-all-$timestamp.sql.gz"
temp=$(mktemp --tmpdir="$backup_root" ".mariadb-all-$timestamp.tmp.XXXXXX")

cleanup() {
  rm -f -- "$temp"
}
trap cleanup EXIT INT TERM

[[ $(docker inspect --format '{{.State.Running}}' mariadb 2>/dev/null) == true ]]
docker exec mariadb test -r /run/mariadb-logrotate.cnf
docker exec mariadb mariadb-admin \
  --defaults-extra-file=/run/mariadb-logrotate.cnf \
  --protocol=socket ping >/dev/null

docker exec mariadb mariadb-dump \
  --defaults-extra-file=/run/mariadb-logrotate.cnf \
  --protocol=socket \
  --all-databases \
  --single-transaction \
  --quick \
  --routines \
  --events \
  --triggers \
  --hex-blob \
  --default-character-set=utf8mb4 \
  | gzip -1 >"$temp"

[[ $(stat --format '%s' "$temp") -gt 1048576 ]]

# Read the compressed stream to EOF once. This simultaneously verifies gzip's
# CRC/trailer and confirms that both the dump header and completion marker are
# present. Do not use `zgrep -m 1`: its intentional early exit closes gzip's
# stdout and becomes a false failure under `set -o pipefail`.
gzip -cd -- "$temp" | awk '
  NR <= 50 && /^-- MariaDB dump/ { header = 1 }
  /^-- Dump completed on / { footer = 1 }
  END { exit !(header && footer) }
' >/dev/null

chmod 0600 -- "$temp"
mv -- "$temp" "$final"
sha256sum -- "$final" >"$final.sha256"
chmod 0600 -- "$final.sha256"
sync -f "$backup_root"
trap - EXIT INT TERM

# Prune only this script's exact artifacts, and only after a new dump passed all
# integrity gates above.
find "$backup_root" -maxdepth 1 -type f \
  \( -name 'mariadb-all-*.sql.gz' -o -name 'mariadb-all-*.sql.gz.sha256' \) \
  -mtime "+$retention_days" -delete

printf 'MariaDB backup verified: %s\n' "$final"
