#!/usr/bin/with-contenv sh
set -eu

: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"

MARIADB_LOGROTATE_CLIENT=/run/mariadb-logrotate.cnf
MARIADB_LOGROTATE_TEMP=${MARIADB_LOGROTATE_CLIENT}.tmp

cleanup() {
    rm -f -- "$MARIADB_LOGROTATE_TEMP"
}
trap cleanup EXIT INT TERM

umask 077
{
    printf '%s\n' '[client]'
    printf '%s\n' 'user=root'
    printf 'password=%s\n' "$MYSQL_ROOT_PASSWORD"
} >"$MARIADB_LOGROTATE_TEMP"

chown abc:abc "$MARIADB_LOGROTATE_TEMP"
chmod 600 "$MARIADB_LOGROTATE_TEMP"
mv -f -- "$MARIADB_LOGROTATE_TEMP" "$MARIADB_LOGROTATE_CLIENT"
trap - EXIT INT TERM
