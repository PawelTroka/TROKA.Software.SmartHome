#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  printf 'usage: %s <target-version> <pinned-image>\n' "$0" >&2
  exit 64
fi

target_version=$1
target_image=$2

app_container=${NEXTCLOUD_APP_CONTAINER:-nextcloud-migration-app}
db_container=${NEXTCLOUD_DB_CONTAINER:-nextcloud-migration-db}
network=${NEXTCLOUD_MIGRATION_NETWORK:-nextcloud-migration}
html_dir=${NEXTCLOUD_HTML_DIR:-/app/homeserver/nextcloud/html}
data_dir=${NEXTCLOUD_DATA_DIR:-/media/storage/shared_data}
backup_root=${NEXTCLOUD_BACKUP_ROOT:-/app/homeserver/.codex-backups/20260821-nextcloud-ladder}
baseline_root=${NEXTCLOUD_BASELINE_ROOT:-/app/homeserver/.codex-backups/20260821-nextcloud-v22}
bind_port=${NEXTCLOUD_MIGRATION_PORT:-18080}

log() {
  printf '[nextcloud] %s\n' "$*"
}

fail() {
  printf '[nextcloud] ERROR: %s\n' "$*" >&2
  exit 1
}

occ() {
  docker exec -u www-data "$app_container" php occ "$@"
}

read_version() {
  occ status --output=json 2>/dev/null |
    sed -n 's/.*"versionstring":"\([^"]*\)".*/\1/p' |
    tail -n 1
}

wait_web_ready() {
  local version=$1 expected_maintenance=$2 deadline status_json
  deadline=$((SECONDS + 180))
  while (( SECONDS < deadline )); do
    status_json=$(curl -fsS "http://127.0.0.1:${bind_port}/status.php" 2>/dev/null || true)
    if grep -Fq '"needsDbUpgrade":false' <<<"$status_json" &&
       grep -Fq "\"maintenance\":$expected_maintenance" <<<"$status_json" &&
       grep -Fq "\"versionstring\":\"$version\"" <<<"$status_json"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

checkpoint() {
  local version image checkpoint_dir dump_tmp
  version=$(read_version)
  [[ -n "$version" ]] || fail 'could not read the installed version'
  checkpoint_dir="$backup_root/v$version"

  if [[ -e "$checkpoint_dir/.complete" ]]; then
    log "checkpoint v$version already verified"
    return
  fi
  if [[ -e "$checkpoint_dir" ]]; then
    fail "incomplete checkpoint already exists: $checkpoint_dir"
  fi

  mkdir -p "$checkpoint_dir"
  for item in config custom_apps themes; do
    if [[ -e "$html_dir/$item" ]]; then
      rsync -a "$html_dir/$item" "$checkpoint_dir/"
    fi
  done

  image=$(docker inspect --format '{{.Config.Image}}' "$app_container")
  printf '%s\n' "$image" > "$checkpoint_dir/image.txt"
  dump_tmp="$checkpoint_dir/nextcloud.sql.gz.partial"
  docker exec "$db_container" sh -lc \
    'mariadb-dump --single-transaction --quick --lock-tables=false --hex-blob --databases nextcloud -u"$MARIADB_USER" -p"$MARIADB_PASSWORD"' |
    gzip -c > "$dump_tmp"
  gzip -t "$dump_tmp"
  mv "$dump_tmp" "$checkpoint_dir/nextcloud.sql.gz"
  touch "$checkpoint_dir/.complete"
  log "checkpointed v$version"
}

[[ $EUID -eq 0 ]] || fail 'run this migration helper as root'
[[ $target_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'target version must be x.y.z'
[[ $target_image == *@sha256:* ]] || fail 'target image must be pinned by digest'
[[ -d "$html_dir/config" ]] || fail "missing Nextcloud HTML/config: $html_dir"
[[ -d "$data_dir" ]] || fail "missing data directory: $data_dir"
[[ -d "$baseline_root/data" ]] || fail 'the full baseline data backup is missing'
gzip -t "$baseline_root/nextcloud.sql.gz" || fail 'the baseline database dump is invalid'
docker inspect "$app_container" >/dev/null 2>&1 || fail "missing app container: $app_container"
docker inspect "$db_container" >/dev/null 2>&1 || fail "missing database container: $db_container"

current_version=$(read_version)
[[ -n "$current_version" ]] || fail 'could not read current Nextcloud version'
current_major=${current_version%%.*}
target_major=${target_version%%.*}
if (( target_major < current_major || target_major > current_major + 1 )); then
  fail "unsafe major-version jump: $current_version -> $target_version"
fi

log "preparing $current_version -> $target_version"
occ maintenance:mode --on >/dev/null
checkpoint
docker pull "$target_image" >/dev/null
docker stop --time 60 "$app_container" >/dev/null
docker rm "$app_container" >/dev/null

docker run -d \
  --name "$app_container" \
  --network "$network" \
  -p "127.0.0.1:${bind_port}:80" \
  -v "$html_dir:/var/www/html" \
  -v "$data_dir:/var/www/html/data" \
  "$target_image" >/dev/null

deadline=$((SECONDS + 1200))
while (( SECONDS < deadline )); do
  running=$(docker inspect --format '{{.State.Running}}' "$app_container" 2>/dev/null || true)
  if [[ $running != true ]]; then
    docker logs --tail 120 "$app_container" >&2 || true
    fail 'upgrade container stopped unexpectedly'
  fi
  observed_version=$(read_version || true)
  status_json=$(curl -fsS "http://127.0.0.1:${bind_port}/status.php" 2>/dev/null || true)
  if [[ $observed_version == "$target_version" ]] &&
     grep -Fq '"needsDbUpgrade":false' <<<"$status_json" &&
     grep -Fq '"maintenance":true' <<<"$status_json" &&
     grep -Fq "\"versionstring\":\"$target_version\"" <<<"$status_json"; then
    break
  fi
  sleep 5
done
[[ ${observed_version:-} == "$target_version" ]] || {
  docker logs --tail 120 "$app_container" >&2 || true
  fail "timed out waiting for $target_version (observed ${observed_version:-unknown})"
}

occ maintenance:mode --off >/dev/null
occ integrity:check-core
for _ in 1 2 3; do
  docker exec -u www-data "$app_container" php -f cron.php
done

wait_web_ready "$target_version" false || fail 'status.php did not leave maintenance mode'

docker exec "$db_container" sh -lc \
  'mariadb-check -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" --check-upgrade --silent nextcloud'
mapfile -t counts < <(docker exec "$db_container" sh -lc \
  'mariadb -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\"nextcloud\"; SELECT COUNT(*) FROM nextcloud.oc_users; SELECT COUNT(*) FROM nextcloud.oc_filecache; SELECT COUNT(*) FROM nextcloud.oc_accounts; SELECT COUNT(*) FROM nextcloud.oc_group_user;"')
[[ ${#counts[@]} -eq 5 ]] || fail 'database validation did not return five counts'
(( counts[0] >= 107 )) || fail 'table count regressed'
[[ ${counts[1]} == 1 ]] || fail 'user count changed'
(( counts[2] >= 24692 )) || fail 'file-cache count regressed'
[[ ${counts[3]} == 1 ]] || fail 'account count changed'
[[ ${counts[4]} == 1 ]] || fail 'group membership count changed'

occ maintenance:mode --on >/dev/null
checkpoint
occ maintenance:mode --off >/dev/null
wait_web_ready "$target_version" false || fail 'status.php did not leave maintenance mode after checkpointing'
log "validated and checkpointed $target_version"
