"""Exercise the pinned GC image-matching pipeline against synthetic listings.

No Docker daemon, host configuration, provider or private input is accessed.
The short pipeline below follows Spotify docker-gc (Apache-2.0), whose installed
script SHA-256 is recorded alongside the reviewed public image inventory.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docker-gc/docker-gc-exclude"
INVENTORY = ROOT / "docker-gc/fizyka-retained-images.json"
FUTURE = r"fizyka-delivery:[0-9a-f]\{40\}"
FIZYKA = {"fizyka-production-web-1", "fizyka-production-cloudflared-1",
          "fizyka-legacy-reference-legacy-reference-1"}

# This is only compute_exclude_ids' text-matching pipeline. There is no Docker
# command, cleanup entrypoint, sourced upstream script, rm or rmi operation.
MATCH = r"""
set -eu
sed 's/^\(.*\)$/ \1 /' policy | sed '/^ *$/d' > patterns
tail -n+2 listing | sed 's/^\([^ ]*\) *\([^ ]*\) *\([^ ]*\).*/ \1:\2 \3 /' |
  grep -f patterns | cut -d' ' -f3 | sed 's/^/^(sha256:)?/' > ids
grep -E -v -f ids candidates > remaining || test "$?" -eq 1
cat remaining
"""


def bash():
    if os.name == "nt":
        git = shutil.which("git")
        path = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
        if path and path.is_file():
            return str(path)
    executable = shutil.which("bash")
    if not executable:
        raise RuntimeError("Bash and its sed/grep tools are required; no checks were skipped")
    return executable


class FizykaMaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        cls.images = [row["image"] for row in cls.inventory["images"]]

    def remaining(self, rows):
        """Rows are repo, tag, full image ID; return GC-eligible IDs."""
        with tempfile.TemporaryDirectory(prefix="fizyka-gc-match-") as directory:
            folder = Path(directory)
            (folder / "policy").write_bytes(POLICY.read_bytes())
            (folder / "listing").write_text("REPOSITORY TAG IMAGE_ID CREATED SIZE\n" + "".join(
                f"{repo} {tag} {image.removeprefix('sha256:')[:12]} 14-days 1MB\n"
                for repo, tag, image in rows), encoding="ascii", newline="\n")
            (folder / "candidates").write_text("".join(image + "\n" for image in dict.fromkeys(
                image for _, _, image in rows)), encoding="ascii", newline="\n")
            result = subprocess.run([bash(), "-c", MATCH], cwd=folder,
                capture_output=True, text=True, timeout=15, check=True)
            return result.stdout.splitlines()

    def test_policy_is_exactly_scoped_and_lf_terminated(self):
        raw = POLICY.read_bytes()
        expected = FUTURE + "\n" + "\n".join(image[7:19] for image in self.images) + "\n"
        self.assertEqual(raw, expected.encode("ascii"))
        self.assertNotIn(b"\r", raw)
        self.assertIn("docker-gc/docker-gc-exclude text eol=lf",
                      (ROOT / ".gitattributes").read_text())

    def test_full_image_inventory_has_unique_complete_ids_and_references(self):
        self.assertEqual(self.inventory["schema"], 1)
        self.assertEqual(len(self.images), 37)
        self.assertEqual(len({image[7:19] for image in self.images}), len(self.images))
        self.assertTrue(all(re.fullmatch(r"sha256:[a-f0-9]{64}", image) for image in self.images))
        references = [ref for row in self.inventory["images"] for ref in row["references"]]
        self.assertEqual(len(references), 38)
        self.assertEqual(len(set(references)), len(references))
        self.assertEqual({ref.removeprefix("container:") for ref in references
                          if ref.startswith("container:")}, FIZYKA)

    def test_all_pinned_untagged_images_survive_but_other_dangling_images_do_not(self):
        unrelated = "sha256:" + "0" * 64
        rows = [("<none>", "<none>", image) for image in [*self.images, unrelated]]
        self.assertEqual(self.remaining(rows), [unrelated])

    def test_future_exact_workflow_tags_survive_and_multi_tag_ids_stay_excluded(self):
        future = "sha256:" + "1" * 64
        rows = [("fizyka-delivery", "a" * 40, future), ("other-tag", "latest", future)]
        self.assertEqual(self.remaining(rows), [])

    def test_unrelated_and_similar_repositories_and_invalid_tags_remain_eligible(self):
        variants = [("unrelated/fizyka-delivery", "a" * 40), ("not-fizyka-delivery", "a" * 40),
                    ("fizyka-delivery-extra", "a" * 40), ("fizyka-delivery", "a" * 39),
                    ("fizyka-delivery", "a" * 41), ("fizyka-delivery", "G" * 40),
                    ("cloudflare/cloudflared", "latest"), ("python", "latest"),
                    ("mariadb", "stable"), ("fizyka-web", "unreviewed")]
        rows = [(repo, tag, "sha256:" + f"{index:064x}")
                for index, (repo, tag) in enumerate(variants, 100)]
        # Distinct short IDs are necessary to model Docker's display correctly.
        rows = [(repo, tag, "sha256:" + f"{index:012x}" + "f" * 52)
                for index, (repo, tag, _) in enumerate(rows, 100)]
        self.assertEqual(self.remaining(rows), [image for _, _, image in rows])

    def test_general_maintenance_does_not_take_ownership_of_fizyka(self):
        compose = (ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
        ignored = re.search(r"^      IGNORE: (.+)$", compose, re.M).group(1).split()
        before = {"traefik", "influxdb", "hassio_dns", "homeassistant", "hassio_supervisor",
                  "addon_core_check_config", "addon_62c7908d_autobackup", "plexms"}
        self.assertEqual(set(ignored), before | FIZYKA)
        updater = compose.split("  ouroboros:\n", 1)[1].split("  dockergc:\n", 1)[0]
        self.assertIn("    profiles:\n      - manual-maintenance\n", updater)
        for name, value in {"FORCE_IMAGE_REMOVAL": "1", "FORCE_CONTAINER_REMOVAL": "0",
                            "GRACE_PERIOD_SECONDS": "604800", "DRY_RUN": "0", "CLEAN_UP_VOLUMES": "0"}.items():
            self.assertRegex(compose, rf"(?m)^      {name}: {value}$")
        self.assertNotRegex(compose, r"(?m)^  fizyka[^:]*:")
        self.assertIn("image: " + self.inventory["gc_image"], compose)


if __name__ == "__main__":
    unittest.main()
