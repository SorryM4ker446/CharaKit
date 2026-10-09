"""Source-only references and manually observed fidelity gates; no model calls."""
import json
from pathlib import Path
import zipfile
import unittest

from PIL import Image

import test_outfits as existing

outfits = existing.outfits


class OutfitFidelityTests(unittest.TestCase):
    setUp = existing.OutfitTests.setUp
    candidate = existing.OutfitTests.candidate
    accepted = existing.OutfitTests.accepted
    assert_code = existing.OutfitTests.assert_code
    cli = existing.OutfitTests.cli

    def prepare(self, **changes):
        args = dict(outfit_id="coat_navy", target="jacket fabric", color="navy blue",
                    boundary="Fabric only; exclude buttons, lining, tie and skirt.",
                    protected_regions=["Whole face, expression, hair, pose", "Other clothing, trim and accessories"],
                    target_box=[24, 38, 72, 98])
        args.update(changes)
        return outfits.prepare_outfit(self.root, **args)

    def scoped_candidate(self, brief=None, size=(96, 144)):
        brief = brief or self.prepare()
        image = self.folder / "scoped.png"
        existing.fixture(image, "#334477", size)
        return outfits.add_asset(self.root, image, "coat_navy", "jacket fabric", "navy blue",
                                 brief_file=Path(brief["brief_file"]))["asset"]

    def observed(self, asset, target="passed", protection="passed", basis="assistant"):
        return outfits.record_fidelity(self.root, asset["id"], target, protection,
                                       "Compared the full source, whole face and garment region.", basis)

    def test_prepare_preserves_source_and_metadata_and_crops_exact_source_pixels(self):
        source_before = (self.root / "source.png").read_bytes()
        state_before = (self.root / "run.json").read_bytes()
        first, second = self.prepare(), self.prepare()
        self.assertNotEqual(first["brief_file"], second["brief_file"])
        self.assertEqual(json.loads(Path(first["brief_file"]).read_text(encoding="utf-8"))["source_sha256"],
                         outfits.digest(self.root / "source.png"))
        with Image.open(self.root / "source.png") as source, Image.open(first["detail_reference"]) as reference:
            self.assertEqual(reference.size, (48, 60))
            self.assertEqual(reference.tobytes(), source.convert("RGBA").crop((24, 38, 72, 98)).tobytes())
        self.assertEqual((self.root / "source.png").read_bytes(), source_before)
        self.assertEqual((self.root / "run.json").read_bytes(), state_before)
        self.assertEqual(outfits.read_state(self.root)["assets"], [])

    def test_invalid_preparation_creates_no_brief_reference_or_project_changes(self):
        before = (self.root / "run.json").read_bytes()
        for fields, code in [({"target_box": [0, 0, 200, 200]}, "INVALID_TARGET_BOX"),
                             ({"target_box": [0, 0, True, 100]}, "INVALID_TARGET_BOX"),
                             ({"boundary": ""}, "INVALID_EDIT_BRIEF"),
                             ({"protected_regions": []}, "INVALID_EDIT_BRIEF"),
                             ({"protected_regions": ["face\npose"]}, "INVALID_EDIT_BRIEF")]:
            with self.subTest(fields=fields):
                self.assert_code(code, self.prepare, **fields)
        self.assertFalse((self.root / "references").exists())
        self.assertFalse((self.root / "briefs").exists())
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.candidate()
        self.assert_code("OUTFIT_DEFINITION_CHANGED", self.prepare, color="red")

    def test_brief_definition_and_reference_changes_are_rejected_before_import(self):
        prepared = self.prepare()
        brief = Path(prepared["brief_file"])
        before = (self.root / "run.json").read_bytes()
        self.assert_code("INVALID_EDIT_BRIEF", outfits.add_asset, self.root, self.source,
                         "coat_red", "jacket fabric", "red", brief_file=brief)
        Path(prepared["detail_reference"]).write_bytes(b"changed reference")
        self.assert_code("REFERENCE_CHANGED", outfits.add_asset, self.root, self.source,
                         "coat_navy", "jacket fabric", "navy blue", brief_file=brief)
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertFalse((self.root / "candidates").exists())

    def test_fidelity_and_real_user_acceptance_are_independent_gates(self):
        asset = self.scoped_candidate()
        self.assertEqual(outfits.fidelity_status(asset), "pending")
        self.assert_code("FIDELITY_REVIEW_REQUIRED", outfits.review_asset, self.root, asset["id"], "accepted")
        result = self.observed(asset)
        self.assertEqual(result["art_review_status"], "unreviewed")
        self.assertEqual(result["selected"], {})
        self.assert_code("ART_REVIEW_REQUIRED", outfits.select_asset, self.root, asset["id"])
        outfits.review_asset(self.root, asset["id"], "accepted", "User selected this result")
        red = self.accepted("coat_red", "red")
        result = self.observed(asset, protection="failed")
        self.assertEqual(result["fidelity_status"], "failed")
        self.assertEqual(result["art_review_status"], "accepted")
        self.assertEqual(result["selected"], {"coat_red": red["id"]})
        self.assert_code("FIDELITY_CHECK_FAILED", outfits.select_asset, self.root, asset["id"])
        self.assert_code("FIDELITY_CHECK_FAILED", outfits.export_pack, self.root, ids=[asset["id"]])
        self.assertEqual(outfits.export_pack(self.root)["asset_ids"], [red["id"]])

    def test_revision_inherits_scope_without_inheriting_fidelity_or_selection(self):
        first = self.scoped_candidate()
        self.observed(first)
        outfits.review_asset(self.root, first["id"], "accepted")
        second = self.candidate()
        self.assertEqual(second["edit_brief"], first["edit_brief"])
        self.assertNotIn("fidelity_review", second)
        self.assertEqual(outfits.fidelity_status(second), "pending")
        self.assertEqual(outfits.read_state(self.root)["selected"], {"coat_navy": first["id"]})
        self.assert_code("FIDELITY_REVIEW_REQUIRED", outfits.review_asset, self.root, second["id"], "accepted")
        result = self.observed(second, protection="uncertain")
        self.assertEqual(result["fidelity_status"], "uncertain")
        self.assert_code("FIDELITY_CHECK_FAILED", outfits.review_asset, self.root, second["id"], "accepted")

    def test_canvas_failure_can_keep_observations_without_becoming_accepted(self):
        asset = self.scoped_candidate(size=(48, 72))
        candidate_before = (self.root / asset["path"]).read_bytes()
        result = self.observed(asset)
        self.assertFalse(result["technical_passed"])
        self.assertEqual(result["fidelity_status"], "passed")
        self.assert_code("TECHNICAL_CHECK_FAILED", outfits.review_asset, self.root, asset["id"], "accepted")
        self.assertEqual((self.root / asset["path"]).read_bytes(), candidate_before)
        self.assertEqual(outfits.read_state(self.root)["selected"], {})

    def test_changed_candidate_and_invalid_observation_cannot_reuse_evidence(self):
        asset = self.scoped_candidate()
        before = (self.root / "run.json").read_bytes()
        self.assert_code("INVALID_FIDELITY_REVIEW", outfits.record_fidelity, self.root, asset["id"],
                         "passed", "passed", "", "assistant")
        self.assert_code("INVALID_FIDELITY_REVIEW", outfits.record_fidelity, self.root, asset["id"],
                         "passed", "passed", "Visible findings", "automatic")
        existing.fixture(self.root / asset["path"], "#ee4455")
        self.assert_code("TECHNICAL_CHECK_FAILED", self.observed, asset)
        self.assertEqual((self.root / "run.json").read_bytes(), before)

    def test_legacy_metadata_is_read_without_fabricating_scope_or_checks(self):
        asset = self.accepted()
        before = (self.root / "run.json").read_bytes()
        state = outfits.read_state(self.root)
        self.assertNotIn("edit_brief", state["assets"][0])
        self.assertNotIn("fidelity_review", state["assets"][0])
        self.assertEqual(outfits.fidelity_status(asset), "unrecorded")
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.observed(asset, protection="failed")
        self.assert_code("FIDELITY_CHECK_FAILED", outfits.review_asset, self.root, asset["id"], "accepted")

    def test_export_includes_scope_and_observation_but_preserves_candidate_bytes(self):
        asset = self.scoped_candidate()
        self.observed(asset, basis="user")
        outfits.review_asset(self.root, asset["id"], "accepted")
        metadata_before = (self.root / "run.json").read_bytes()
        preview = self.folder / "fidelity-preview.png"
        outfits.make_preview(self.root, preview, [asset["id"]], face_box=[34, 5, 62, 35], detail_box=[24,38,72,98],
                             labels={"fidelity_passed":"保真观察通过"})
        result = outfits.export_pack(self.root)
        sprite = result["manifest"]["sprites"][0]
        self.assertEqual(sprite["edit_scope"]["boundary"], asset["edit_brief"]["boundary"])
        self.assertEqual(sprite["fidelity_review"]["basis"], "user")
        with zipfile.ZipFile(result["export"]) as archive:
            self.assertEqual(archive.read(sprite["path"]), (self.root / asset["path"]).read_bytes())
            self.assertFalse(any(name.startswith(("briefs/", "references/")) for name in archive.namelist()))
        self.assertEqual((self.root / "run.json").read_bytes(), metadata_before)
        state = outfits.read_state(self.root)
        state["assets"][0]["fidelity_review"]["asset_sha256"] = "0" * 64
        outfits.write_state(self.root, state)
        self.assert_code("INVALID_PROJECT", outfits.read_state, self.root)

    def test_packaged_cli_prepares_and_records_unicode_observations_outside_repo(self):
        package = self.folder / "plugin.zip"
        existing.builder.build(existing.REPO, package)
        installed = self.folder / "installed"
        with zipfile.ZipFile(package) as archive:
            archive.extractall(installed)
        script = installed / "skills/charakit-outfits/scripts/studio.py"
        result = self.cli(script, "prepare", "--project", self.root, "--outfit", "coat_navy", "--target", "jacket fabric",
                          "--color", "navy blue", "--boundary", "仅外套布料，排除饰边", "--protect", "整个面部、头发与姿势",
                          "--protect", "其他衣物、纽扣", "--target-box", 24, 38, 72, 98)
        self.assertEqual(result.returncode, 0, result.stderr)
        brief = json.loads(result.stdout)["brief_file"]
        result = self.cli(script, "add", "--project", self.root, "--outfit", "coat_navy", "--target", "jacket fabric",
                          "--color", "navy blue", "--image", self.source, "--brief-file", brief)
        self.assertEqual(result.returncode, 0, result.stderr)
        asset = json.loads(result.stdout)["asset"]["id"]
        result = self.cli(script, "fidelity", "--project", self.root, "--asset", asset, "--target-check", "failed",
                          "--protection-check", "passed", "--note", "合成夹具未改色；脸与其他部位未改变")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["fidelity_status"], "failed")
        result = self.cli(script, "review", "--project", self.root, "--asset", asset, "--status", "accepted")
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "FIDELITY_CHECK_FAILED")


if __name__ == "__main__":
    unittest.main()
