# Fizyka hosting boundaries

Fizyka shares the home server with SmartHome but has its own deployment owner:
[PhysicsForEveryone](https://github.com/PawelTroka/PhysicsForEveryone). Keep its
Compose services, release engine, live SQLite state, private keys and provider
credentials there. This repository records the shared-host boundary and prevents
general maintenance from discarding Fizyka's retained images.

| Resource | Owner and location |
|---|---|
| Production application | PhysicsForEveryone; `/app/fizyka-production`; container `fizyka-production-web-1` |
| Cloudflare connector | PhysicsForEveryone; container `fizyka-production-cloudflared-1` |
| Read-only old website | PhysicsForEveryone; `/app/fizyka-legacy-reference`; container `fizyka-legacy-reference-legacy-reference-1` |
| Archive network attachment | `fizyka-reference-attachment.timer`; preserve its reviewed attachment policy |
| Release delivery | Installed tools under `/opt/fizyka-delivery`; `fizyka-delivery.service` and timer |
| Shared Docker maintenance | This repository's optional Ouroboros and Docker GC configuration |

The public routes are recorded in [external-services.md](external-services.md).
Production's `current.json`, running image and completed acceptance receipt are
authoritative for the active release. Consult the maintained
[delivery and recovery guide](https://github.com/PawelTroka/PhysicsForEveryone/blob/master/docs/git-delivery.md)
and [archive guide](https://github.com/PawelTroka/PhysicsForEveryone/blob/master/docs/migration/legacy-reference-archive.md)
instead of copying their Compose files, systemd units or runtime configuration.

## Shared Docker maintenance

The 11 October 2026 read-only host inventory found no Ouroboros or Watchtower
container. Ouroboros remains behind the `manual-maintenance` profile. Its ignore
list now also names the three Fizyka containers, for any future deliberate
activation; this change does not start the updater.

The existing Docker GC service runs nightly with a seven-day grace period and
forced image removal. Its image-exclusion file was empty at inspection. The
reviewed [exclusion file](../docker-gc/docker-gc-exclude) protects:

- The 37 distinct image IDs in the
  [retained-image inventory](../docker-gc/fizyka-retained-images.json), covering
  38 existing release/container references. Most older images have no tags.
- Future `fizyka-delivery:<40 lowercase hexadecimal characters>` images, the
  exact repository/tag format produced by the Fizyka GitHub workflow.

There is no wildcard for all dangling images, Python, Cloudflare or other
applications. Cleanup timing, force flags, container/volume policy and unrelated
image eligibility are unchanged. Retention is not permission to start an old
image against newer production state; code-only recovery and database recovery
still follow the Fizyka guide. Retire an image only after a separate review of
its release references and recovery copies.

The pinned `clockworksoul/docker-gc-cron` image and installed script checksum are
recorded in the inventory. Its
[Spotify image-matching function](https://github.com/spotify/docker-gc/blob/master/docker-gc)
uses basic `grep` expressions against space-delimited `repository:tag` or short
image IDs. The exact 12-character IDs here correspond to the recorded full IDs;
verify uniqueness against the current complete host inventory before applying.
Full `sha256:` IDs or line anchors would not match that first-stage display.
Keep the file LF-terminated. Recheck this behavior before changing the pinned GC
image or introducing another Fizyka image-tag convention.

## Applying the maintenance change

This Git change does not change the running host. Do not reconcile the whole
SmartHome stack merely to install exclusions.

1. Confirm the pinned GC image/script, its existing bind mount and current file
   contents. Preserve unrelated local exclusions if the file has changed since
   the empty-file inventory; stop for review instead of overwriting them.
2. Verify that every pinned full image ID still resolves, that its short ID is
   unique across all local images, and that the matching function excludes the
   intended images without excluding unrelated IDs. Run only the matching
   function on captured image listings; do not invoke the cleanup script.
3. Coordinate with the running GC scheduler before writing. Install the reviewed
   bytes at `/app/homeserver/docker-gc/docker-gc-exclude` while preserving the
   currently bound inode. An atomic rename on the host alone leaves a single-file
   bind mount attached to the old file. Back up the previous bytes first.
4. Verify the SHA-256 and bytes through both the host path and the running
   container's `/etc/docker-gc-exclude`, then confirm the Fizyka container IDs,
   images and deployment configuration are unchanged. No Fizyka restart is
   required. Keep automatic delivery activation a separate reviewed operation.

Run the offline matcher and ownership regressions with Python 3 and Bash
(Git for Windows supplies Bash, sed and grep):

```sh
python -B -m unittest discover -s tests -p test_fizyka_maintenance.py
git diff --check
```

## Delivery authentication and backups

The Fizyka SSH deploy key reads its Git repository. It does not authenticate the
GitHub Actions artifact API used by the installed delivery poller. Merely changing
a Git remote to SSH does not enable that poller. Follow the Fizyka guide for its
repository-scoped API authentication and verified off-host backup prerequisites;
do not copy credentials into SmartHome or enable a second updater here.

SmartHome's MariaDB recovery copies, Nextcloud storage and SnapRAID are on this
same server. They do not satisfy the independent off-host backup requirement.
Any later Home Assistant integration should expose only a reviewed, read-only
health/backup summary, without mailbox data, private articles, secrets, a Docker
socket mount or controls to bypass deployment guards.
