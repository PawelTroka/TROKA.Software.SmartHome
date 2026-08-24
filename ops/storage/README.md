# d3 storage persistence and SnapRAID safety

The two fragments in this directory document the accepted replacement d3 disk:

- LUKS UUID `af36e2aa-c2be-4eef-9f3b-ae79cc64445f`;
- inner ext4 UUID `ad352d2c-6f7c-4c5e-99f1-3d4e6d03c8a8`;
- stable partition identity
  `/dev/disk/by-id/ata-OOS14000G_000D87HC-part1` (enforced by the runner).

`d3.crypttab.template` pins the encrypted source to the stable by-id path and
deliberately leaves the key-file path host-local. Before installing it, verify
both identities directly:

```sh
readlink -f /dev/disk/by-id/ata-OOS14000G_000D87HC-part1
sudo cryptsetup luksUUID \
  /dev/disk/by-id/ata-OOS14000G_000D87HC-part1
# Required output: af36e2aa-c2be-4eef-9f3b-ae79cc64445f
```

Never copy the placeholder key path into `/etc/crypttab`.
`d3.fstab.fragment` makes d3 depend on its cryptsetup unit. Its mergerfs entry
has a separate `x-systemd.requires-mounts-for=` dependency for every branch,
d1 through d5. Verify all resolved UUIDs and generated unit dependencies before
installing either fragment.

Neither fragment uses `nofail`: all five member disks and the mergerfs pool are
intentionally boot-critical so no missing member can silently expose an
underlying root-filesystem directory as a writable storage branch.

SnapRAID operations are governed solely by the fail-closed runner documented in
[`../../snapraid-runner/README.md`](../../snapraid-runner/README.md). The tracked
systemd timer invokes only its `report` action. The runner has no sync, scrub,
fix, touch, force, approval-token, or other mutation path. A future sync must be
a separately reviewed, explicitly authorized, supervised one-off outside the
deployed scheduler. Do not retain the historical cron entry or install a second
wrapper around the runner.

The mergerfs mount must continue to depend on all five member mounts. If any
member is absent, the pool must fail closed rather than treating an underlying
root directory as a writable branch.
