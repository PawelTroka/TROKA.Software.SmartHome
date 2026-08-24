#!/usr/bin/env python3
"""Fail-closed, report-only SnapRAID validation.

The only supported operation validates the array and runs ``snapraid diff``.
This program has no synchronization, scrub, fix, touch, or force code path.
"""

import argparse
import configparser
import contextlib
import dataclasses
import glob
import hashlib
import json
import os
import posixpath
import re
import shlex
import stat
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:  # pragma: no cover - permits static/unit checks on Windows
    fcntl = None


EXPECTED_D3_NAME = "d3"
EXPECTED_D3_MOUNT = "/media/storagedrive3"
EXPECTED_D3_FILESYSTEM_UUID = "ad352d2c-6f7c-4c5e-99f1-3d4e6d03c8a8"
EXPECTED_D3_LUKS_UUID = "af36e2aa-c2be-4eef-9f3b-ae79cc64445f"
EXPECTED_D3_MAPPER = "/dev/mapper/storagedrive3"
EXPECTED_D3_BACKING_BY_UUID = "/dev/disk/by-uuid/" + EXPECTED_D3_LUKS_UUID
EXPECTED_FIRST_CONTENT = "/media/cachedrive/.snapraid/content"
EXPECTED_SNAPRAID_CONTENT_LOCK = EXPECTED_FIRST_CONTENT + ".lock"
EXPECTED_DATA_LAYOUT = tuple(
    ("d{}".format(index), "/media/storagedrive{}".format(index)) for index in range(1, 6)
)
SUPPORTED_SNAPRAID_VERSION = "11.3"
SNAPRAID_VERSION_PATTERN = re.compile(
    r"^snapraid v([0-9]+\.[0-9]+) by Andrea Mazzoleni, http://www\.snapraid\.it$"
)
PARITY_DIRECTIVE_PATTERN = re.compile(r"^(?:[2-6]-)?parity$")
SUMMARY_PATTERN = re.compile(
    r"^\s*([0-9]+)\s+(equal|added|removed|updated|moved|copied|restored)\s*$"
)
ACTION_PATTERN = re.compile(r"^(add|remove|update|move|copy|restore)\s+.+$")
LOADING_PATTERN = re.compile(r"^Loading state from (/[^\r\n]+)\.\.\.$")
PARITY_WARNING_PATTERN = re.compile(
    r"^WARNING! With 5 disks it's recommended to use two parity levels\.$"
)
SUMMARY_KEYS = ("equal", "added", "removed", "updated", "moved", "copied", "restored")
ACTION_TO_SUMMARY = {
    "add": "added",
    "remove": "removed",
    "update": "updated",
    "move": "moved",
    "copy": "copied",
    "restore": "restored",
}
REJECTED_FILESYSTEMS = {"fuse.mergerfs", "overlay", "rootfs", "tmpfs"}


class SafetyError(RuntimeError):
    """A fail-closed safety check rejected the requested action."""


@dataclasses.dataclass(frozen=True)
class Settings:
    runner_config: str
    executable: str
    snapraid_config: str
    lock_file: str
    minimum_content_copies: int
    diff_timeout_seconds: int
    d3_backing_by_id: str


@dataclasses.dataclass(frozen=True)
class SnapraidLayout:
    data: tuple
    parity: tuple
    content: tuple


@dataclasses.dataclass(frozen=True)
class MountInfo:
    target: str
    source: str
    fstype: str
    uuid: str
    maj_min: str
    options: str

    def fingerprint(self):
        return {
            "target": self.target,
            "source": self.source,
            "fstype": self.fstype,
            "uuid": self.uuid,
            "maj_min": self.maj_min,
            "options": self.options,
        }


@dataclasses.dataclass(frozen=True)
class ValidationSnapshot:
    fingerprint: str
    content_hash: str
    details: dict


@dataclasses.dataclass(frozen=True)
class DiffSnapshot:
    semantic_digest: str
    raw_digest: str
    counts: dict
    actions: tuple

    @property
    def changed_count(self):
        return sum(self.counts[key] for key in SUMMARY_KEYS if key != "equal")

    @property
    def terminal_result(self):
        return "There are differences!" if self.changed_count else "No differences"


def log(message):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print("{} {}".format(timestamp, message), flush=True)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    before = os.stat(path, follow_symlinks=False)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = os.stat(path, follow_symlinks=False)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise SafetyError("file changed while it was hashed: {}".format(path))
    return digest.hexdigest()


def canonical_digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def require_absolute(path, label):
    if not path or not posixpath.isabs(path):
        raise SafetyError("{} must be an absolute path".format(label))
    return posixpath.normpath(path)


def require_secure_regular_file(path, label, executable=False):
    path = require_absolute(path, label)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise SafetyError("{} does not exist: {}".format(label, path))
    if stat.S_ISLNK(info.st_mode):
        raise SafetyError("{} must not be a symbolic link: {}".format(label, path))
    if not stat.S_ISREG(info.st_mode):
        raise SafetyError("{} is not a regular file: {}".format(label, path))
    if os.geteuid() == 0 and info.st_uid != 0:
        raise SafetyError("{} must be owned by root: {}".format(label, path))
    if stat.S_IMODE(info.st_mode) & 0o022:
        raise SafetyError("{} must not be group/world writable: {}".format(label, path))
    if executable and not stat.S_IMODE(info.st_mode) & 0o111:
        raise SafetyError("{} is not executable: {}".format(label, path))
    return path


def validate_installed_runner():
    # Deliberately inspect the original path. Resolving it first would hide a
    # symlinked installation from require_secure_regular_file().
    return require_secure_regular_file(
        os.path.abspath(__file__), "installed SnapRAID runner", executable=True
    )


def get_required(parser, section, option):
    if not parser.has_option(section, option):
        raise SafetyError("missing configuration option [{}] {}".format(section, option))
    value = parser.get(section, option).strip()
    if not value:
        raise SafetyError("empty configuration option [{}] {}".format(section, option))
    return value


def get_bounded_int(parser, section, option, minimum, maximum):
    value = get_required(parser, section, option)
    try:
        parsed = int(value)
    except ValueError:
        raise SafetyError("[{}] {} must be an integer".format(section, option))
    if parsed < minimum or parsed > maximum:
        raise SafetyError(
            "[{}] {} must be between {} and {}".format(section, option, minimum, maximum)
        )
    return parsed


def require_exact_config_schema(parser):
    expected = {
        "snapraid": {"executable", "config"},
        "safety": {
            "lock_file",
            "minimum_content_copies",
            "diff_timeout_seconds",
            "d3_name",
            "d3_mount",
            "d3_filesystem_uuid",
            "d3_luks_uuid",
            "d3_mapper",
            "d3_backing_by_uuid",
            "d3_backing_by_id",
        },
    }
    if parser.defaults():
        raise SafetyError("runner configuration must not use DEFAULT options")
    observed_sections = set(parser.sections())
    if observed_sections != set(expected):
        raise SafetyError(
            "runner configuration sections must be exactly {}; observed {}".format(
                sorted(expected), sorted(observed_sections)
            )
        )
    for section, expected_options in expected.items():
        observed_options = set(parser.options(section))
        if observed_options != expected_options:
            raise SafetyError(
                "runner configuration [{}] options must be exactly {}; observed {}".format(
                    section, sorted(expected_options), sorted(observed_options)
                )
            )


def load_settings(path):
    path = require_secure_regular_file(path, "runner configuration")
    parser = configparser.RawConfigParser(interpolation=None)
    loaded = parser.read(path)
    if loaded != [path]:
        raise SafetyError("could not read runner configuration: {}".format(path))
    require_exact_config_schema(parser)

    executable = require_absolute(get_required(parser, "snapraid", "executable"), "SnapRAID executable")
    snapraid_config = require_absolute(
        get_required(parser, "snapraid", "config"), "SnapRAID configuration"
    )
    lock_file = require_absolute(get_required(parser, "safety", "lock_file"), "lock file")
    backing_by_id = require_absolute(
        get_required(parser, "safety", "d3_backing_by_id"), "d3 stable by-id path"
    )

    fixed_values = {
        "d3_name": EXPECTED_D3_NAME,
        "d3_mount": EXPECTED_D3_MOUNT,
        "d3_filesystem_uuid": EXPECTED_D3_FILESYSTEM_UUID,
        "d3_luks_uuid": EXPECTED_D3_LUKS_UUID,
        "d3_mapper": EXPECTED_D3_MAPPER,
        "d3_backing_by_uuid": EXPECTED_D3_BACKING_BY_UUID,
    }
    for option, expected in fixed_values.items():
        observed = get_required(parser, "safety", option)
        if posixpath.isabs(expected):
            observed = posixpath.normpath(observed)
        if observed != expected:
            raise SafetyError(
                "[safety] {} must remain exactly {!r}; observed {!r}".format(
                    option, expected, observed
                )
            )

    if not backing_by_id.startswith("/dev/disk/by-id/"):
        raise SafetyError("d3_backing_by_id must be a /dev/disk/by-id/... partition path")
    if "REPLACE" in backing_by_id.upper() or "TODO" in backing_by_id.upper():
        raise SafetyError("d3_backing_by_id still contains a placeholder")

    return Settings(
        runner_config=path,
        executable=executable,
        snapraid_config=snapraid_config,
        lock_file=lock_file,
        minimum_content_copies=get_bounded_int(
            parser, "safety", "minimum_content_copies", 2, 16
        ),
        diff_timeout_seconds=get_bounded_int(
            parser, "safety", "diff_timeout_seconds", 60, 18000
        ),
        d3_backing_by_id=backing_by_id,
    )


def parse_snapraid_config_text(text):
    data = []
    parity = []
    content = []
    data_names = set()

    for line_number, line in enumerate(text.splitlines(), 1):
        try:
            tokens = shlex.split(line, comments=True, posix=True)
        except ValueError as error:
            raise SafetyError("invalid SnapRAID config line {}: {}".format(line_number, error))
        if not tokens:
            continue
        directive = tokens[0].lower()
        if directive in ("data", "disk"):
            if len(tokens) != 3:
                raise SafetyError("invalid data directive on SnapRAID config line {}".format(line_number))
            name, path = tokens[1], require_absolute(tokens[2], "data {} path".format(tokens[1]))
            if name in data_names:
                raise SafetyError("duplicate SnapRAID data name: {}".format(name))
            data_names.add(name)
            data.append((name, path))
        elif PARITY_DIRECTIVE_PATTERN.match(directive):
            if len(tokens) != 2:
                raise SafetyError("invalid parity directive on SnapRAID config line {}".format(line_number))
            for index, path in enumerate(tokens[1].split(","), 1):
                parity.append(
                    (
                        "{}:{}".format(directive, index),
                        require_absolute(path, "{} path".format(directive)),
                    )
                )
        elif directive == "content":
            if len(tokens) != 2:
                raise SafetyError("invalid content directive on SnapRAID config line {}".format(line_number))
            content.append(require_absolute(tokens[1], "content path"))

    if not data:
        raise SafetyError("SnapRAID config has no data disks")
    if not parity:
        raise SafetyError("SnapRAID config has no parity files")
    if not content:
        raise SafetyError("SnapRAID config has no content files")
    if EXPECTED_D3_NAME not in data_names:
        raise SafetyError("SnapRAID config has no data disk named d3")
    return SnapraidLayout(tuple(data), tuple(parity), tuple(content))


def load_snapraid_layout(path):
    path = require_secure_regular_file(path, "SnapRAID configuration")
    with open(path, "r", encoding="utf-8") as handle:
        return parse_snapraid_config_text(handle.read())


def validate_expected_data_layout(layout):
    if tuple(layout.data) != EXPECTED_DATA_LAYOUT:
        raise SafetyError(
            "SnapRAID data layout must remain exactly {}; observed {}".format(
                EXPECTED_DATA_LAYOUT, tuple(layout.data)
            )
        )


def command_environment():
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    return environment


def run_probe(arguments, timeout=30):
    try:
        completed = subprocess.run(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=timeout,
            env=command_environment(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SafetyError("probe failed: {}: {}".format(" ".join(arguments), error))
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "exit {}".format(completed.returncode)
        raise SafetyError("probe failed: {}: {}".format(" ".join(arguments), detail))
    return completed.stdout.strip()


def parse_snapraid_version_output(stdout, stderr):
    if stderr.strip():
        raise SafetyError("SnapRAID version probe produced unexpected stderr")
    output = stdout.strip()
    match = SNAPRAID_VERSION_PATTERN.fullmatch(output)
    if not match:
        raise SafetyError("unrecognized SnapRAID version output: {!r}".format(output))
    version = match.group(1)
    if version != SUPPORTED_SNAPRAID_VERSION:
        raise SafetyError(
            "unsupported SnapRAID version {}; exactly {} is required".format(
                version, SUPPORTED_SNAPRAID_VERSION
            )
        )
    return version


def probe_snapraid_version(executable):
    try:
        completed = subprocess.run(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=30,
            env=command_environment(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SafetyError("SnapRAID version probe failed: {}".format(error))
    if completed.returncode != 0:
        raise SafetyError("SnapRAID version probe exited with status {}".format(completed.returncode))
    return parse_snapraid_version_output(completed.stdout, completed.stderr)


def find_program(name):
    for directory in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise SafetyError("required program not found: {}".format(name))


def find_mount(path):
    findmnt = find_program("findmnt")
    output = run_probe(
        [
            findmnt,
            "--first-only",
            "--noheadings",
            "--pairs",
            "--target",
            path,
            "--output",
            "TARGET,SOURCE,FSTYPE,UUID,MAJ:MIN,OPTIONS",
        ]
    )
    fields = {}
    for token in shlex.split(output, posix=True):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    required = ("TARGET", "SOURCE", "FSTYPE", "MAJ:MIN", "OPTIONS")
    if any(key not in fields for key in required):
        raise SafetyError("could not parse findmnt output for {}".format(path))
    return MountInfo(
        target=os.path.realpath(fields["TARGET"]),
        source=fields["SOURCE"],
        fstype=fields["FSTYPE"],
        uuid=fields.get("UUID", ""),
        maj_min=fields["MAJ:MIN"],
        options=fields["OPTIONS"],
    )


def validate_mount(mount, root_mount, label):
    if mount.target == "/" or mount.maj_min == root_mount.maj_min:
        raise SafetyError("{} resolves to the root filesystem".format(label))
    if mount.fstype.lower() in REJECTED_FILESYSTEMS:
        raise SafetyError("{} uses rejected filesystem {}".format(label, mount.fstype))
    if not os.path.ismount(mount.target):
        raise SafetyError("{} target is not an actual mount: {}".format(label, mount.target))
    access_modes = {option for option in mount.options.split(",") if option in {"ro", "rw"}}
    if len(access_modes) != 1:
        raise SafetyError("{} has ambiguous mount access options: {}".format(label, mount.options))


def validate_local_mount(mount, root_mount, label):
    """Require a genuine local block-backed mount, either RO or RW.

    The systemd report unit deliberately exposes the array read-only, while a
    manually invoked report sees the host's normal RW mounts. Both are safe for
    ``snapraid diff``; network, mergerfs, pseudo, and root-backed mounts are not.
    """

    validate_mount(mount, root_mount, label)
    source_device = mount.source.split("[", 1)[0]
    if not source_device.startswith("/dev/"):
        raise SafetyError("{} is not backed by a local block device: {}".format(label, mount.source))
    require_block_device(source_device, "{} mount source".format(label))


def require_block_device(path, label, require_symlink=False):
    if require_symlink and not os.path.islink(path):
        raise SafetyError("{} must be a stable symbolic link: {}".format(label, path))
    try:
        info = os.stat(path)
    except FileNotFoundError:
        raise SafetyError("{} does not exist: {}".format(label, path))
    if not stat.S_ISBLK(info.st_mode):
        raise SafetyError("{} is not a block device: {}".format(label, path))
    return os.path.realpath(path)


def validate_d3(d3_mount, settings):
    configured_by_uuid = require_block_device(
        EXPECTED_D3_BACKING_BY_UUID, "d3 LUKS by-uuid identity", require_symlink=True
    )
    configured_by_id = require_block_device(
        settings.d3_backing_by_id, "d3 stable by-id identity", require_symlink=True
    )
    if configured_by_uuid != configured_by_id:
        raise SafetyError(
            "d3 by-uuid and by-id identities resolve to different devices: {} != {}".format(
                configured_by_uuid, configured_by_id
            )
        )

    cryptsetup = find_program("cryptsetup")
    luks_uuid = run_probe([cryptsetup, "luksUUID", settings.d3_backing_by_id])
    if luks_uuid != EXPECTED_D3_LUKS_UUID:
        raise SafetyError("unexpected d3 LUKS UUID: {}".format(luks_uuid))

    mapper_real = require_block_device(EXPECTED_D3_MAPPER, "d3 mapper", require_symlink=True)
    source_real = require_block_device(d3_mount.source, "d3 mounted source")
    if mapper_real != source_real:
        raise SafetyError("d3 is not mounted from {}".format(EXPECTED_D3_MAPPER))

    blkid = find_program("blkid")
    filesystem_uuid = run_probe([blkid, "-s", "UUID", "-o", "value", EXPECTED_D3_MAPPER])
    filesystem_type = run_probe([blkid, "-s", "TYPE", "-o", "value", EXPECTED_D3_MAPPER])
    if filesystem_uuid != EXPECTED_D3_FILESYSTEM_UUID:
        raise SafetyError("unexpected d3 filesystem UUID: {}".format(filesystem_uuid))
    if d3_mount.uuid and d3_mount.uuid != EXPECTED_D3_FILESYSTEM_UUID:
        raise SafetyError("findmnt reports an unexpected d3 filesystem UUID: {}".format(d3_mount.uuid))
    if filesystem_type != "ext4" or d3_mount.fstype != "ext4":
        raise SafetyError("d3 must be the expected ext4 filesystem")

    mapper_name = os.path.basename(mapper_real)
    slave_paths = glob.glob("/sys/class/block/{}/slaves/*".format(mapper_name))
    slave_devices = {os.path.realpath("/dev/" + os.path.basename(item)) for item in slave_paths}
    if slave_devices != {configured_by_id}:
        raise SafetyError(
            "d3 mapper backing device mismatch: expected {}, observed {}".format(
                configured_by_id, sorted(slave_devices)
            )
        )
    return {
        "mapper": mapper_real,
        "backing": configured_by_id,
        "filesystem_uuid": filesystem_uuid,
        "luks_uuid": luks_uuid,
    }


def validate_content_copies(paths, minimum, root_mount):
    if len(paths) < minimum:
        raise SafetyError(
            "at least {} SnapRAID content copies are required; configured {}".format(minimum, len(paths))
        )
    hashes = []
    mounts = []
    seen_paths = set()
    for path in paths:
        canonical = os.path.realpath(path)
        if canonical != os.path.normpath(path):
            raise SafetyError("content path must not traverse a symbolic link: {}".format(path))
        if canonical in seen_paths:
            raise SafetyError("duplicate SnapRAID content path: {}".format(path))
        seen_paths.add(canonical)
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise SafetyError("SnapRAID content copy is missing: {}".format(path))
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise SafetyError("SnapRAID content copy is not a regular non-symlink file: {}".format(path))
        mount = find_mount(path)
        validate_local_mount(mount, root_mount, "content copy {}".format(path))
        try:
            inside_mount = os.path.commonpath([canonical, mount.target]) == mount.target
        except ValueError:
            inside_mount = False
        if not inside_mount:
            raise SafetyError("content copy is not on its reported mount: {}".format(path))
        hashes.append(sha256_file(path))
        mounts.append(mount)
    if len(set(hashes)) != 1:
        raise SafetyError("SnapRAID content copies are not byte-for-byte consistent")
    distinct_devices = {mount.maj_min for mount in mounts}
    if len(distinct_devices) < minimum:
        raise SafetyError("SnapRAID content copies are not stored on enough distinct filesystems")
    return hashes[0], mounts


def validate_snapraid_content_lock(paths, content_mounts):
    if not paths or paths[0] != EXPECTED_FIRST_CONTENT:
        raise SafetyError(
            "first SnapRAID content path must remain exactly {}".format(EXPECTED_FIRST_CONTENT)
        )
    lock_path = EXPECTED_SNAPRAID_CONTENT_LOCK
    if os.path.realpath(lock_path) != os.path.normpath(lock_path):
        raise SafetyError("SnapRAID content lock path must not traverse a symbolic link")
    require_secure_regular_file(lock_path, "SnapRAID content lock")
    info = os.lstat(lock_path)
    if info.st_uid != 0 or info.st_gid != 0:
        raise SafetyError("SnapRAID content lock must be owned by root:root")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise SafetyError("SnapRAID content lock permissions must be exactly 0600")
    if info.st_nlink != 1 or info.st_size != 0:
        raise SafetyError("SnapRAID content lock must be a unique, empty file")
    content_info = os.lstat(paths[0])
    if not content_mounts or info.st_dev != content_info.st_dev:
        raise SafetyError("SnapRAID content lock is not on the first content filesystem")
    return {
        "path": lock_path,
        "device": info.st_dev,
        "inode": info.st_ino,
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": stat.S_IMODE(info.st_mode),
        "links": info.st_nlink,
        "size": info.st_size,
        "mount": content_mounts[0].fingerprint(),
    }


def ensure_no_other_snapraid_processes(executable):
    executable_real = os.path.realpath(executable)
    conflicts = []
    for entry in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(entry)
        if pid == str(os.getpid()):
            continue
        try:
            process_executable = os.path.realpath(os.readlink(os.path.join(entry, "exe")))
            with open(os.path.join(entry, "cmdline"), "rb") as handle:
                arguments = [part.decode("utf-8", "replace") for part in handle.read().split(b"\0") if part]
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        exact_name = any(os.path.basename(argument) == "snapraid" for argument in arguments[:1])
        if process_executable == executable_real or exact_name:
            conflicts.append({"pid": int(pid), "arguments": arguments})
    if conflicts:
        raise SafetyError("another SnapRAID process is active: {}".format(conflicts))


@contextlib.contextmanager
def exclusive_lock(path):
    if fcntl is None:
        raise SafetyError("POSIX flock support is unavailable; this runner requires Linux")
    path = require_absolute(path, "lock file")
    parent = os.path.dirname(path)
    if not os.path.isdir(parent) or os.path.islink(parent):
        raise SafetyError("lock directory is missing or unsafe: {}".format(parent))
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise SafetyError("lock path is not a regular file")
        if os.geteuid() == 0 and info.st_uid != 0:
            raise SafetyError("lock file must be owned by root")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise SafetyError("lock file permissions must be 0600 or stricter")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("another SnapRAID runner holds {}".format(path))
        os.ftruncate(descriptor, 0)
        os.write(descriptor, (str(os.getpid()) + "\n").encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def validate_array(settings):
    runner_program = validate_installed_runner()
    require_secure_regular_file(settings.executable, "SnapRAID executable", executable=True)
    require_secure_regular_file(settings.snapraid_config, "SnapRAID configuration")
    snapraid_version = probe_snapraid_version(settings.executable)
    layout = load_snapraid_layout(settings.snapraid_config)
    validate_expected_data_layout(layout)
    root_mount = find_mount("/")
    data_mounts = []
    parity_mounts = []

    for name, path in layout.data:
        if not os.path.isdir(path):
            raise SafetyError("data {} path is missing: {}".format(name, path))
        if os.path.realpath(path) != os.path.normpath(path):
            raise SafetyError("data {} path must not be a symbolic link: {}".format(name, path))
        mount = find_mount(path)
        if mount.target != os.path.realpath(path):
            raise SafetyError("data {} path is not itself a mountpoint: {}".format(name, path))
        validate_local_mount(mount, root_mount, "data {}".format(name))
        data_mounts.append((name, path, mount))

    for label, path in layout.parity:
        if not os.path.isfile(path) or os.path.islink(path):
            raise SafetyError("{} file is missing or unsafe: {}".format(label, path))
        mount = find_mount(path)
        validate_local_mount(mount, root_mount, label)
        try:
            inside_mount = os.path.commonpath([os.path.realpath(path), mount.target]) == mount.target
        except ValueError:
            inside_mount = False
        if not inside_mount:
            raise SafetyError("{} file is not on its reported mount".format(label))
        parity_mounts.append((label, path, mount))

    data_devices = [mount.maj_min for _, _, mount in data_mounts]
    parity_devices = [mount.maj_min for _, _, mount in parity_mounts]
    if len(data_devices) != len(set(data_devices)):
        raise SafetyError("two SnapRAID data entries resolve to the same mounted filesystem")
    if len(parity_devices) != len(set(parity_devices)):
        raise SafetyError("two SnapRAID parity entries resolve to the same mounted filesystem")
    if set(data_devices) & set(parity_devices):
        raise SafetyError("a parity filesystem is also configured as a data filesystem")

    d3_entries = [(path, mount) for name, path, mount in data_mounts if name == EXPECTED_D3_NAME]
    if len(d3_entries) != 1 or d3_entries[0][0] != EXPECTED_D3_MOUNT:
        raise SafetyError("d3 must map exactly to {}".format(EXPECTED_D3_MOUNT))
    d3_details = validate_d3(d3_entries[0][1], settings)

    content_hash, content_mounts = validate_content_copies(
        layout.content, settings.minimum_content_copies, root_mount
    )
    content_lock = validate_snapraid_content_lock(layout.content, content_mounts)
    details = {
        "snapraid_version": snapraid_version,
        "runner_program_sha256": sha256_file(runner_program),
        "runner_config_sha256": sha256_file(settings.runner_config),
        "snapraid_executable_sha256": sha256_file(settings.executable),
        "snapraid_config_sha256": sha256_file(settings.snapraid_config),
        "data": [
            {"name": name, "path": path, "mount": mount.fingerprint()}
            for name, path, mount in data_mounts
        ],
        "parity": [
            {"name": label, "path": path, "mount": mount.fingerprint()}
            for label, path, mount in parity_mounts
        ],
        "content": {
            "paths": list(layout.content),
            "sha256": content_hash,
            "mounts": [mount.fingerprint() for mount in content_mounts],
        },
        "content_lock": content_lock,
        "d3": d3_details,
    }
    return ValidationSnapshot(canonical_digest(details), content_hash, details)


def normalize_diff_output(stdout, stderr):
    counts = {}
    actions = []
    loading_paths = []
    self_test_count = 0
    comparing_count = 0
    terminal_lines = []
    for record_number, original in enumerate(stdout.replace("\r", "\n").splitlines(), 1):
        line = original.strip()
        if not line:
            continue
        summary_match = SUMMARY_PATTERN.match(line)
        if summary_match:
            key = summary_match.group(2).lower()
            value = int(summary_match.group(1))
            if key in counts:
                raise SafetyError("duplicate SnapRAID diff summary for {}".format(key))
            counts[key] = value
            continue
        action_match = ACTION_PATTERN.match(line)
        if action_match:
            actions.append(line)
            continue
        loading_match = LOADING_PATTERN.match(line)
        if loading_match:
            loading_paths.append(loading_match.group(1))
            continue
        if line == "Self test...":
            self_test_count += 1
            continue
        if line == "Comparing...":
            comparing_count += 1
            continue
        if line in {"There are differences!", "No differences"}:
            terminal_lines.append(line)
            continue
        raise SafetyError(
            "unrecognized SnapRAID diff stdout record {} (sha256 {})".format(
                record_number, sha256_bytes(line.encode("utf-8", "surrogateescape"))
            )
        )

    warning_count = 0
    for record_number, original in enumerate(stderr.replace("\r", "\n").splitlines(), 1):
        line = original.strip()
        if not line:
            continue
        if PARITY_WARNING_PATTERN.fullmatch(line):
            warning_count += 1
            continue
        raise SafetyError(
            "unrecognized SnapRAID diff stderr record {} (sha256 {})".format(
                record_number, sha256_bytes(line.encode("utf-8", "surrogateescape"))
            )
        )

    if len(loading_paths) != 1:
        raise SafetyError(
            "SnapRAID diff must emit exactly one recognized state-loading line; observed {}".format(
                len(loading_paths)
            )
        )
    if loading_paths[0] != EXPECTED_FIRST_CONTENT:
        raise SafetyError(
            "SnapRAID diff loaded unexpected content state: {}".format(loading_paths[0])
        )
    if self_test_count != 1:
        raise SafetyError(
            "SnapRAID diff must emit exactly one Self test line; observed {}".format(
                self_test_count
            )
        )
    if comparing_count != 1:
        raise SafetyError(
            "SnapRAID diff must emit exactly one Comparing line; observed {}".format(comparing_count)
        )
    if len(terminal_lines) != 1:
        raise SafetyError(
            "SnapRAID diff must emit exactly one terminal result line; observed {}".format(
                len(terminal_lines)
            )
        )
    if warning_count > 1:
        raise SafetyError("SnapRAID diff emitted the parity warning more than once")
    missing = [key for key in SUMMARY_KEYS if key not in counts]
    if missing:
        raise SafetyError(
            "unrecognized/incomplete SnapRAID diff output; missing summaries: {}".format(
                ", ".join(missing)
            )
        )
    action_counts = {key: 0 for key in SUMMARY_KEYS if key != "equal"}
    for line in actions:
        action_counts[ACTION_TO_SUMMARY[line.split(None, 1)[0]]] += 1
    for key, observed in action_counts.items():
        if observed != counts[key]:
            raise SafetyError(
                "SnapRAID diff listed {} {} actions but summarized {}".format(
                    observed, key, counts[key]
                )
            )
    changed_count = sum(counts[key] for key in SUMMARY_KEYS if key != "equal")
    expected_terminal = "There are differences!" if changed_count else "No differences"
    if terminal_lines[0] != expected_terminal:
        raise SafetyError(
            "SnapRAID diff terminal result {!r} conflicts with {} changes".format(
                terminal_lines[0], changed_count
            )
        )
    combined = stdout + ("\n" + stderr if stderr else "")
    semantic = {
        "counts": counts,
        "actions": sorted(actions),
        "loaded_from": loading_paths[0],
        "terminal": terminal_lines[0],
    }
    return DiffSnapshot(
        semantic_digest=canonical_digest(semantic),
        raw_digest=sha256_bytes(combined.encode("utf-8", "surrogateescape")),
        counts=counts,
        actions=tuple(sorted(actions)),
    )


def run_diff(settings):
    ensure_no_other_snapraid_processes(settings.executable)
    command = [settings.executable, "-c", settings.snapraid_config, "diff"]
    log("running read-only SnapRAID diff")
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=settings.diff_timeout_seconds,
            env=command_environment(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SafetyError("SnapRAID diff failed: {}".format(error))
    if completed.returncode not in {0, 2}:
        raise SafetyError("SnapRAID diff exited with status {}".format(completed.returncode))
    snapshot = normalize_diff_output(completed.stdout, completed.stderr)
    expected_status = 2 if snapshot.changed_count else 0
    if completed.returncode != expected_status:
        raise SafetyError(
            "SnapRAID diff status {} conflicts with {} reported changes".format(
                completed.returncode, snapshot.changed_count
            )
        )
    log("diff counts: {}".format(json.dumps(snapshot.counts, sort_keys=True)))
    log("diff terminal: {}".format(snapshot.terminal_result))
    log("diff semantic digest: {}".format(snapshot.semantic_digest))
    log("diff raw digest: {}".format(snapshot.raw_digest))
    return snapshot


def report_action(settings):
    validation = validate_array(settings)
    log("array validation fingerprint: {}".format(validation.fingerprint))
    run_diff(settings)
    ensure_no_other_snapraid_processes(settings.executable)
    final_validation = validate_array(settings)
    ensure_no_other_snapraid_processes(settings.executable)
    if final_validation.fingerprint != validation.fingerprint:
        raise SafetyError("array/config/mount state changed while diff was running")
    log("report-only run complete")


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Fail-closed, report-only SnapRAID validation runner"
    )
    parser.add_argument(
        "-c",
        "--conf",
        default="/etc/homeserver/snapraid-runner.conf",
        help="root-owned runner configuration",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("report",),
        default="report",
    )
    return parser


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    if os.name != "posix" or not os.path.isdir("/proc"):
        raise SafetyError("this runner requires a Linux host with /proc")
    if os.geteuid() != 0:
        raise SafetyError("this runner must run as root")
    validate_installed_runner()
    settings = load_settings(arguments.conf)
    with exclusive_lock(settings.lock_file):
        ensure_no_other_snapraid_processes(settings.executable)
        report_action(settings)


if __name__ == "__main__":
    try:
        main()
    except SafetyError as error:
        log("SAFETY FAILURE: {}".format(error))
        sys.exit(1)
    except KeyboardInterrupt:
        log("interrupted; no automatic retry will occur")
        sys.exit(130)
