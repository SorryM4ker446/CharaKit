"""Observable file workflow checks using original, synthetic fixtures only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/charakit-expressions/skills/charakit-expressions/scripts/studio.py"
spec = importlib.util.spec_from_file_location("studio", SCRIPT)
studio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio)


def fixture(path: Path, size=(64, 96), color="#aa6688", transparent=True):
    image = Image.new("RGBA" if transparent else "RGB", size, (0, 0, 0, 0) if transparent else "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] - 8), fill=color)
    image.save(path)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "original-\u00e9.png"
        fixture(self.source)
        self.root = self.folder / "character output"
        studio.init_project(self.root, self.source, "test_character")

    def candidate(self, expression="angry", size=(64, 96), transparent=True):
        path = self.folder / "candidate-\u00e9.png"
        fixture(path, size=size, color="#bb3366", transparent=transparent)
        return studio.add_asset(self.root, path, expression)["asset"]

    def accepted(self, expression="angry"):
        asset = self.candidate(expression)
        studio.review_asset(self.root, asset["id"], "accepted", "User explicitly selected this version.")
        return asset

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(studio.StudioError) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_source_snapshot_survives_original_changes(self):
        original_hash = studio.digest(self.source)
        fixture(self.source, color="#2255aa")
        state = studio.read_state(self.root)
        self.assertEqual(state["source_sha256"], original_hash)
        self.assertEqual(studio.digest(self.root / "source.png"), original_hash)

    def test_existing_project_and_outputs_are_not_overwritten(self):
        before = (self.root / "run.json").read_bytes()
        self.assert_code("PROJECT_EXISTS", studio.init_project, self.root, self.source, "other")
        self.assertEqual(before, (self.root / "run.json").read_bytes())
        asset = self.accepted()
        output = self.folder / "pack.zip"
        studio.export_pack(self.root, output)
        packed = output.read_bytes()
        with self.assertRaises(FileExistsError):
            studio.export_pack(self.root, output)
        self.assertEqual(output.read_bytes(), packed)

    def test_versions_preserve_other_assets_and_candidate_bytes(self):
        angry = self.candidate()
        happy = self.candidate("happy")
        original = (self.root / angry["path"]).read_bytes()
        next_angry = self.candidate()
        self.assertEqual(next_angry["version"], 2)
        self.assertEqual(next_angry["parent_asset_id"], angry["id"])
        self.assertEqual((self.root / angry["path"]).read_bytes(), original)
        self.assertTrue((self.root / happy["path"]).is_file())

    def test_failed_canvas_is_retained_but_cannot_be_accepted(self):
        asset = self.candidate(size=(32, 48))
        self.assertTrue((self.root / asset["path"]).is_file())
        self.assertEqual(asset["technical_status"], "failed")
        self.assertIn("CANVAS_MISMATCH", asset["validation"]["errors"])
        self.assert_code("TECHNICAL_CHECK_FAILED", studio.review_asset, self.root, asset["id"], "accepted")

    def test_technical_pass_does_not_imply_art_acceptance(self):
        asset = self.candidate()
        self.assertEqual(asset["technical_status"], "passed")
        self.assertEqual(asset["art_review_status"], "unreviewed")
        self.assert_code("ART_REVIEW_REQUIRED", studio.export_pack, self.root, ids=[asset["id"]])

    def test_rejection_removes_selection(self):
        asset = self.accepted()
        studio.review_asset(self.root, asset["id"], "rejected", "Face detail is not faithful.")
        state = studio.read_state(self.root)
        self.assertEqual(state["selected"], {})
        self.assertEqual(state["assets"][0]["review_note"], "Face detail is not faithful.")
        self.assert_code("NO_SELECTED_ASSETS", studio.export_pack, self.root)

    def test_can_select_old_accepted_version_without_regeneration(self):
        first = self.accepted()
        self.accepted()
        studio.select_asset(self.root, first["id"])
        self.assertEqual(studio.read_state(self.root)["selected"]["angry"], first["id"])
        self.assertEqual(len(studio.read_state(self.root)["assets"]), 2)

    def test_changed_candidate_cannot_be_exported(self):
        asset = self.accepted()
        fixture(self.root / asset["path"], color="#0000ff")
        self.assert_code("TECHNICAL_CHECK_FAILED", studio.export_pack, self.root)
        self.assertFalse((self.root / "exports").exists())

    def test_changed_saved_source_stops_workflow(self):
        fixture(self.root / "source.png", color="#112233")
        self.assert_code("SOURCE_CHANGED", studio.read_state, self.root)

    def test_corrupt_candidate_can_be_rejected_without_losing_other_results(self):
        damaged = self.candidate()
        good = self.accepted("happy")
        (self.root / damaged["path"]).write_bytes(b"broken image")
        studio.review_asset(self.root, damaged["id"], "rejected", "Damaged file")
        state = studio.read_state(self.root)
        self.assertEqual(state["selected"]["happy"], good["id"])
        self.assertEqual(state["assets"][0]["technical_status"], "failed")
        self.assertEqual(studio.export_pack(self.root)["asset_ids"], [good["id"]])

    def test_missing_selected_candidate_blocks_export(self):
        asset = self.accepted()
        (self.root / asset["path"]).unlink()
        self.assert_code("TECHNICAL_CHECK_FAILED", studio.export_pack, self.root)

    def test_json_validation_also_works_in_optimized_python(self):
        state = studio.read_state(self.root)
        state["canvas"]["width"] = 0
        studio.write_state(self.root, state)
        result = subprocess.run([sys.executable, "-O", str(SCRIPT), "status", "--project", str(self.root)],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "INVALID_PROJECT")

    def test_zip_contains_only_chosen_accepted_versions_and_original_pixels(self):
        selected = self.accepted()
        unselected = self.candidate("happy")
        rejected = self.candidate()
        studio.review_asset(self.root, rejected["id"], "rejected")
        result = studio.export_pack(self.root)
        with zipfile.ZipFile(result["export"]) as archive:
            self.assertEqual(set(archive.namelist()), {"sprites/test_character/angry.png", "manifest.json"})
            self.assertEqual(archive.read("sprites/test_character/angry.png"), (self.root / selected["path"]).read_bytes())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["sprites"][0]["asset_id"], selected["id"])
            self.assertEqual(manifest["canvas"], {"width": 64, "height": 96})
            self.assertNotIn(unselected["id"], result["asset_ids"])

    def test_duplicate_expression_is_not_silently_overwritten_in_zip(self):
        first, second = self.accepted(), self.accepted()
        self.assert_code("DUPLICATE_EXPRESSION", studio.export_pack, self.root, ids=[first["id"], second["id"]])

    def test_no_alpha_and_all_transparent_assets_are_rejected(self):
        opaque = self.candidate(transparent=False)
        self.assertIn("NO_TRANSPARENCY", opaque["validation"]["errors"])
        path = self.folder / "empty.png"
        Image.new("RGBA", (64, 96), (0, 0, 0, 0)).save(path)
        empty = studio.add_asset(self.root, path, "happy")["asset"]
        self.assertIn("EMPTY_IMAGE", empty["validation"]["errors"])

    def test_png_palette_transparency_is_recognized(self):
        path = self.folder / "palette.png"
        image = Image.new("P", (64, 96), 0)
        image.putpalette([0, 0, 0, 255, 128, 64] + [0] * (768 - 6))
        ImageDraw.Draw(image).rectangle((12, 12, 50, 80), fill=1)
        image.save(path, transparency=0)
        report = studio.validate_image(path, {"width": 64, "height": 96}, "transparent_sprite")
        self.assertTrue(report["passed"])

    def test_invalid_image_is_not_imported(self):
        path = self.folder / "fake.png"
        path.write_text("not an image", encoding="utf-8")
        self.assert_code("INVALID_IMAGE", studio.add_asset, self.root, path, "happy")
        self.assertEqual(studio.read_state(self.root)["assets"], [])

    def test_path_escape_in_metadata_is_rejected(self):
        asset = self.candidate()
        state = studio.read_state(self.root)
        state["assets"][0]["path"] = "../original-\u00e9.png"
        studio.write_state(self.root, state)
        self.assert_code("INVALID_PATH", studio.read_state, self.root)

    def test_preview_composites_actual_alpha_without_changing_assets(self):
        asset = self.candidate()
        before = (self.root / asset["path"]).read_bytes()
        output = self.folder / "face comparison-\u00e9.png"
        result = studio.make_preview(self.root, output, face_box=[10, 10, 54, 40], background="light")
        with Image.open(output) as preview:
            self.assertEqual(preview.size, tuple(result["size"]))
            self.assertEqual(preview.getpixel((0, 0)), (250, 250, 250))
        self.assertEqual(before, (self.root / asset["path"]).read_bytes())
        with self.assertRaises(FileExistsError):
            studio.make_preview(self.root, output)

    def test_invalid_face_box_does_not_create_preview(self):
        output = self.folder / "bad-preview.png"
        self.assert_code("INVALID_FACE_BOX", studio.make_preview, self.root, output, face_box=[0, 0, 100, 100])
        self.assertFalse(output.exists())

    def test_failed_add_cli_has_structured_report_and_keeps_candidate(self):
        path = self.folder / "wrong-size.png"
        fixture(path, size=(32, 48))
        result = subprocess.run([sys.executable, str(SCRIPT), "add", "--project", str(self.root),
                                 "--image", str(path), "--expression", "angry"],
                                capture_output=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 2)
        response = json.loads(result.stdout)
        self.assertFalse(response["passed"])
        self.assertTrue((self.root / response["asset"]["path"]).is_file())

    def test_localized_preview_cli_changes_labels_without_changing_assets_or_records(self):
        asset = self.candidate(size=(32, 48))
        candidate_bytes = (self.root / asset["path"]).read_bytes()
        metadata_bytes = (self.root / "run.json").read_bytes()
        default_output = self.folder / "preview-default.png"
        localized_output = self.folder / "preview-localized.png"
        studio.make_preview(self.root, default_output)
        labels = self.folder / "labels.json"
        labels.write_text(json.dumps({"source": "Original", "reference": "Referencia",
                                     "angry": "Enojado", "unreviewed": "Sin revisión",
                                     "technical_failed": "Error tecnico",
                                     "CANVAS_MISMATCH": "Tamano distinto"}, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "preview", "--project", str(self.root),
                                 "--output", str(localized_output), "--labels-file", str(labels)],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["preview"], str(localized_output.resolve()))
        with Image.open(default_output) as default, Image.open(localized_output) as localized:
            self.assertEqual(default.size, localized.size)
            self.assertNotEqual(default.crop((0, 420, 720, 520)).tobytes(),
                                localized.crop((0, 420, 720, 520)).tobytes())
        self.assertEqual((self.root / asset["path"]).read_bytes(), candidate_bytes)
        self.assertEqual((self.root / "run.json").read_bytes(), metadata_bytes)

    def test_invalid_preview_labels_fail_before_output_is_created(self):
        output = self.folder / "invalid-labels-preview.png"
        labels = self.folder / "invalid-labels.json"
        labels.write_text('{"source": 123}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "preview", "--project", str(self.root),
                                 "--output", str(output), "--labels-file", str(labels)],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "INVALID_PREVIEW_LABELS")
        self.assertFalse(output.exists())

if __name__ == "__main__":
    unittest.main()
