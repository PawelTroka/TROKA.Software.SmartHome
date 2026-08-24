# Fail-closed, report-only SnapRAID runner

This runner validates the complete array and runs only `snapraid diff`. Its CLI
accepts only the `report` action. It contains no sync, scrub, fix, touch, force,
approval-token, or other mutation path.

## Safety gates

Every report requires all of the following:

- a non-blocking POSIX `flock` held for the complete run;
- no other SnapRAID process present in `/proc`;
- the installed runner, SnapRAID binary, and both configurations are secure,
  root-owned regular files;
- the binary reports exactly
  `snapraid v11.3 by Andrea Mazzoleni, http://www.snapraid.it`;
- every data, parity, and content location is on a genuine local block-backed
  mount, not `/`, the root filesystem, mergerfs, a network mount, or a
  pseudo-filesystem;
- the data layout is exactly d1 through d5 mapped to
  `/media/storagedrive1` through `/media/storagedrive5` in that order;
- direct member mounts may appear RW during a manual report or RO inside the
  hardened systemd report namespace;
- d3 is exactly `/media/storagedrive3`, mounted from
  `/dev/mapper/storagedrive3`, with ext4 UUID
  `ad352d2c-6f7c-4c5e-99f1-3d4e6d03c8a8`;
- that mapper has LUKS UUID `af36e2aa-c2be-4eef-9f3b-ae79cc64445f` and the
  exact partition identity
  `/dev/disk/by-id/ata-OOS14000G_000D87HC-part1`;
- all configured content copies are non-symlink regular files, byte-identical,
  and stored on the configured minimum number of distinct local filesystems;
- the first content path is exactly `/media/cachedrive/.snapraid/content` and
  its persistent SnapRAID lock is a root-owned regular `0600` file at
  `/media/cachedrive/.snapraid/content.lock`.

The parser recognizes only the captured/upstream SnapRAID 11.3 diff grammar:
zero or one `Self test...` progress record (it is suppressed for the production
non-TTY pipe), one state-loading line, one `Comparing...` line, the six known
action categories, all seven known summaries, one matching terminal result,
and the known parity warning. Any other stdout/stderr line, category, duplicate
footer, count mismatch, or return-code mismatch fails closed.

The systemd unit adds a kernel-enforced boundary: `ProtectSystem=strict` and
`ReadOnlyPaths=/media` expose the array read-only. Only `/run/lock` and the
single pre-existing `/media/cachedrive/.snapraid/content.lock` file are writable
inside the service namespace. The parent content directory is not writable.

## Host installation

Do this only after the live mounts and identities have been verified.

1. Disable and back up every historical SnapRAID cron entry, runner, or timer.
   There must be one scheduler, and it must be this report-only timer.

2. Resolve the encrypted partition to its persistent by-id link:

   ```sh
   target=$(readlink -f -- \
     /dev/disk/by-uuid/af36e2aa-c2be-4eef-9f3b-ae79cc64445f)
   for link in /dev/disk/by-id/*; do
     [ -L "$link" ] || continue
     [ "$(readlink -f -- "$link")" = "$target" ] && printf '%s\n' "$link"
   done
   sudo cryptsetup luksUUID \
     /dev/disk/by-id/ata-OOS14000G_000D87HC-part1
   ```

   The final command must print
   `af36e2aa-c2be-4eef-9f3b-ae79cc64445f`. Never substitute `/dev/sdX`.

3. Confirm the installed SnapRAID version exactly:

   ```sh
   /usr/local/bin/snapraid --version
   # snapraid v11.3 by Andrea Mazzoleni, http://www.snapraid.it
   ```

4. Install a root-owned runner and exact-schema private configuration. Never
   run the root service from a user-writable Git checkout:

   ```sh
   sudo install -d -o root -g root -m 0755 /usr/local/libexec /etc/homeserver
   sudo install -o root -g root -m 0755 \
     /app/homeserver/snapraid-runner/snapraid-runner.py \
     /usr/local/libexec/homeserver-snapraid-runner
   sudo install -o root -g root -m 0600 \
     /app/homeserver/snapraid-runner/snapraid-runner.conf.example \
     /etc/homeserver/snapraid-runner.conf
   sudoedit /etc/homeserver/snapraid-runner.conf
   ```

5. Verify `/etc/snapraid.conf` uses direct member mountpoints, contains exactly
   one `disk d3 /media/storagedrive3` (or equivalent `data`) entry, and lists
   `/media/cachedrive/.snapraid/content` first. The persistent lock must already
   exist with its accepted identity. Verify it without following a symlink or
   changing any metadata:

   ```sh
   lock=/media/cachedrive/.snapraid/content.lock
   verified=$(sudo find "$lock" -maxdepth 0 -type f -user root -group root \
     -links 1 -perm 0600 -size 0c -print)
   [ "$verified" = "$lock" ] || {
     printf '%s\n' 'Unsafe or missing SnapRAID content lock; stop.' >&2
     exit 1
   }
   ```

   If this check fails, do not create, `chown`, `chmod`, or otherwise repair the
   path in place. Stop and investigate it as a storage-identity problem.

6. Install and verify the report-only units:

   ```sh
   sudo install -o root -g root -m 0644 \
     /app/homeserver/host/systemd/homeserver-snapraid-report.service \
     /etc/systemd/system/
   sudo install -o root -g root -m 0644 \
     /app/homeserver/host/systemd/homeserver-snapraid-report.timer \
     /etc/systemd/system/
   sudo systemd-analyze verify \
     /etc/systemd/system/homeserver-snapraid-report.service \
     /etc/systemd/system/homeserver-snapraid-report.timer
   sudo systemctl daemon-reload
   ```

7. Exercise the hardened service once and inspect its validated summary:

   ```sh
   sudo systemctl start homeserver-snapraid-report.service
   sudo systemctl status homeserver-snapraid-report.service
   sudo journalctl -u homeserver-snapraid-report.service --since today
   ```

   The scheduled service logs only counts, the terminal result, and envelope,
   action-list, and raw SHA-256 digests. The action-list digest preserves the
   historical algorithm: recognized action lines sorted bytewise, joined with
   LF, and terminated with LF when nonempty. The preserved recovery capture is
   `c48f077652d42376eca656c53c7d52128e5b217523ad00a4be490503485ae5cb`.
   The service never sends the full filename list to journald. If an
   operator needs that list, stop the timer and use a separately reviewed,
   root-only capture outside the scheduled service; do not widen `/media` in
   this unit.

8. Only after that succeeds, enable the report-only timer:

   ```sh
   sudo systemctl enable --now homeserver-snapraid-report.timer
   ```

## Future synchronization is outside this runner

Do not add sync back to this runner or timer. A future irreversible sync needs
new explicit user approval and a separately reviewed, manually supervised
one-off procedure with no hard process timeout.

Before that procedure is even considered:

1. Stop and disable the report timer for the maintenance window.
2. Pause downloads, imports, media ingestion, surveillance recording, backups,
   and any other jobs that can change the pool or a member branch.
3. Stop the entire Compose project, plus every applicable SMB/NFS service; this
   includes containers such as Nextcloud, Shinobi, Transmission, Radarr,
   Sonarr, Lidarr, PhotoPrism, Plex, and Jellyfin.
4. Inspect all remaining containers' bind sources and prove none uses
   `/media/storage` or `/media/storagedrive1` through `storagedrive5`.
5. Run `fuser -vm` against the pool and all five members. Review every row and
   require that no userspace process retains an open handle.
6. Use `findmnt --mountpoint` for each member and prove every path is its real,
   expected local filesystem rather than an underlying root directory.
7. Keep every writer stopped from the final reviewed diff until the supervised
   one-off and its read-only status check have finished. Any changed mount,
   open handle, new diff, interruption, or uncertainty cancels the operation.

Representative freeze and verification commands are:

```sh
sudo systemctl disable --now homeserver-snapraid-report.timer
cd /app/homeserver
docker compose stop
for unit in smbd nmbd winbind nfs-server; do
  systemctl is-active --quiet "$unit" && sudo systemctl stop "$unit"
done

docker ps -q | xargs -r docker inspect --format \
  '{{.Name}} {{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'
sudo fuser -vm /media/storage /media/storagedrive{1..5}
for member in /media/storagedrive{1..5}; do
  sudo findmnt --mountpoint "$member" -o TARGET,SOURCE,FSTYPE,UUID,OPTIONS
done
```

The container inspection must show no remaining storage bind. The `fuser`
output may include kernel mount bookkeeping, but no userspace PID may hold the
pool or any member. Each `findmnt` row must identify the intended local member
filesystem and an exact mountpoint.

Scrub remains a later, separately reviewed operation after a known-good recent
sync; it is never scheduled or invoked here.
