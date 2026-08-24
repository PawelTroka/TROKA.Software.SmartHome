import configparser
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name("snapraid-runner.py")
REPO_ROOT = MODULE_PATH.parent.parent
SPEC = importlib.util.spec_from_file_location("safe_snapraid_runner", MODULE_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class SnapraidConfigTests(unittest.TestCase):
    def test_parses_disk_data_split_parity_and_content(self):
        layout = RUNNER.parse_snapraid_config_text(
            """
            parity /media/parity1/snapraid.parity,/media/parity2/snapraid.parity
            2-parity /media/qparity/snapraid.2-parity
            content /media/cachedrive/.snapraid/content
            content /media/storagedrive1/.snapraid/content
            disk d1 /media/storagedrive1
            data d3 /media/storagedrive3
            """
        )
        self.assertEqual(layout.data[-1], ("d3", "/media/storagedrive3"))
        self.assertEqual(len(layout.parity), 3)
        self.assertEqual(len(layout.content), 2)

    def test_rejects_duplicate_data_names(self):
        with self.assertRaisesRegex(RUNNER.SafetyError, "duplicate"):
            RUNNER.parse_snapraid_config_text(
                """
                parity /media/parity/snapraid.parity
                content /media/cachedrive/.snapraid/content
                disk d3 /media/storagedrive3
                data d3 /media/other
                """
            )

    def test_requires_d3(self):
        with self.assertRaisesRegex(RUNNER.SafetyError, "named d3"):
            RUNNER.parse_snapraid_config_text(
                """
                parity /media/parity/snapraid.parity
                content /media/cachedrive/.snapraid/content
                disk d1 /media/storagedrive1
                """
            )

    def test_array_layout_is_pinned_to_all_five_members(self):
        expected = RUNNER.SnapraidLayout(RUNNER.EXPECTED_DATA_LAYOUT, (), ())
        RUNNER.validate_expected_data_layout(expected)
        incomplete = RUNNER.SnapraidLayout(RUNNER.EXPECTED_DATA_LAYOUT[:-1], (), ())
        with self.assertRaisesRegex(RUNNER.SafetyError, "data layout must remain exactly"):
            RUNNER.validate_expected_data_layout(incomplete)


class VersionGateTests(unittest.TestCase):
    EXACT = "snapraid v11.3 by Andrea Mazzoleni, http://www.snapraid.it\n"

    def test_accepts_only_exact_supported_version(self):
        self.assertEqual(RUNNER.parse_snapraid_version_output(self.EXACT, ""), "11.3")

    def test_rejects_newer_version(self):
        newer = self.EXACT.replace("v11.3", "v12.0")
        with self.assertRaisesRegex(RUNNER.SafetyError, "unsupported.*exactly 11.3"):
            RUNNER.parse_snapraid_version_output(newer, "")

    def test_rejects_unexpected_version_stderr(self):
        with self.assertRaisesRegex(RUNNER.SafetyError, "unexpected stderr"):
            RUNNER.parse_snapraid_version_output(self.EXACT, "warning")


class DiffParsingTests(unittest.TestCase):
    VALID_DIFF = r"""
    Self test...
    Loading state from /media/cachedrive/.snapraid/content...
    Comparing...
    add movies/new.mkv
    remove tv/old.mkv
    update music/changed.flac
    copy private/My\ File.jpg
             100 equal
               1 added
               1 removed
               1 updated
               0 moved
               1 copied
               0 restored
    There are differences!
    """
    WARNING = "WARNING! With 5 disks it's recommended to use two parity levels.\n"

    def test_semantic_diff_is_stable_across_known_warning(self):
        first = RUNNER.normalize_diff_output(self.VALID_DIFF, "")
        second = RUNNER.normalize_diff_output(self.VALID_DIFF, self.WARNING)
        self.assertEqual(first.semantic_digest, second.semantic_digest)
        self.assertEqual(first.changed_count, 4)
        self.assertNotEqual(first.raw_digest, second.raw_digest)

    def test_historical_action_digest_is_byte_sorted_lf_terminated_and_multiset_safe(self):
        self.assertEqual(
            RUNNER.digest_action_lines(["remove z", "add a", "remove z"]),
            "b0b5381f549cc90f13e6fc7be89fbc970aeaa306757717f992e89b9efdf1b7a9",
        )
        self.assertEqual(
            RUNNER.digest_action_lines([]),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        self.assertEqual(
            RUNNER.PRESERVED_REFERENCE_ACTION_SHA256,
            "c48f077652d42376eca656c53c7d52128e5b217523ad00a4be490503485ae5cb",
        )

    def test_rejects_summary_action_mismatch(self):
        with self.assertRaisesRegex(RUNNER.SafetyError, "listed 1 added.*summarized 2"):
            RUNNER.normalize_diff_output(self.VALID_DIFF.replace("1 added", "2 added"), "")

    def test_preserves_legitimate_duplicate_action_text(self):
        duplicate = self.VALID_DIFF.replace(
            "    add movies/new.mkv", "    add movies/new.mkv\n    add movies/new.mkv"
        ).replace("               1 added", "               2 added")
        snapshot = RUNNER.normalize_diff_output(duplicate, "")
        self.assertEqual(snapshot.actions.count("add movies/new.mkv"), 2)
        self.assertEqual(snapshot.counts["added"], 2)

    def test_rejects_incomplete_summary(self):
        incomplete = self.VALID_DIFF.replace("               0 restored\n", "")
        with self.assertRaisesRegex(RUNNER.SafetyError, "missing summaries: restored"):
            RUNNER.normalize_diff_output(incomplete, "")

    def test_rejects_new_relocated_action_category(self):
        relocated = self.VALID_DIFF.replace(
            "             100 equal", "    relocate old/path new/path\n             100 equal"
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "unrecognized.*stdout record"):
            RUNNER.normalize_diff_output(relocated, "")

    def test_rejects_new_relocated_summary_category(self):
        relocated = self.VALID_DIFF.replace(
            "               0 restored", "               0 relocated\n               0 restored"
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "unrecognized.*stdout record"):
            RUNNER.normalize_diff_output(relocated, "")

    def test_rejects_unrecognized_stdout_or_stderr(self):
        unknown_stdout = self.VALID_DIFF.replace("Comparing...", "Unexpected phase...\nComparing...")
        with self.assertRaisesRegex(RUNNER.SafetyError, "unrecognized.*stdout record"):
            RUNNER.normalize_diff_output(unknown_stdout, "")
        with self.assertRaisesRegex(RUNNER.SafetyError, "unrecognized.*stderr"):
            RUNNER.normalize_diff_output(self.VALID_DIFF, "unknown warning")

    def test_accepts_zero_or_one_self_test_record_and_rejects_duplicates(self):
        missing = self.VALID_DIFF.replace("    Self test...\n", "")
        without_progress = RUNNER.normalize_diff_output(missing, "")
        with_progress = RUNNER.normalize_diff_output(self.VALID_DIFF, "")
        self.assertEqual(without_progress.semantic_digest, with_progress.semantic_digest)
        self.assertEqual(
            without_progress.semantic_action_sha256,
            with_progress.semantic_action_sha256,
        )
        duplicate = self.VALID_DIFF.replace("    Self test...\n", "    Self test...\n    Self test...\n")
        with self.assertRaisesRegex(RUNNER.SafetyError, "at most one Self test.*observed 2"):
            RUNNER.normalize_diff_output(duplicate, "")

    def test_requires_exact_first_content_state(self):
        wrong = self.VALID_DIFF.replace(
            "/media/cachedrive/.snapraid/content...",
            "/media/storagedrive1/.snapraid/content...",
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "loaded unexpected content state"):
            RUNNER.normalize_diff_output(wrong, "")

    def test_rejects_terminal_count_conflict(self):
        conflict = self.VALID_DIFF.replace("There are differences!", "No differences")
        with self.assertRaisesRegex(RUNNER.SafetyError, "terminal result.*conflicts"):
            RUNNER.normalize_diff_output(conflict, "")

    def test_accepts_strict_zero_change_result(self):
        zero = """
        Self test...
        Loading state from /media/cachedrive/.snapraid/content...
        Comparing...
        100 equal
        0 added
        0 removed
        0 updated
        0 moved
        0 copied
        0 restored
        No differences
        """
        self.assertEqual(RUNNER.normalize_diff_output(zero, "").changed_count, 0)

    def test_parses_preserved_large_diff_count_shape(self):
        actions = []
        actions.extend("add added/{:06d}".format(index) for index in range(3625))
        actions.extend("remove removed/{:06d}".format(index) for index in range(168690))
        actions.extend("update updated/{:06d}".format(index) for index in range(507))
        actions.append("copy copied/000000")
        footer = """
          248687 equal
            3625 added
          168690 removed
             507 updated
               0 moved
               1 copied
               0 restored
        There are differences!
        """
        stdout = "\n".join(
            [
                "Self test...",
                "Loading state from /media/cachedrive/.snapraid/content...",
                "Comparing...",
                *actions,
                footer,
            ]
        )
        snapshot = RUNNER.normalize_diff_output(stdout, self.WARNING)
        self.assertEqual(snapshot.changed_count, 172823)
        self.assertEqual(snapshot.counts["removed"], 168690)


class CliAndCommandTests(unittest.TestCase):
    @staticmethod
    def settings():
        return RUNNER.Settings(
            runner_config="/etc/homeserver/snapraid-runner.conf",
            executable="/usr/local/bin/snapraid",
            snapraid_config="/etc/snapraid.conf",
            lock_file="/run/lock/homeserver-snapraid.lock",
            minimum_content_copies=2,
            diff_timeout_seconds=3600,
            d3_backing_by_id="/dev/disk/by-id/ata-OOS14000G_000D87HC-part1",
        )

    def test_default_and_only_action_is_report(self):
        parser = RUNNER.build_argument_parser()
        self.assertEqual(parser.parse_args([]).action, "report")
        for action in ("prepare-sync", "sync", "scrub", "fix", "touch", "force"):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args([action])

    def test_removed_approval_options_are_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                RUNNER.build_argument_parser().parse_args(["--approval-token", "x"])

    def test_diff_subprocess_is_hardcoded_read_only(self):
        completed = types.SimpleNamespace(
            returncode=0,
            stdout="""
            Self test...
            Loading state from /media/cachedrive/.snapraid/content...
            Comparing...
            1 equal
            0 added
            0 removed
            0 updated
            0 moved
            0 copied
            0 restored
            No differences
            """,
            stderr="",
        )
        output = io.StringIO()
        with mock.patch.object(RUNNER, "ensure_no_other_snapraid_processes"), mock.patch.object(
            RUNNER.subprocess, "run", return_value=completed
        ) as run, contextlib.redirect_stdout(output):
            RUNNER.run_diff(self.settings())
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/local/bin/snapraid", "-c", "/etc/snapraid.conf", "diff"],
        )
        self.assertNotIn("Loading state", output.getvalue())
        self.assertIn("diff counts:", output.getvalue())
        self.assertIn("diff terminal: No differences", output.getvalue())
        self.assertIn("diff semantic digest:", output.getvalue())
        self.assertIn("diff semantic action sha256:", output.getvalue())
        self.assertIn("diff raw digest:", output.getvalue())

    def test_invalid_diff_is_rejected_before_raw_output_is_logged(self):
        completed = types.SimpleNamespace(
            returncode=2,
            stdout="SENSITIVE-UNVALIDATED-PATH\n",
            stderr="",
        )
        output = io.StringIO()
        with mock.patch.object(RUNNER, "ensure_no_other_snapraid_processes"), mock.patch.object(
            RUNNER.subprocess, "run", return_value=completed
        ), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RUNNER.SafetyError, "unrecognized") as caught:
                RUNNER.run_diff(self.settings())
        self.assertNotIn("SENSITIVE-UNVALIDATED-PATH", output.getvalue())
        self.assertNotIn("SENSITIVE-UNVALIDATED-PATH", str(caught.exception))

    def test_runner_path_is_checked_before_symlink_resolution(self):
        fake_path = str(REPO_ROOT / "installed-runner-link")
        with mock.patch.object(RUNNER, "__file__", fake_path), mock.patch.object(
            RUNNER, "require_secure_regular_file", return_value=fake_path
        ) as secure, mock.patch.object(
            RUNNER.os.path, "realpath", side_effect=AssertionError("must not resolve runner path")
        ):
            self.assertEqual(RUNNER.validate_installed_runner(), fake_path)
        self.assertEqual(secure.call_args.args[0], str(pathlib.Path(fake_path).absolute()))

    def test_no_mutation_or_token_functions_remain(self):
        for name in (
            "run_snapraid",
            "prepare_sync_action",
            "sync_action",
            "write_approval",
            "read_approval",
            "consume_approval",
        ):
            self.assertFalse(hasattr(RUNNER, name), name)

    def test_post_diff_process_scans_bracket_final_validation(self):
        events = []
        snapshot = RUNNER.ValidationSnapshot("same", "content", {})

        def validate(_settings):
            events.append("validate")
            return snapshot

        with mock.patch.object(RUNNER, "validate_array", side_effect=validate), mock.patch.object(
            RUNNER, "run_diff", side_effect=lambda _settings: events.append("diff")
        ), mock.patch.object(
            RUNNER,
            "ensure_no_other_snapraid_processes",
            side_effect=lambda _executable: events.append("scan"),
        ), contextlib.redirect_stdout(io.StringIO()):
            RUNNER.report_action(self.settings())
        self.assertEqual(events, ["validate", "diff", "scan", "validate", "scan"])


class ConfigSchemaTests(unittest.TestCase):
    def test_stale_sync_option_fails_closed(self):
        parser = configparser.RawConfigParser(interpolation=None)
        parser.read_string(
            """
            [snapraid]
            executable=/usr/local/bin/snapraid
            config=/etc/snapraid.conf
            [safety]
            lock_file=/run/lock/homeserver-snapraid.lock
            minimum_content_copies=2
            diff_timeout_seconds=3600
            d3_name=d3
            d3_mount=/media/storagedrive3
            d3_filesystem_uuid=ad352d2c-6f7c-4c5e-99f1-3d4e6d03c8a8
            d3_luks_uuid=af36e2aa-c2be-4eef-9f3b-ae79cc64445f
            d3_mapper=/dev/mapper/storagedrive3
            d3_backing_by_uuid=/dev/disk/by-uuid/af36e2aa-c2be-4eef-9f3b-ae79cc64445f
            d3_backing_by_id=/dev/disk/by-id/ata-OOS14000G_000D87HC-part1
            sync_enabled=true
            """
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "options must be exactly"):
            RUNNER.require_exact_config_schema(parser)


class MountGateTests(unittest.TestCase):
    ROOT = RUNNER.MountInfo("/", "/dev/root", "ext4", "root", "8:1", "rw,relatime")

    def test_rejects_root_device_alias(self):
        alias = RUNNER.MountInfo(
            "/media/storagedrive1", "/dev/root", "ext4", "root", "8:1", "rw,relatime"
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "root filesystem"):
            RUNNER.validate_mount(alias, self.ROOT, "data d1")

    def test_rejects_mergerfs_and_network_mounts(self):
        mergerfs = RUNNER.MountInfo(
            "/media/storagedrive1", "mergerfs", "fuse.mergerfs", "", "0:99", "ro,relatime"
        )
        with self.assertRaisesRegex(RUNNER.SafetyError, "rejected filesystem"):
            RUNNER.validate_mount(mergerfs, self.ROOT, "data d1")

        network = RUNNER.MountInfo(
            "/media/cachedrive", "server:/share", "nfs4", "", "0:100", "ro,relatime"
        )
        with mock.patch.object(RUNNER.os.path, "ismount", return_value=True):
            with self.assertRaisesRegex(RUNNER.SafetyError, "not backed by a local block"):
                RUNNER.validate_local_mount(network, self.ROOT, "content")

    def test_accepts_read_only_local_mount_for_sandboxed_report(self):
        local = RUNNER.MountInfo(
            "/media/cachedrive", "/dev/mapper/cache", "ext4", "cache", "253:1", "ro,relatime"
        )
        with mock.patch.object(RUNNER.os.path, "ismount", return_value=True), mock.patch.object(
            RUNNER, "require_block_device", return_value="/dev/dm-1"
        ):
            RUNNER.validate_local_mount(local, self.ROOT, "content")

    def test_content_validation_calls_local_mount_gate_for_every_copy(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as temporary:
            root = pathlib.Path(temporary)
            first = root / "content1"
            second = root / "content2"
            first.write_bytes(b"same")
            second.write_bytes(b"same")
            mounts = [
                RUNNER.MountInfo(str(root), "/dev/a", "ext4", "a", "8:2", "ro"),
                RUNNER.MountInfo(str(root), "/dev/b", "ext4", "b", "8:3", "ro"),
            ]
            with mock.patch.object(RUNNER, "find_mount", side_effect=mounts), mock.patch.object(
                RUNNER, "validate_local_mount"
            ) as gate:
                digest, observed = RUNNER.validate_content_copies(
                    [str(first), str(second)], 2, self.ROOT
                )
            self.assertEqual(len(digest), 64)
            self.assertEqual(observed, mounts)
            self.assertEqual(gate.call_count, 2)

    def test_first_content_path_is_identity_pinned(self):
        with self.assertRaisesRegex(RUNNER.SafetyError, "first SnapRAID content path"):
            RUNNER.validate_snapraid_content_lock(
                ["/media/other/content"], []
            )

    def test_content_lock_rejects_hardlinks_or_payload(self):
        mount = RUNNER.MountInfo(
            "/media/cachedrive", "/dev/cache", "ext4", "cache", "8:4", "ro"
        )
        unsafe_lock = types.SimpleNamespace(
            st_uid=0,
            st_gid=0,
            st_mode=RUNNER.stat.S_IFREG | 0o600,
            st_nlink=2,
            st_size=0,
            st_dev=4,
            st_ino=10,
        )
        content = types.SimpleNamespace(st_dev=4)
        with mock.patch.object(RUNNER.os.path, "realpath", side_effect=lambda path: path), mock.patch.object(
            RUNNER.os.path, "normpath", side_effect=lambda path: path
        ), mock.patch.object(RUNNER, "require_secure_regular_file"), mock.patch.object(
            RUNNER.os, "lstat", side_effect=[unsafe_lock, content]
        ):
            with self.assertRaisesRegex(RUNNER.SafetyError, "unique, empty"):
                RUNNER.validate_snapraid_content_lock([RUNNER.EXPECTED_FIRST_CONTENT], [mount])


class RepositoryPolicyTests(unittest.TestCase):
    def test_systemd_unit_is_read_only_except_exact_lock_files(self):
        unit = (REPO_ROOT / "host/systemd/homeserver-snapraid-report.service").read_text()
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ReadOnlyPaths=/media", unit)
        self.assertNotIn("StateDirectory=", unit)
        write_line = next(line for line in unit.splitlines() if line.startswith("ReadWritePaths="))
        self.assertEqual(
            set(write_line.removeprefix("ReadWritePaths=").split()),
            {"/run/lock", "/media/cachedrive/.snapraid/content.lock"},
        )
        self.assertNotIn(" /media ", " " + write_line + " ")
        self.assertIn(" report", unit)
        self.assertIn("TimeoutStartSec=6h", unit)
        self.assertIn("TimeoutStopSec=5m", unit)
        self.assertIn("KillSignal=SIGINT", unit)

    def test_storage_fragments_pin_by_id_and_all_branches(self):
        crypttab = (REPO_ROOT / "ops/storage/d3.crypttab.template").read_text()
        data_line = next(line for line in crypttab.splitlines() if line and not line.startswith("#"))
        self.assertEqual(
            data_line.split()[1],
            "/dev/disk/by-id/ata-OOS14000G_000D87HC-part1",
        )
        fstab = (REPO_ROOT / "ops/storage/d3.fstab.fragment").read_text()
        self.assertNotIn("nofail", crypttab + fstab)
        pool_line = fstab.splitlines()[1]
        for index in range(1, 6):
            dependency = "x-systemd.requires-mounts-for=/media/storagedrive{}".format(index)
            self.assertEqual(pool_line.count(dependency), 1)

    def test_docs_and_config_have_no_deployed_sync_controls(self):
        config = (MODULE_PATH.parent / "snapraid-runner.conf.example").read_text()
        self.assertNotIn("sync_enabled", config)
        self.assertNotIn("sync_timeout", config)
        self.assertNotIn("approval", config.lower())
        readme = (MODULE_PATH.parent / "README.md").read_text()
        self.assertNotIn("find -L", readme)
        self.assertNotIn("chown root:root /media/cachedrive/.snapraid/content.lock", readme)
        self.assertNotIn("chmod 0600 /media/cachedrive/.snapraid/content.lock", readme)
        self.assertIn("-type f -user root -group root", readme)
        self.assertIn("Future synchronization is outside this runner", readme)


if __name__ == "__main__":
    unittest.main()
