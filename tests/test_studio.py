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

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/charakit/skills/charakit-expressions/scripts/studio.py"
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
        # Preserve this suite's historical workflow/compatibility coverage using legacy metadata.
        state = studio.read_state(self.root)
        state.pop("quality_policy")
        studio.write_state(self.root, state)

    def candidate(self, expression="angry", size=(64, 96), transparent=True, mouth_state="default"):
        path = self.folder / "candidate-\u00e9.png"
        fixture(path, size=size, color="#bb3366", transparent=transparent)
        return studio.add_asset(self.root, path, expression, mouth_state=mouth_state)["asset"]

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

    def test_presets_cli_lists_new_choices_without_creating_a_project(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "presets"],
                                cwd=self.folder, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        presets = json.loads(result.stdout)["presets"]
        self.assertEqual([p["id"] for p in json.loads(result.stdout)["mouth_states"]], ["default", "closed", "open"])
        self.assertEqual([p["id"] for p in presets], [
            "neutral", "happy", "sad", "angry", "surprised", "eyes_closed",
            "shy", "confused", "wry_smile", "worried", "confident", "crying",
        ])
        self.assertTrue(all(p["name"] and p["direction"] for p in presets))
        self.assertFalse((self.folder / "run.json").exists())

    def test_new_presets_cli_versions_and_export_keep_legacy_selection(self):
        legacy = self.accepted("happy")
        legacy_bytes = (self.root / legacy["path"]).read_bytes()
        chosen = {"happy": legacy}
        for expression in ("shy", "confused", "wry_smile", "worried", "confident", "crying"):
            with self.subTest(expression=expression):
                image = self.folder / f"{expression}.png"
                fixture(image, color="#446688")
                result = subprocess.run([sys.executable, str(SCRIPT), "add", "--project", str(self.root),
                                         "--image", str(image), "--expression", expression],
                                        capture_output=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                first = json.loads(result.stdout)["asset"]
                studio.review_asset(self.root, first["id"], "accepted", "User chose this expression.")
                revision = self.candidate(expression)
                self.assertEqual(revision["version"], 2)
                self.assertEqual(revision["parent_asset_id"], first["id"])
                studio.review_asset(self.root, revision["id"], "accepted", "User reviewed the revision.")
                studio.select_asset(self.root, first["id"])
                chosen[expression] = first
                self.assertEqual(studio.read_state(self.root)["selected"]["happy"], legacy["id"])
        state = studio.read_state(self.root)
        self.assertEqual(state["schema_version"], "1.0")
        self.assertEqual(state["selected"], {key: asset["id"] for key, asset in chosen.items()})
        result = studio.export_pack(self.root)
        with zipfile.ZipFile(result["export"]) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json"} | {
                f"sprites/test_character/{key}.png" for key in chosen})
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual({s["expression"]: s["asset_id"] for s in manifest["sprites"]},
                             {key: asset["id"] for key, asset in chosen.items()})
            for expression, asset in chosen.items():
                self.assertEqual(archive.read(f"sprites/test_character/{expression}.png"),
                                 (self.root / asset["path"]).read_bytes())
        self.assertEqual((self.root / legacy["path"]).read_bytes(), legacy_bytes)

    def test_new_preset_failures_and_unknown_ids_preserve_existing_project(self):
        legacy = self.accepted("happy")
        failed = self.candidate("crying", size=(32, 48))
        self.assertIn("CANVAS_MISMATCH", failed["validation"]["errors"])
        self.assert_code("TECHNICAL_CHECK_FAILED", studio.review_asset, self.root, failed["id"], "accepted")
        self.assertEqual(studio.export_pack(self.root)["asset_ids"], [legacy["id"]])
        state_before = (self.root / "run.json").read_bytes()
        image = self.folder / "unsupported.png"
        fixture(image)
        self.assert_code("INVALID_EXPRESSION", studio.add_asset, self.root, image, "custom_expression")
        result = subprocess.run([sys.executable, str(SCRIPT), "add", "--project", str(self.root),
                                 "--image", str(image), "--expression", "custom_expression"],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / "run.json").read_bytes(), state_before)

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
        asset = self.candidate("crying", size=(32, 48))
        candidate_bytes = (self.root / asset["path"]).read_bytes()
        metadata_bytes = (self.root / "run.json").read_bytes()
        default_output = self.folder / "preview-default.png"
        localized_output = self.folder / "preview-localized.png"
        studio.make_preview(self.root, default_output)
        labels = self.folder / "labels.json"
        labels.write_text(json.dumps({"source": "Original", "reference": "Referencia",
                                     "crying": "Llorando", "unreviewed": "Sin revisión",
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

    def test_legacy_read_and_default_add_do_not_upgrade_or_infer_mouth_state(self):
        legacy = self.accepted("surprised")
        before = (self.root / "run.json").read_bytes()
        self.assertEqual(studio.read_state(self.root)["schema_version"], "1.0")
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertNotIn("mouth_state", legacy)
        self.assertFalse((self.root / "run.schema-1.0.backup.json").exists())
        result = studio.export_pack(self.root)
        self.assertEqual(result["manifest"]["schema_version"], "1.0")
        self.assertEqual(result["manifest"]["sprites"][0]["path"], "sprites/test_character/surprised.png")
        self.assertNotIn("mouth_state", result["manifest"]["sprites"][0])

    def test_mouth_upgrade_backs_up_legacy_and_keeps_independent_versions(self):
        legacy = self.accepted("happy")
        legacy_record = studio.read_state(self.root)["assets"][0]
        before = (self.root / "run.json").read_bytes()
        source_before = (self.root / "source.png").read_bytes()
        closed = self.candidate("happy", mouth_state="closed")
        opened = self.candidate("happy", mouth_state="open")
        revised = self.candidate("happy", mouth_state="open")
        self.assertEqual(closed["id"], "happy_mouth_closed_v001")
        self.assertEqual(opened["id"], "happy_mouth_open_v001")
        self.assertEqual(revised["id"], "happy_mouth_open_v002")
        self.assertIsNone(closed["parent_asset_id"])
        self.assertIsNone(opened["parent_asset_id"])
        self.assertEqual(revised["parent_asset_id"], opened["id"])
        state = studio.read_state(self.root)
        self.assertEqual(state["schema_version"], "1.1")
        self.assertEqual(state["selected"], {"happy": legacy["id"]})
        self.assertEqual((self.root / "run.schema-1.0.backup.json").read_bytes(), before)
        self.assertEqual((self.root / "source.png").read_bytes(), source_before)
        self.assertEqual(state["assets"][0], legacy_record)
        next_default = self.candidate("happy")
        self.assertEqual(next_default["id"], "happy_v002")
        self.assertEqual(next_default["parent_asset_id"], legacy["id"])

    def test_mouth_selection_revision_and_rejection_only_affect_matching_state(self):
        legacy = self.accepted("happy")
        closed = self.candidate("happy", mouth_state="closed")
        opened = self.candidate("happy", mouth_state="open")
        for asset in (closed, opened):
            studio.review_asset(self.root, asset["id"], "accepted", "User selected this state.")
        newer = self.candidate("happy", mouth_state="open")
        studio.review_asset(self.root, newer["id"], "accepted")
        studio.select_asset(self.root, opened["id"])
        self.assertEqual(studio.read_state(self.root)["selected"], {
            "happy": legacy["id"], "happy_mouth_closed": closed["id"], "happy_mouth_open": opened["id"],
        })
        studio.review_asset(self.root, newer["id"], "rejected")
        self.assertEqual(studio.read_state(self.root)["selected"]["happy_mouth_open"], opened["id"])
        studio.review_asset(self.root, opened["id"], "rejected")
        self.assertEqual(studio.read_state(self.root)["selected"], {
            "happy": legacy["id"], "happy_mouth_closed": closed["id"],
        })

    def test_export_mixes_legacy_and_both_mouth_states_with_unchanged_bytes(self):
        legacy = self.accepted("angry")
        assets = [legacy, self.candidate("angry", mouth_state="closed"),
                  self.candidate("angry", mouth_state="open")]
        for asset in assets[1:]:
            studio.review_asset(self.root, asset["id"], "accepted")
        result = studio.export_pack(self.root)
        self.assertEqual(result["manifest"]["schema_version"], "1.1")
        self.assertEqual([s["mouth_state"] for s in result["manifest"]["sprites"]], ["default", "closed", "open"])
        with zipfile.ZipFile(result["export"]) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            for asset, sprite in zip(assets, result["manifest"]["sprites"]):
                self.assertEqual(sprite["path"], f'sprites/test_character/{studio.asset_slot(asset)}.png')
                self.assertEqual(archive.read(sprite["path"]), (self.root / asset["path"]).read_bytes())
        default_only = studio.export_pack(self.root, ids=[legacy["id"]])
        self.assertEqual(default_only["manifest"]["schema_version"], "1.0")

    def test_export_duplicate_mouth_versions_fails_before_creating_archive(self):
        first = self.candidate("happy", mouth_state="open")
        second = self.candidate("happy", mouth_state="open")
        for asset in (first, second):
            studio.review_asset(self.root, asset["id"], "accepted")
        output = self.folder / "duplicate.zip"
        self.assert_code("DUPLICATE_STATE", studio.export_pack, self.root, output, [first["id"], second["id"]])
        self.assertFalse(output.exists())

    def test_invalid_mouth_state_does_not_modify_project(self):
        before = (self.root / "run.json").read_bytes()
        self.assert_code("INVALID_MOUTH_STATE", studio.add_asset, self.root, self.source, "happy", mouth_state="talking")
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertFalse((self.root / "candidates").exists())
        self.assertFalse((self.root / "run.schema-1.0.backup.json").exists())

    def test_failed_mouth_candidate_is_retained_and_cannot_replace_valid_selection(self):
        closed = self.candidate("worried", mouth_state="closed")
        studio.review_asset(self.root, closed["id"], "accepted")
        failed = self.candidate("worried", size=(32, 48), mouth_state="open")
        self.assertTrue((self.root / failed["path"]).exists())
        self.assert_code("TECHNICAL_CHECK_FAILED", studio.review_asset, self.root, failed["id"], "accepted")
        self.assert_code("ART_REVIEW_REQUIRED", studio.select_asset, self.root, failed["id"])
        self.assertEqual(studio.export_pack(self.root)["asset_ids"], [closed["id"]])

    def test_mouth_metadata_and_selection_cannot_mislabel_assets(self):
        opened = self.candidate("happy", mouth_state="open")
        studio.review_asset(self.root, opened["id"], "accepted")
        original = studio.read_state(self.root)
        for mutation in ("mouth", "id", "selection", "schema"):
            with self.subTest(mutation=mutation):
                state = json.loads(json.dumps(original))
                if mutation == "mouth":
                    state["assets"][0]["mouth_state"] = "unknown"
                elif mutation == "id":
                    state["assets"][0]["mouth_state"] = "closed"
                elif mutation == "selection":
                    state["selected"] = {"happy_mouth_closed": opened["id"]}
                else:
                    state["schema_version"] = "1.0"
                studio.write_state(self.root, state)
                self.assert_code("INVALID_PROJECT", studio.read_state, self.root)
        studio.write_state(self.root, original)

    def test_cli_mouth_import_prompt_and_filtered_two_candidate_preview(self):
        assets = [self.candidate("happy", mouth_state="closed"), self.candidate("sad", mouth_state="open")]
        prompt = self.folder / "prompt.txt"
        prompt.write_text("保持开心，仅自然张嘴。", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "add", "--project", str(self.root),
                                 "--image", str(self.source), "--expression", "happy", "--mouth-state", "open",
                                 "--prompt-file", str(prompt)], capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        opened = json.loads(result.stdout)["asset"]
        self.assertEqual(opened["mouth_state"], "open")
        self.assertEqual((self.root / opened["prompt_path"]).read_text(encoding="utf-8"), prompt.read_text(encoding="utf-8"))
        before = (self.root / "run.json").read_bytes()
        labels = self.folder / "labels.json"
        labels.write_text(json.dumps({"happy": "Happy", "mouth_closed": "Closed", "mouth_open": "Open"}), encoding="utf-8")
        output = self.folder / "two-mouth-states.png"
        result = subprocess.run([sys.executable, str(SCRIPT), "preview", "--project", str(self.root),
                                 "--expression", "happy", "--output", str(output), "--labels-file", str(labels),
                                 "--face-box", "10", "10", "54", "40"], capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["asset_ids"], [assets[0]["id"], opened["id"]])
        with Image.open(output) as preview:
            self.assertEqual(preview.size, (1080, 770))
        selected = studio.make_preview(self.root, self.folder / "open-only.png", expression="happy", mouth_state="open")
        self.assertEqual(selected["asset_ids"], [opened["id"]])
        self.assertEqual((self.root / "run.json").read_bytes(), before)

    def test_empty_mouth_preview_filter_does_not_create_misleading_source_only_sheet(self):
        self.candidate("happy", mouth_state="closed")
        output = self.folder / "empty.png"
        self.assert_code("NO_MATCHING_ASSETS", studio.make_preview, self.root, output, expression="happy", mouth_state="open")
        self.assertFalse(output.exists())

    def test_conflicting_upgrade_backup_stops_before_candidate_copy(self):
        backup = self.root / "run.schema-1.0.backup.json"
        backup.write_bytes(b"previous backup")
        before = (self.root / "run.json").read_bytes()
        self.assert_code("MIGRATION_BACKUP_EXISTS", studio.add_asset, self.root, self.source, "happy", mouth_state="open")
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertEqual(backup.read_bytes(), b"previous backup")
        self.assertFalse((self.root / "candidates").exists())

    def test_matching_upgrade_backup_allows_interrupted_upgrade_to_resume(self):
        before = (self.root / "run.json").read_bytes()
        (self.root / "run.schema-1.0.backup.json").write_bytes(before)
        self.candidate("happy", mouth_state="closed")
        self.assertEqual(studio.read_state(self.root)["schema_version"], "1.1")
        self.assertEqual((self.root / "run.schema-1.0.backup.json").read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
